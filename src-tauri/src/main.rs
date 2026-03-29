#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    collections::HashMap,
    net::TcpListener,
    path::PathBuf,
    sync::{Arc, Condvar, Mutex},
    time::Duration,
};

use axum::{extract::{Query, State}, http::HeaderValue, response::Json, routing::get, Router};
// use ndarray::Array2;
use ort::session::Session;
use ort::value::Tensor;
use reqwest::Client;
use serde::Deserialize;
use serde_json::{json, Value};
use tauri::Manager;
use tower_http::cors::{Any, CorsLayer};

// ── Tauri BackendState (same condvar pattern, now wraps the axum URL) ──────────

struct BackendState {
    inner: Mutex<BackendInner>,
    ready: Condvar,
}

#[derive(Default)]
struct BackendInner {
    url:   Option<String>,
    error: Option<String>,
}

impl Default for BackendState {
    fn default() -> Self {
        Self { inner: Mutex::new(BackendInner::default()), ready: Condvar::new() }
    }
}

// ── Deserialized bundle_metadata.json ─────────────────────────────────────────

#[derive(Debug, Clone, Deserialize)]
struct PreprocessorParams {
    numeric_features: Vec<String>,
    scaler_mean:      Vec<f32>,
    scaler_scale:     Vec<f32>,
    ohe_cities:       Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct BundleMetadata {
    anomaly_preprocessor:     PreprocessorParams,
    category_preprocessor:    PreprocessorParams,
    category_encoder_classes: Vec<String>,
    city_baselines:           HashMap<String, HashMap<String, f64>>,
    global_baseline:          HashMap<String, f64>,
    supported_cities:         Vec<String>,
    city_catalog:             Vec<Value>,
    dataset_min_date:         String,
    dataset_max_date:         String,
}

// ── Shared state cloned into every axum handler ────────────────────────────────

#[derive(Clone)]
struct InferenceState {
    anomaly_xgb:  Arc<Mutex<Session>>,
    anomaly_brf:  Arc<Mutex<Session>>,
    category_xgb: Arc<Mutex<Session>>,
    metadata:     Arc<BundleMetadata>,
    http_client:  Client,
}

// ── Raw weather features from Open Meteo ──────────────────────────────────────

struct RawFeatures {
    temperature_2m_mean:        f64,
    precipitation_sum:          f64,
    precipitation_hours:        f64,
    windspeed_10m_max:          f64,
    winddirection_10m_dominant: f64,
    shortwave_radiation_sum:    f64,
    et0_fao_evapotranspiration: f64,
}

// ── Preprocessing (StandardScaler + OHE) ──────────────────────────────────────

fn preprocess(
    params:    &PreprocessorParams,
    raw:       &RawFeatures,
    latitude:  f64,
    longitude: f64,
    elevation: f64,
    city:      &str,
) -> Vec<f32> {
    let lookup: HashMap<&str, f32> = [
        ("precipitation_hours",          raw.precipitation_hours as f32),
        ("winddirection_10m_dominant",   raw.winddirection_10m_dominant as f32),
        ("et0_fao_evapotranspiration",   raw.et0_fao_evapotranspiration as f32),
        ("latitude",                     latitude as f32),
        ("longitude",                    longitude as f32),
        ("elevation",                    elevation as f32),
    ].into_iter().collect();

    let mut v = Vec::with_capacity(params.numeric_features.len() + params.ohe_cities.len());
    for (i, name) in params.numeric_features.iter().enumerate() {
        let x = *lookup.get(name.as_str()).unwrap_or(&0.0);
        v.push((x - params.scaler_mean[i]) / params.scaler_scale[i]);
    }
    for c in &params.ohe_cities {
        v.push(if c == city { 1.0 } else { 0.0 });
    }
    v
}

// ── ONNX inference helpers ─────────────────────────────────────────────────────

fn run_binary(session: &mut Session, features: Vec<f32>) -> Result<(bool, f32), String> {
    let n = features.len();
    let tensor = Tensor::from_array(([1, n], features)).map_err(|e| e.to_string())?;
    let out = session
        .run(ort::inputs!["float_input" => tensor])
        .map_err(|e| e.to_string())?;
    let (_shape, label_data) = out[0].try_extract_tensor::<i64>().map_err(|e| e.to_string())?;
    let (_shape, proba_data) = out[1].try_extract_tensor::<f32>().map_err(|e| e.to_string())?;
    Ok((label_data[0] != 0, proba_data[1]))
}

fn run_multiclass(session: &mut Session, features: Vec<f32>) -> Result<Vec<f32>, String> {
    let n = features.len();
    let tensor = Tensor::from_array(([1, n], features)).map_err(|e| e.to_string())?;
    let out = session
        .run(ort::inputs!["float_input" => tensor])
        .map_err(|e| e.to_string())?;
    let (_shape, proba_data) = out[1].try_extract_tensor::<f32>().map_err(|e| e.to_string())?;
    Ok(proba_data.to_vec())
}

// ── Z-scores ──────────────────────────────────────────────────────────────────

fn compute_z_scores(
    raw:             &RawFeatures,
    city:            &str,
    city_baselines:  &HashMap<String, HashMap<String, f64>>,
    global_baseline: &HashMap<String, f64>,
) -> Vec<(String, f64)> {
    let bl = city_baselines.get(city).unwrap_or(global_baseline);
    let mut scores: Vec<(String, f64)> = [
        ("Temperature", "temperature_2m_mean",    raw.temperature_2m_mean),
        ("Rainfall",    "precipitation_sum",      raw.precipitation_sum),
        ("Wind",        "windspeed_10m_max",      raw.windspeed_10m_max),
        ("Radiation",   "shortwave_radiation_sum", raw.shortwave_radiation_sum),
    ]
    .iter()
    .map(|(lbl, feat, val)| {
        let mean = bl.get(&format!("{feat}_mean")).copied().unwrap_or(0.0);
        let std  = bl.get(&format!("{feat}_std")).copied().unwrap_or(1.0);
        (lbl.to_string(), (val - mean).abs() / std)
    })
    .collect();
    scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    scores
}

// ── Open-Meteo fetch ──────────────────────────────────────────────────────────

const OPEN_METEO_URL: &str = "https://archive-api.open-meteo.com/v1/archive";
const FORECAST_URL: &str = "https://api.open-meteo.com/v1/forecast";

async fn fetch_open_meteo(
    client:        &Client,
    latitude:      f64,
    longitude:     f64,
    selected_date: &str,
) -> Result<(RawFeatures, f64 /* elevation */), String> {
    let query_params = vec![
        ("latitude",      latitude.to_string()),
        ("longitude",     longitude.to_string()),
        ("timezone",      "auto".to_string()),
        ("start_date",    selected_date.to_string()),
        ("end_date",      selected_date.to_string()),
        ("daily",         "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_hours,wind_speed_10m_max,wind_direction_10m_dominant,shortwave_radiation_sum,et0_fao_evapotranspiration".to_string()),
    ];

    let mut resp = client
        .get(OPEN_METEO_URL)
        .query(&query_params)
        .timeout(Duration::from_secs(15))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if !resp.status().is_success() {
        resp = client
            .get(FORECAST_URL)
            .query(&query_params)
            .timeout(Duration::from_secs(15))
            .send()
            .await
            .map_err(|e| e.to_string())?;
    }

    let resp_json: Value = resp
        .error_for_status()
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())?;

