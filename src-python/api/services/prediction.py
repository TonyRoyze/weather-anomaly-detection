from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from imblearn.ensemble import BalancedRandomForestClassifier
from xgboost import XGBClassifier

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Optional: the CSV is useful for local training and historical backfills, but it is
# not required at runtime when a prebuilt model artifact is shipped (e.g. on Vercel).
DATASET_PATH = Path(__file__).resolve().parents[3] / "src" / "SriLanka_Weather_Dataset_V1.csv"
MODEL_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_ARTIFACT_PATH = MODEL_ARTIFACTS_DIR / "anomaly_prediction_bundle.joblib"

TRAINING_DROP_COLUMNS = [
    "weathercode",
    "sunrise",
    "sunset",
    "country",
    "rain_sum",
    "snowfall_sum",
]

ISOLATION_FEATURES = [
    "temperature_2m_mean",
    "shortwave_radiation_sum",
    "precipitation_sum",
    "windspeed_10m_max",
]

ANOMALY_FEATURE_DROP = [
    "temperature_2m_mean",
    "shortwave_radiation_sum",
    "precipitation_sum",
    "windspeed_10m_max",
    "apparent_temperature_mean",
    "weathercode",
    "time",
    "windgusts_10m_max",
    "temperature_2m_min",
    "apparent_temperature_min",
    "temperature_2m_max",
    "apparent_temperature_max",
    "anomaly",
    "rain_sum",
    "snowfall_sum",
    "is_anomaly",
]

MULTI_FEATURE_DROP = [
    "temperature_2m_mean",
    "shortwave_radiation_sum",
    "precipitation_sum",
    "windspeed_10m_max",
    "apparent_temperature_mean",
    "weathercode",
    "time",
    "windgusts_10m_max",
    "temperature_2m_min",
    "apparent_temperature_min",
    "temperature_2m_max",
    "apparent_temperature_max",
    "anomaly",
    "is_anomaly",
    "anomaly_type",
]


@dataclass(slots=True)
class ModelBundle:
    anomaly_models: dict[str, Pipeline]
    category_model: Pipeline
    category_encoder: LabelEncoder
    city_baselines: dict[str, dict[str, float]]
    global_baseline: dict[str, float]
    supported_cities: list[str]
    city_catalog: list[dict[str, Any]]
    dataset_min_date: str
    dataset_max_date: str
    forecast_feature_columns: list[str]


_bundle: ModelBundle | None = None


def _safe_std(value: float) -> float:
    return value if pd.notna(value) and value > 0 else 1.0


def _dataset_signature() -> dict[str, Any] | None:
    if not DATASET_PATH.exists():
        return None

    stat = DATASET_PATH.stat()
    return {"path": str(DATASET_PATH), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _build_preprocessor(df: pd.DataFrame) -> tuple[ColumnTransformer, list[str]]:
    numeric_features = df.select_dtypes(include=["float64", "int64"]).columns.tolist()
    categorical_features = ["city"] if "city" in df.columns else []

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
        ],
        verbose_feature_names_out=False,
    )

    return preprocessor, numeric_features + categorical_features


def _label_anomaly_type(row: pd.Series, thresholds: dict[str, float]) -> str:
    if int(row["is_anomaly"]) == 0:
        return "Normal"

    temp_dev = abs(row["temperature_2m_mean"] - thresholds["temp_mean"]) / thresholds["temp_std"]
    prec_dev = abs(row["precipitation_sum"] - thresholds["prec_mean"]) / thresholds["prec_std"]
    wind_dev = abs(row["windspeed_10m_max"] - thresholds["wind_mean"]) / thresholds["wind_std"]
    rad_dev = abs(row["shortwave_radiation_sum"] - thresholds["rad_mean"]) / thresholds["rad_std"]

    devs = {
        "Temperature Anomaly": temp_dev,
        "Rainfall Anomaly": prec_dev,
        "Wind Anomaly": wind_dev,
        "Radiation Anomaly": rad_dev,
    }
    return max(devs, key=devs.get)


