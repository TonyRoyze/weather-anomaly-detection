from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import xgboost as xgb

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DATASET_BASENAME = "SriLanka_Weather_Dataset_V1.csv"
# Preferred location (works when the Vercel Project Root Directory is `src-python`).
DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / DATASET_BASENAME
# Backwards-compatible location (repo root `src/`).
LEGACY_DATASET_PATH = Path(__file__).resolve().parents[3] / "src" / DATASET_BASENAME

ISOLATION_FEATURES = [
    "temperature_2m_mean",
    "shortwave_radiation_sum",
    "precipitation_sum",
    "windspeed_10m_max",
]

DEFAULT_LOCATION = {
    "latitude": 6.9271,
    "longitude": 79.8612,
    "label": "Colombo",
}

MODELS_LITE_DIR = Path(__file__).resolve().parents[2] / "models-lite"
XGB_MODEL_PATH = MODELS_LITE_DIR / "anomaly_xgb.json"
PREPROCESS_PATH = MODELS_LITE_DIR / "preprocess.json"

_dataset_cache: "_DatasetCache | None" = None
_historical_record_cache: dict[tuple[str, str], dict[str, Any]] = {}
_model_cache: "_ModelCache | None" = None


@dataclass(slots=True)
class _RunningStats:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def add(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def std(self) -> float:
        if self.count < 2:
            return 1.0
        variance = self.m2 / (self.count - 1)
        return math.sqrt(variance) if variance > 0 else 1.0


@dataclass(slots=True)
class _DatasetCache:
    city_catalog: list[dict[str, Any]]
    supported_cities: list[str]
    dataset_min_date: str
    dataset_max_date: str
    city_baselines: dict[str, dict[str, float]]
    global_baseline: dict[str, float]


@dataclass(slots=True)
class _ModelCache:
    booster: xgb.Booster
    numeric_features: list[str]
    numeric_means: dict[str, float]
    numeric_stds: dict[str, float]
    city_labels: list[str]
    city_to_index: dict[str, int]
    probability_threshold: float


def _resolve_dataset_path() -> Path | None:
    if DATASET_PATH.exists():
        return DATASET_PATH
    if LEGACY_DATASET_PATH.exists():
        return LEGACY_DATASET_PATH
    return None


def _to_iso_date(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""

    # Most callers pass YYYY-MM-DD.
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except ValueError:
        pass

    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    return ""


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)

def _signal_label(metric: str) -> str:
    return {
        "Temperature": "Temperature Anomaly",
        "Rainfall": "Rainfall Anomaly",
        "Wind": "Wind Anomaly",
        "Radiation": "Radiation Anomaly",
    }.get(metric, "Weather Anomaly")


def _load_model_cache() -> _ModelCache:
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    if not PREPROCESS_PATH.exists() or not XGB_MODEL_PATH.exists():
        raise RuntimeError(
            "Pretrained model artifacts are missing. Generate and commit "
            f"{XGB_MODEL_PATH} and {PREPROCESS_PATH}."
        )

    payload = json.loads(PREPROCESS_PATH.read_text(encoding="utf-8"))
    numeric_features = list(payload["numeric_features"])
    numeric_means = {str(k): float(v) for k, v in payload["numeric_means"].items()}
    numeric_stds = {str(k): float(v) for k, v in payload["numeric_stds"].items()}
    city_labels = [str(item) for item in payload["city_labels"]]
    probability_threshold = float(payload.get("probability_threshold", 0.55))

    booster = xgb.Booster()
    booster.load_model(XGB_MODEL_PATH)

    _model_cache = _ModelCache(
        booster=booster,
        numeric_features=numeric_features,
        numeric_means=numeric_means,
        numeric_stds=numeric_stds,
        city_labels=city_labels,
        city_to_index={label: idx for idx, label in enumerate(city_labels)},
        probability_threshold=probability_threshold,
    )
    return _model_cache


def _build_feature_vector(
    model: _ModelCache,
    label: str,
    latitude: float,
    longitude: float,
    elevation: float,
    raw_features: dict[str, Any],
) -> np.ndarray:
    values: list[float] = []
    for feature in model.numeric_features:
        if feature == "latitude":
            value = float(latitude)
        elif feature == "longitude":
            value = float(longitude)
        elif feature == "elevation":
            value = float(elevation)
        else:
            value = float(raw_features.get(feature, 0.0))

        mean = float(model.numeric_means.get(feature, 0.0))
        std = float(model.numeric_stds.get(feature, 1.0)) or 1.0
        values.append((value - mean) / std)

    one_hot = [0.0] * len(model.city_labels)
    index = model.city_to_index.get(label)
    if index is not None:
        one_hot[index] = 1.0

    return np.asarray(values + one_hot, dtype=np.float32)


def _load_dataset_cache() -> _DatasetCache:
    global _dataset_cache
    if _dataset_cache is not None:
        return _dataset_cache

    dataset_path = _resolve_dataset_path()
    if dataset_path is None:
        raise RuntimeError(
            "Historical dataset CSV not found. Expected either "
            f"{DATASET_PATH} or {LEGACY_DATASET_PATH}."
        )

    # Per-city stats for ISOLATION_FEATURES.
    per_city: dict[str, dict[str, _RunningStats]] = {}
    global_stats: dict[str, _RunningStats] = {feature: _RunningStats() for feature in ISOLATION_FEATURES}

    # City catalog (lat/long/elevation from first seen row).
    city_catalog_map: dict[str, dict[str, Any]] = {}

    min_date = ""
    max_date = ""

    with dataset_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            city = (row.get("city") or "").strip()
            date_iso = _to_iso_date(row.get("time") or "")
            if not city or not date_iso:
                continue

            if not min_date or date_iso < min_date:
                min_date = date_iso
            if not max_date or date_iso > max_date:
                max_date = date_iso

            if city not in city_catalog_map:
                try:
                    latitude = float(row.get("latitude") or DEFAULT_LOCATION["latitude"])
                    longitude = float(row.get("longitude") or DEFAULT_LOCATION["longitude"])
                    elevation = float(row.get("elevation") or 0.0)
                except ValueError:
                    latitude = DEFAULT_LOCATION["latitude"]
                    longitude = DEFAULT_LOCATION["longitude"]
                    elevation = 0.0

                city_catalog_map[city] = {
                    "id": city.lower().replace(" ", "-"),
                    "label": city,
                    "latitude": latitude,
                    "longitude": longitude,
                    "elevation": elevation,
                }

            city_stats = per_city.setdefault(city, {feature: _RunningStats() for feature in ISOLATION_FEATURES})
            for feature in ISOLATION_FEATURES:
                raw = row.get(feature)
                if raw is None:
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                city_stats[feature].add(value)
                global_stats[feature].add(value)

    city_baselines: dict[str, dict[str, float]] = {}
    for city, stats in per_city.items():
        city_baselines[city] = {}
        for feature in ISOLATION_FEATURES:
            city_baselines[city][f"{feature}_mean"] = stats[feature].mean
            city_baselines[city][f"{feature}_std"] = stats[feature].std()

    global_baseline: dict[str, float] = {}
    for feature in ISOLATION_FEATURES:
        global_baseline[f"{feature}_mean"] = global_stats[feature].mean
        global_baseline[f"{feature}_std"] = global_stats[feature].std()

    city_catalog = [city_catalog_map[city] for city in sorted(city_catalog_map)]
    supported_cities = [city["label"] for city in city_catalog]

    _dataset_cache = _DatasetCache(
        city_catalog=city_catalog,
        supported_cities=supported_cities,
        dataset_min_date=min_date,
        dataset_max_date=max_date,
        city_baselines=city_baselines,
        global_baseline=global_baseline,
    )
    return _dataset_cache


def _metric_z_scores(label: str, raw_features: dict[str, Any], cache: _DatasetCache) -> dict[str, float]:
    baseline = cache.city_baselines.get(label, cache.global_baseline)
    z_scores: dict[str, float] = {}

    for feature, metric in [
        ("temperature_2m_mean", "Temperature"),
        ("precipitation_sum", "Rainfall"),
        ("windspeed_10m_max", "Wind"),
        ("shortwave_radiation_sum", "Radiation"),
    ]:
        mean_value = float(baseline[f"{feature}_mean"])
        std_value = float(baseline[f"{feature}_std"]) or 1.0
        z_scores[metric] = abs(float(raw_features[feature]) - mean_value) / std_value

    return z_scores


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
    key = (label, selected_date)
    cached = _historical_record_cache.get(key)
    if cached is not None:
        return cached

    dataset_path = _resolve_dataset_path()
    if dataset_path is None:
        return None

    with dataset_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("city") or "").strip() != label:
                continue
            if _to_iso_date(row.get("time") or "") != selected_date:
                continue
            normalized = dict(row)
            normalized["time"] = selected_date
            _historical_record_cache[key] = normalized
            return normalized

    return None