    let elevation = resp_json["elevation"].as_f64().unwrap_or(0.0);
    let daily     = &resp_json["daily"];
    let empty_arr = vec![];
    let dates: Vec<&str> = daily["time"]
        .as_array().unwrap_or(&empty_arr)
        .iter().filter_map(|v| v.as_str()).collect();

    let idx = dates.iter().position(|&d| d == selected_date)
        .ok_or_else(|| format!("date {selected_date} not found in historical weather API response"))?;

    let get = |field: &str| {
        daily[field].as_array()
            .and_then(|a| a.get(idx))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0)
    };

    let t_max = get("temperature_2m_max");
    let t_min = get("temperature_2m_min");
    Ok((RawFeatures {
        temperature_2m_mean:        (t_max + t_min) / 2.0,
        precipitation_sum:          get("precipitation_sum"),
        precipitation_hours:        get("precipitation_hours"),
        windspeed_10m_max:          get("wind_speed_10m_max"),
        winddirection_10m_dominant: get("wind_direction_10m_dominant"),
        shortwave_radiation_sum:    get("shortwave_radiation_sum"),
        et0_fao_evapotranspiration: get("et0_fao_evapotranspiration"),
    }, elevation))
}

// ── axum route handlers ───────────────────────────────────────────────────────

async fn health_handler() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}

async fn metadata_handler(State(st): State<InferenceState>) -> Json<Value> {
    let m = &st.metadata;
    Json(json!({
        "cities":          m.city_catalog,
        "datasetDateRange": { "min": m.dataset_min_date, "max": m.dataset_max_date },
        "defaultCity":     m.city_catalog.first().cloned().unwrap_or(Value::Null),
        "modes": [
            { "value": "conservative", "label": "Conservative",
              "description": "XGBoost with fewer false alarms" },
            { "value": "sensitive",    "label": "Sensitive",
              "description": "Balanced Random Forest with higher anomaly recall" },
        ],
    }))
}