def _train_models() -> ModelBundle:
    if not DATASET_PATH.exists():
        raise RuntimeError(
            "Training requires the SriLanka_Weather_Dataset_V1.csv dataset file, which is missing."
        )

    df = pd.read_csv(DATASET_PATH)
    df["time"] = pd.to_datetime(df["time"])
    df = df.drop(columns=TRAINING_DROP_COLUMNS, errors="ignore")

    train_df, _ = train_test_split(df, test_size=0.2, random_state=42, stratify=df["city"])
    train_df = train_df.copy()

    iso_model = IsolationForest(contamination=0.01, random_state=42)
    train_df["anomaly"] = iso_model.fit_predict(train_df[ISOLATION_FEATURES])
    train_df["is_anomaly"] = (train_df["anomaly"] == -1).astype(int)

    X_train = train_df.drop(columns=[column for column in ANOMALY_FEATURE_DROP if column in train_df.columns])
    y_train = train_df["is_anomaly"]

    anomaly_preprocessor, forecast_feature_columns = _build_preprocessor(X_train)
    anomaly_model_xgb = Pipeline(
        steps=[
            ("preprocessor", anomaly_preprocessor),
            (
                "classifier",
                XGBClassifier(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=1.0,
                    colsample_bytree=1.0,
                    random_state=42,
                    eval_metric="logloss",
                ),
            ),
        ]
    )
    anomaly_model_xgb.fit(X_train, y_train)

    anomaly_model_brf = Pipeline(
        steps=[
            ("preprocessor", anomaly_preprocessor),
            (
                "classifier",
                BalancedRandomForestClassifier(
                    n_estimators=100,
                    random_state=42,
                ),
            ),
        ]
    )
    anomaly_model_brf.fit(X_train, y_train)

    stats_dict = {
        "temp_mean": float(train_df["temperature_2m_mean"].mean()),
        "temp_std": _safe_std(float(train_df["temperature_2m_mean"].std())),
        "prec_mean": float(train_df["precipitation_sum"].mean()),
        "prec_std": _safe_std(float(train_df["precipitation_sum"].std())),
        "wind_mean": float(train_df["windspeed_10m_max"].mean()),
        "wind_std": _safe_std(float(train_df["windspeed_10m_max"].std())),
        "rad_mean": float(train_df["shortwave_radiation_sum"].mean()),
        "rad_std": _safe_std(float(train_df["shortwave_radiation_sum"].std())),
    }
    train_df["anomaly_type"] = train_df.apply(lambda row: _label_anomaly_type(row, stats_dict), axis=1)

    train_anomalies = train_df[train_df["is_anomaly"] == 1].copy()
    X_train_multi = train_anomalies.drop(
        columns=[column for column in MULTI_FEATURE_DROP if column in train_anomalies.columns]
    )
    y_train_multi = train_anomalies["anomaly_type"]

    category_encoder = LabelEncoder()
    y_train_encoded = category_encoder.fit_transform(y_train_multi)
    category_preprocessor, _ = _build_preprocessor(X_train_multi)
    category_model = Pipeline(
        steps=[
            ("preprocessor", category_preprocessor),
            (
                "classifier",
                XGBClassifier(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=1.0,
                    colsample_bytree=1.0,
                    random_state=42,
                    eval_metric="mlogloss",
                ),
            ),
        ]
    )
    category_model.fit(X_train_multi, y_train_encoded)

    baseline_frame = train_df.groupby("city")[ISOLATION_FEATURES].agg(["mean", "std"])
    city_baselines: dict[str, dict[str, float]] = {}
    for city in baseline_frame.index:
        city_baselines[city] = {}
        for feature in ISOLATION_FEATURES:
            city_baselines[city][f"{feature}_mean"] = float(baseline_frame.loc[city, (feature, "mean")])
            city_baselines[city][f"{feature}_std"] = _safe_std(float(baseline_frame.loc[city, (feature, "std")]))

    global_baseline = {
        f"{feature}_mean": float(train_df[feature].mean()) for feature in ISOLATION_FEATURES
    }
    global_baseline.update(
        {f"{feature}_std": _safe_std(float(train_df[feature].std())) for feature in ISOLATION_FEATURES}
    )

    return ModelBundle(
        anomaly_models={
            "conservative": anomaly_model_xgb,
            "sensitive": anomaly_model_brf,
        },
        category_model=category_model,
        category_encoder=category_encoder,
        city_baselines=city_baselines,
        global_baseline=global_baseline,
        supported_cities=sorted(df["city"].dropna().unique().tolist()),
        city_catalog=[
            {
                "id": str(city).lower().replace(" ", "-"),
                "label": str(city),
                "latitude": float(city_frame.iloc[0]["latitude"]),
                "longitude": float(city_frame.iloc[0]["longitude"]),
                "elevation": float(city_frame.iloc[0]["elevation"]),
            }
            for city, city_frame in df.sort_values("time").groupby("city", sort=True)
        ],
        dataset_min_date=df["time"].min().strftime("%Y-%m-%d"),
        dataset_max_date=df["time"].max().strftime("%Y-%m-%d"),
        forecast_feature_columns=forecast_feature_columns,
    )