def get_prediction_metadata() -> dict[str, Any]:
    cache = _load_dataset_cache()
    return {
        "cities": cache.city_catalog,
        "datasetDateRange": {
            "min": cache.dataset_min_date,
            "max": cache.dataset_max_date,
        },
        "defaultCity": cache.city_catalog[0] if cache.city_catalog else None,
        "modes": [
            {
                "value": "conservative",
                "label": "Conservative",
                "description": "Single scoring mode",
            }
        ],
    }


def export_model_artifacts() -> dict[str, str]:
    raise RuntimeError(
        "Model export is disabled in the lightweight runtime. "
        "This deployment avoids heavy ML dependencies to fit Vercel limits."
    )


async def get_weather_prediction(
    latitude: float,
    longitude: float,
    label: str,
    selected_date: str,
    mode: str = "conservative",
) -> dict[str, Any]:
    cache = _load_dataset_cache()
    selected_mode = "conservative"
    model = _load_model_cache()

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
        elevation = float(forecast_payload.get("elevation") or 0.0)
    else:
        source = "historical-dataset"
        dataset_record = _find_dataset_record(label=label, selected_date=selected_date)
        if dataset_record is None:
            forecast_min = forecast_dates[0] if forecast_dates else ""
            forecast_max = forecast_dates[-1] if forecast_dates else ""
            raise ValueError(
                "The selected date is not available. Choose a date within the forecast window "
                f"({forecast_min} to {forecast_max}) or within the historical dataset range "
                f"({cache.dataset_min_date} to {cache.dataset_max_date})."
            )

        def _f(name: str, fallback: float = 0.0) -> float:
            try:
                return float(dataset_record.get(name) or fallback)
            except ValueError:
                return fallback

        raw_features = {
            "temperature_2m_mean": _f("temperature_2m_mean"),
            "precipitation_sum": _f("precipitation_sum"),
            "precipitation_hours": _f("precipitation_hours"),
            "windspeed_10m_max": _f("windspeed_10m_max"),
            "winddirection_10m_dominant": _f("winddirection_10m_dominant"),
            "shortwave_radiation_sum": _f("shortwave_radiation_sum"),
            "et0_fao_evapotranspiration": _f("et0_fao_evapotranspiration"),
        }
        latitude = _f("latitude", latitude)
        longitude = _f("longitude", longitude)
        elevation = _f("elevation", 0.0)

    z_scores = _metric_z_scores(label=label, raw_features=raw_features, cache=cache)
    sorted_signals = sorted(z_scores.items(), key=lambda item: item[1], reverse=True)
    dominant_signal = sorted_signals[0][0]
    max_z = float(sorted_signals[0][1])

    vector = _build_feature_vector(
        model=model,
        label=label,
        latitude=latitude,
        longitude=longitude,
        elevation=elevation,
        raw_features=raw_features,
    )
    dmatrix = xgb.DMatrix(vector.reshape(1, -1))
    anomaly_probability = float(model.booster.predict(dmatrix)[0])
    is_anomaly = bool(anomaly_probability >= model.probability_threshold)

    top_signals = [{"metric": metric, "zScore": round(float(score), 2)} for metric, score in sorted_signals[:3]]

    category_label = _signal_label(dominant_signal) if is_anomaly else "Normal"
    category_confidence = anomaly_probability if is_anomaly else 1.0 - anomaly_probability

    return {
        "location": {
            "label": label,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
        },
        "selectedDate": selected_date,
        "predictionSource": source,
        "supportedCities": cache.supported_cities,
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
            "label": category_label,
            "confidence": round(float(category_confidence), 4),
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