#[derive(Deserialize)]
struct PredictQuery {
    latitude:  f64,
    longitude: f64,
    label:     String,
    date:      String,
    #[serde(default = "default_mode")]
    mode:      String,
}
fn default_mode() -> String { "conservative".into() }

type ApiError = (axum::http::StatusCode, Json<Value>);

async fn prediction_handler(
    State(st): State<InferenceState>,
    Query(q):  Query<PredictQuery>,
) -> Result<Json<Value>, ApiError> {
    use axum::http::StatusCode;
    let err = |code: StatusCode, msg: String| (code, Json(json!({ "detail": msg })));

    // 1. Fetch weather data
    let (raw, elevation) = fetch_open_meteo(&st.http_client, q.latitude, q.longitude, &q.date)
        .await
        .map_err(|e| {
            if e.contains("not found in historical") {
                err(StatusCode::NOT_FOUND, e)
            } else {
                err(StatusCode::BAD_GATEWAY, e)
            }
        })?;

    let mode = if q.mode == "sensitive" { "sensitive" } else { "conservative" };
    let meta = &st.metadata;

    // 2. Anomaly inference
    let anom_feat = preprocess(&meta.anomaly_preprocessor, &raw, q.latitude, q.longitude, elevation, &q.label);
    let (is_anomaly, anom_prob) = if mode == "sensitive" {
        run_binary(&mut st.anomaly_brf.lock().unwrap(), anom_feat)
    } else {
        run_binary(&mut st.anomaly_xgb.lock().unwrap(), anom_feat)
    }.map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("anomaly inference: {e}")))?;

    // 3. Category inference
    let cat_feat = preprocess(&meta.category_preprocessor, &raw, q.latitude, q.longitude, elevation, &q.label);
    let cat_proba = run_multiclass(&mut st.category_xgb.lock().unwrap(), cat_feat)
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, format!("category inference: {e}")))?;

    let cat_idx   = cat_proba.iter().enumerate()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(i, _)| i).unwrap_or(0);
    let cat_label = meta.category_encoder_classes.get(cat_idx)
        .cloned().unwrap_or_else(|| "Unknown".into());
    let cat_conf  = cat_proba.get(cat_idx).copied().unwrap_or(0.0);

    // 4. Z-scores & signals
    let z_scores = compute_z_scores(&raw, &q.label, &meta.city_baselines, &meta.global_baseline);
    let dominant = z_scores.first().map(|(s, _)| s.as_str()).unwrap_or("Unknown");
    let signals: Vec<Value> = z_scores.iter().take(3)
        .map(|(m, z)| json!({ "metric": m, "zScore": (z * 100.0).round() / 100.0 }))
        .collect();

    let severity = if anom_prob >= 0.8 { "high" } else if anom_prob >= 0.55 { "medium" } else { "low" };

    Ok(Json(json!({
        "location": {
            "label": q.label, "latitude": q.latitude,
            "longitude": q.longitude, "elevation": elevation,
        },
        "selectedDate":      q.date,
        "predictionSource":  "historical",
        "supportedCities":   meta.supported_cities,
        "modelSummary": {
            "mode":                 mode,
            "anomalyModel":         if mode == "sensitive" { "Balanced Random Forest" } else { "XGBoost" },
            "anomalyModelMetric":   if mode == "sensitive" {
                                        "Recall 0.91, precision 0.16 in notebook evaluation"
                                    } else {
                                        "ROC-AUC 0.9828 in notebook evaluation"
                                    },
            "categoryModel":        "XGBoost",
            "categoryModelMetric":  "Macro F1 0.748 in notebook evaluation",
        },
        "anomalyPrediction": {
            "isAnomaly":   is_anomaly,
            "probability": (anom_prob * 10000.0).round() / 10000.0,
            "severity":    severity,
        },
        "categoryPrediction": {
            "label":         if is_anomaly { cat_label.as_str() } else { "Normal" },
            "confidence":    (cat_conf * 10000.0).round() / 10000.0,
            "dominantSignal": dominant,
        },
        "signals": signals,
        "features": {
            "temperatureMean":          (raw.temperature_2m_mean        * 100.0).round() / 100.0,
            "precipitationSum":         (raw.precipitation_sum           * 100.0).round() / 100.0,
            "precipitationHours":       (raw.precipitation_hours         * 100.0).round() / 100.0,
            "windSpeedMax":             (raw.windspeed_10m_max           * 100.0).round() / 100.0,
            "windDirectionDominant":    (raw.winddirection_10m_dominant  * 100.0).round() / 100.0,
            "shortwaveRadiationSum":    (raw.shortwave_radiation_sum     * 100.0).round() / 100.0,
            "et0FaoEvapotranspiration": (raw.et0_fao_evapotranspiration  * 100.0).round() / 100.0,
        },
    })))
}