def _bundle_to_artifact_payload(bundle: ModelBundle) -> dict[str, Any]:
    # Note: dataset_signature may be None in serverless environments where the
    # CSV is intentionally not present.
    return {
        "dataset_signature": _dataset_signature(),
        "anomaly_models": bundle.anomaly_models,
        "category_model": bundle.category_model,
        "category_encoder": bundle.category_encoder,
        "city_baselines": bundle.city_baselines,
        "global_baseline": bundle.global_baseline,
        "supported_cities": bundle.supported_cities,
        "city_catalog": bundle.city_catalog,
        "dataset_min_date": bundle.dataset_min_date,
        "dataset_max_date": bundle.dataset_max_date,
        "forecast_feature_columns": bundle.forecast_feature_columns,
    }


def _bundle_from_artifact_payload(payload: dict[str, Any]) -> ModelBundle:
    if "anomaly_models" not in payload:
        raise KeyError("Missing anomaly_models in saved artifact")

    return ModelBundle(
        anomaly_models=payload["anomaly_models"],
        category_model=payload["category_model"],
        category_encoder=payload["category_encoder"],
        city_baselines=payload["city_baselines"],
        global_baseline=payload["global_baseline"],
        supported_cities=payload["supported_cities"],
        city_catalog=payload["city_catalog"],
        dataset_min_date=payload["dataset_min_date"],
        dataset_max_date=payload["dataset_max_date"],
        forecast_feature_columns=payload["forecast_feature_columns"],
    )


def _artifact_is_fresh(payload: dict[str, Any]) -> bool:
    # If the dataset isn't present, we can't validate freshness. Prefer the bundled
    # artifact (common on Vercel) instead of triggering an expensive retrain.
    current_signature = _dataset_signature()
    if current_signature is None:
        return True
    return payload.get("dataset_signature") == current_signature


def _save_bundle_to_disk(bundle: ModelBundle) -> None:
    MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(_bundle_to_artifact_payload(bundle), MODEL_ARTIFACT_PATH)


def _load_bundle_from_disk() -> ModelBundle | None:
    if not MODEL_ARTIFACT_PATH.exists():
        return None

    try:
        payload = joblib.load(MODEL_ARTIFACT_PATH)
        if not isinstance(payload, dict):
            return None
        if not _artifact_is_fresh(payload):
            return None
        return _bundle_from_artifact_payload(payload)
    except Exception:
        return None


def get_model_bundle() -> ModelBundle:
    global _bundle

    if _bundle is None:
        loaded_bundle = _load_bundle_from_disk()
        if loaded_bundle is not None:
            _bundle = loaded_bundle
        else:
            raise RuntimeError(
                "Model artifact not found or invalid. Generate it locally and commit "
                f"{MODEL_ARTIFACT_PATH} (and optionally the dataset) before deploying."
            )

    return _bundle


def get_prediction_metadata() -> dict[str, Any]:
    bundle = get_model_bundle()
    return {
        "cities": bundle.city_catalog,
        "datasetDateRange": {
            "min": bundle.dataset_min_date,
            "max": bundle.dataset_max_date,
        },
        "defaultCity": bundle.city_catalog[0] if bundle.city_catalog else None,
        "modes": [
            {
                "value": "conservative",
                "label": "Conservative",
                "description": "XGBoost with fewer false alarms",
            },
            {
                "value": "sensitive",
                "label": "Sensitive",
                "description": "Balanced Random Forest with higher anomaly recall",
            },
        ],
    }


def export_model_artifacts() -> dict[str, str]:
    bundle = _train_models()
    _save_bundle_to_disk(bundle)
    artifact_manifest = {
        "artifact_path": str(MODEL_ARTIFACT_PATH),
        "dataset_signature": json.dumps(_dataset_signature(), sort_keys=True),
    }
    return artifact_manifest


async def _fetch_forecast_payload(latitude: float, longitude: float) -> dict[str, Any]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "forecast_days": 7,
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_hours",
                "wind_speed_10m_max",
                "wind_direction_10m_dominant",
                "shortwave_radiation_sum",
                "et0_fao_evapotranspiration",
            ]
        ),
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(FORECAST_URL, params=params)
        response.raise_for_status()
        return response.json()


def _find_dataset_record(label: str, selected_date: str) -> dict[str, Any] | None:
    if not DATASET_PATH.exists():
        return None

    df = pd.read_csv(DATASET_PATH)
    parsed_date = pd.to_datetime(selected_date).normalize()
    df["time"] = pd.to_datetime(df["time"])
    match = df[(df["city"] == label) & (df["time"].dt.normalize() == parsed_date)]
    if match.empty:
        return None

    record = match.iloc[0].to_dict()
    record["time"] = match.iloc[0]["time"].strftime("%Y-%m-%d")
    return record


def _build_prediction_frame(
    label: str,
    latitude: float,
    longitude: float,
    elevation: float,
    raw_features: dict[str, Any],
    columns: list[str],
) -> pd.DataFrame:
    feature_map = {
        "city": label,
        "latitude": latitude,
        "longitude": longitude,
        "elevation": elevation,
        "precipitation_hours": raw_features.get("precipitation_hours", 0.0),
        "winddirection_10m_dominant": raw_features.get("winddirection_10m_dominant", 0.0),
        "et0_fao_evapotranspiration": raw_features.get("et0_fao_evapotranspiration", 0.0),
    }

    frame = pd.DataFrame([{column: feature_map.get(column) for column in columns}])
    return frame


def _metric_z_scores(label: str, raw_features: dict[str, Any], bundle: ModelBundle) -> dict[str, float]:
    baseline = bundle.city_baselines.get(label, bundle.global_baseline)
    z_scores = {}

    for feature, label_name in [
        ("temperature_2m_mean", "Temperature"),
        ("precipitation_sum", "Rainfall"),
        ("windspeed_10m_max", "Wind"),
        ("shortwave_radiation_sum", "Radiation"),
    ]:
        mean_value = baseline[f"{feature}_mean"]
        std_value = baseline[f"{feature}_std"]
        z_scores[label_name] = abs(float(raw_features[feature]) - mean_value) / std_value

    return z_scores