// ── port helper ────────────────────────────────────────────────────────────────

fn pick_free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("OS must provide an ephemeral port")
        .local_addr().unwrap().port()
}

// ── ONNX file resolution ───────────────────────────────────────────────────────

fn find_onnx_file(resource_dir: &std::path::Path, name: &str) -> Option<PathBuf> {
    [
        resource_dir.join("models").join("onnx").join(name),
        resource_dir.join("onnx").join(name),
        resource_dir.join(name),
        // development fallback – source tree
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../src-python/models/onnx")
            .join(name),
    ]
    .into_iter()
    .find(|p| p.exists())
}

// ── start in-process axum inference server ─────────────────────────────────────

async fn start_native_server(resource_dir: PathBuf) -> Result<String, String> {
    // Load metadata JSON
    let meta_path = find_onnx_file(&resource_dir, "bundle_metadata.json")
        .ok_or("bundle_metadata.json not found in resources")?;
    let metadata: BundleMetadata = serde_json::from_slice(
        &std::fs::read(&meta_path).map_err(|e| format!("read metadata: {e}"))?,
    )
    .map_err(|e| format!("parse metadata: {e}"))?;

    // Load ONNX models
    let load_session = |name: &str| -> Result<Arc<Mutex<Session>>, String> {
        let path = find_onnx_file(&resource_dir, name)
            .ok_or_else(|| format!("{name} not found in resources"))?;
        Session::builder()
            .map_err(|e| format!("ort builder: {e}"))?
            .commit_from_file(&path)
            .map_err(|e| format!("load {name}: {e}"))
            .map(|s| Arc::new(Mutex::new(s)))
    };
    let anomaly_xgb  = load_session("anomaly_xgb.onnx")?;
    let anomaly_brf  = load_session("anomaly_brf.onnx")?;
    let category_xgb = load_session("category_xgb.onnx")?;

    let state = InferenceState {
        anomaly_xgb,
        anomaly_brf,
        category_xgb,
        metadata:    Arc::new(metadata),
        http_client: Client::new(),
    };

    let cors = CorsLayer::new()
        .allow_origin([
            "tauri://localhost"         .parse::<HeaderValue>().unwrap(),
            "https://tauri.localhost"   .parse::<HeaderValue>().unwrap(),
            "http://tauri.localhost"    .parse::<HeaderValue>().unwrap(),
            "http://localhost:5173"     .parse::<HeaderValue>().unwrap(),
        ])
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/health",                          get(health_handler))
        .route("/api/weather/prediction-metadata", get(metadata_handler))
        .route("/api/weather/prediction",          get(prediction_handler))
        .layer(cors)
        .with_state(state);

    let port     = pick_free_port();
    let listener = tokio::net::TcpListener::bind(format!("127.0.0.1:{port}"))
        .await
        .map_err(|e| format!("bind axum: {e}"))?;

    tokio::spawn(async move {
        axum::serve(listener, app).await.expect("axum inference server crashed");
    });

    Ok(format!("http://127.0.0.1:{port}"))
}

// ── Tauri command ──────────────────────────────────────────────────────────────

#[tauri::command]
fn backend_base_url(state: tauri::State<BackendState>) -> Result<String, String> {
    let guard = state.inner.lock().map_err(|_| "state poisoned".to_string())?;
    let (guard, _) = state
        .ready
        .wait_timeout_while(guard, Duration::from_secs(30), |inner| inner.url.is_none())
        .map_err(|_| "state poisoned".to_string())?;
    if let Some(url) = &guard.url   { return Ok(url.clone()); }
    if let Some(err) = &guard.error { return Err(err.clone()); }
    Err("backend not ready".to_string())
}

// ── main ──────────────────────────────────────────────────────────────────────

fn main() {
    let app = tauri::Builder::default()
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![backend_base_url])
        .setup(|app| {
            let handle       = app.handle().clone();
            let resource_dir = handle
                .path()
                .resource_dir()
                .unwrap_or_else(|_| std::env::current_dir().unwrap());

            tauri::async_runtime::spawn(async move {
                let state: tauri::State<BackendState> = handle.state();
                match start_native_server(resource_dir).await {
                    Ok(url) => {
                        let mut inner = state.inner.lock().expect("poisoned");
                        inner.url = Some(url);
                        state.ready.notify_all();
                    }
                    Err(err) => {
                        eprintln!("Native inference server failed to start: {err}");
                        let mut inner = state.inner.lock().expect("poisoned");
                        inner.error = Some(err);
                        state.ready.notify_all();
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building Tauri app");

    app.run(|_handle, _event| {});
}