async def get_weather_prediction(
    latitude: float,
    longitude: float,
    label: str,
    selected_date: str,
    mode: str = "conservative",
) -> dict[str, Any]:
    bundle = get_model_bundle()
    selected_mode = mode if mode in bundle.anomaly_models else "conservative"

    forecast_payload = await _fetch_forecast_payload(latitude=latitude, longitude=longitude)
    forecast_dates = forecast_payload["daily"]["time"]

    source = "forecast"
    if selected_date in forecast_dates:
        index = forecast_dates.index(selected_date)
        raw_features = {
            "temperature_2m_mean": (
                float(forecast_payload["daily"]["temperature_2m_max"][index])
                + float(forecast_payload["daily"]["temperature_2m_min"][index])
            )
            / 2,
            "precipitation_sum": float(forecast_payload["daily"]["precipitation_sum"][index]),
            "precipitation_hours": float(forecast_payload["daily"]["precipitation_hours"][index]),
            "windspeed_10m_max": float(forecast_payload["daily"]["wind_speed_10m_max"][index]),
            "winddirection_10m_dominant": float(
                forecast_payload["daily"]["wind_direction_10m_dominant"][index]
            ),
            "shortwave_radiation_sum": float(forecast_payload["daily"]["shortwave_radiation_sum"][index]),
            "et0_fao_evapotranspiration": float(
                forecast_payload["daily"]["et0_fao_evapotranspiration"][index]
            ),
        }
        elevation = float(forecast_payload["elevation"])
    else:
        source = "historical-dataset"
        dataset_record = _find_dataset_record(label=label, selected_date=selected_date)
        if dataset_record is None:
            if not DATASET_PATH.exists():
                raise ValueError(
                    "The selected date is outside the forecast window. This deployment is configured "
                    "without the historical CSV dataset, so only forecast-window predictions are available."
                )
            raise ValueError(
                "The selected date is not available in the forecast window or the historical dataset."
            )

        raw_features = {
            "temperature_2m_mean": float(dataset_record["temperature_2m_mean"]),
            "precipitation_sum": float(dataset_record["precipitation_sum"]),
            "precipitation_hours": float(dataset_record["precipitation_hours"]),
            "windspeed_10m_max": float(dataset_record["windspeed_10m_max"]),
            "winddirection_10m_dominant": float(dataset_record["winddirection_10m_dominant"]),
            "shortwave_radiation_sum": float(dataset_record["shortwave_radiation_sum"]),
            "et0_fao_evapotranspiration": float(dataset_record["et0_fao_evapotranspiration"]),
        }
        latitude = float(dataset_record["latitude"])
        longitude = float(dataset_record["longitude"])
        elevation = float(dataset_record["elevation"])

    model_frame = _build_prediction_frame(
        label=label,
        latitude=latitude,
        longitude=longitude,
        elevation=elevation,
        raw_features=raw_features,
        columns=bundle.forecast_feature_columns,
    )

    anomaly_model = bundle.anomaly_models[selected_mode]
    anomaly_probability = float(anomaly_model.predict_proba(model_frame)[0][1])
    is_anomaly = bool(anomaly_model.predict(model_frame)[0])

    category_probabilities = bundle.category_model.predict_proba(model_frame)[0]
    category_index = int(np.argmax(category_probabilities))
    category_label = str(bundle.category_encoder.inverse_transform([category_index])[0])
    category_confidence = float(category_probabilities[category_index])

    z_scores = _metric_z_scores(label=label, raw_features=raw_features, bundle=bundle)
    sorted_signals = sorted(z_scores.items(), key=lambda item: item[1], reverse=True)
    dominant_signal = sorted_signals[0][0]
    top_signals = [
        {"metric": metric, "zScore": round(score, 2)} for metric, score in sorted_signals[:3]
    ]

    return {
        "location": {
            "label": label,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
        },
        "selectedDate": selected_date,
        "predictionSource": source,
        "supportedCities": bundle.supported_cities,
        "modelSummary": {
            "mode": selected_mode,
            "anomalyModel": "Balanced Random Forest" if selected_mode == "sensitive" else "XGBoost",
            "anomalyModelMetric": (
                "Recall 0.91, precision 0.16 in notebook evaluation"
                if selected_mode == "sensitive"
                else "ROC-AUC 0.9828 in notebook evaluation"
            ),
            "categoryModel": "XGBoost",
            "categoryModelMetric": "Macro F1 0.748 in notebook evaluation",
        },
        "anomalyPrediction": {
            "isAnomaly": is_anomaly,
            "probability": round(anomaly_probability, 4),
            "severity": (
                "high"
                if anomaly_probability >= 0.8
                else "medium"
                if anomaly_probability >= 0.55
                else "low"
            ),
        },
        "categoryPrediction": {
            "label": category_label if is_anomaly else "Normal",
            "confidence": round(category_confidence, 4) if is_anomaly else round(1 - anomaly_probability, 4),
            "dominantSignal": dominant_signal,
        },
        "signals": top_signals,
        "features": {
            "temperatureMean": round(float(raw_features["temperature_2m_mean"]), 2),
            "precipitationSum": round(float(raw_features["precipitation_sum"]), 2),
            "precipitationHours": round(float(raw_features["precipitation_hours"]), 2),
            "windSpeedMax": round(float(raw_features["windspeed_10m_max"]), 2),
            "windDirectionDominant": round(float(raw_features["winddirection_10m_dominant"]), 2),
            "shortwaveRadiationSum": round(float(raw_features["shortwave_radiation_sum"]), 2),
            "et0FaoEvapotranspiration": round(float(raw_features["et0_fao_evapotranspiration"]), 2),
        },
    }
