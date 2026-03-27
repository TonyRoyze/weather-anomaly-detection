from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = REPO_ROOT / "src-python" / "data" / "SriLanka_Weather_Dataset_V1.csv"
MODELS_LITE_DIR = REPO_ROOT / "src-python" / "models-lite"
MODEL_PATH = MODELS_LITE_DIR / "anomaly_xgb.json"
PREPROCESS_PATH = MODELS_LITE_DIR / "preprocess.json"

SIGNAL_COLUMNS = [
    "temperature_2m_mean",
    "precipitation_sum",
    "windspeed_10m_max",
    "shortwave_radiation_sum",
]


@dataclass(slots=True)
class RunningStats:
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


def to_iso_date(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""

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


def severity(probability: float) -> str:
    if probability >= 0.8:
        return "high"
    if probability >= 0.55:
        return "medium"
    return "low"


def dominant_signal_label(z_scores: dict[str, float]) -> str:
    metric = max(z_scores, key=z_scores.get)
    return metric


def category_from_signal(metric: str) -> str:
    return {
        "Temperature": "Temperature Anomaly",
        "Rainfall": "Rainfall Anomaly",
        "Wind": "Wind Anomaly",
        "Radiation": "Radiation Anomaly",
    }.get(metric, "Weather Anomaly")


def compute_baselines(dataset_path: Path) -> tuple[dict[str, dict[str, tuple[float, float]]], dict[str, tuple[float, float]]]:
    per_city: dict[str, dict[str, RunningStats]] = {}
    global_stats: dict[str, RunningStats] = {col: RunningStats() for col in SIGNAL_COLUMNS}

    with dataset_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            city = (row.get("city") or "").strip()
            if not city:
                continue

            city_stats = per_city.setdefault(city, {col: RunningStats() for col in SIGNAL_COLUMNS})
            for col in SIGNAL_COLUMNS:
                raw = row.get(col)
                if raw is None:
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                city_stats[col].add(value)
                global_stats[col].add(value)

    per_city_baselines: dict[str, dict[str, tuple[float, float]]] = {}
    for city, stats in per_city.items():
        per_city_baselines[city] = {col: (stats[col].mean, stats[col].std()) for col in SIGNAL_COLUMNS}

    global_baselines = {col: (global_stats[col].mean, global_stats[col].std()) for col in SIGNAL_COLUMNS}
    return per_city_baselines, global_baselines


def z_scores_for_row(
    row: dict[str, Any],
    city: str,
    per_city: dict[str, dict[str, tuple[float, float]]],
    global_baselines: dict[str, tuple[float, float]],
) -> dict[str, float]:
    baselines = per_city.get(city) or global_baselines

    def z(col: str) -> float:
        mean, std = baselines[col]
        std = std or 1.0
        value = float(row.get(col) or 0.0)
        return abs(value - mean) / std

    return {
        "Temperature": z("temperature_2m_mean"),
        "Rainfall": z("precipitation_sum"),
        "Wind": z("windspeed_10m_max"),
        "Radiation": z("shortwave_radiation_sum"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Find demo anomaly dates from the historical dataset.")
    parser.add_argument("--city", default="", help="Optional exact city label (matches CSV 'city').")
    parser.add_argument("--top", type=int, default=30, help="How many anomalies to keep (sorted by probability).")
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "src-python" / "demo-output" / "anomalies.json"),
        help="Output JSON path.",
    )
    args = parser.parse_args()

    if not DATASET_PATH.exists():
        raise SystemExit(f"Dataset not found at {DATASET_PATH}")
    if not MODEL_PATH.exists() or not PREPROCESS_PATH.exists():
        raise SystemExit(
            "Missing pretrained artifacts. Generate them first:\n"
            "  python src-python/scripts/export_xgb_lite.py\n"
            f"Expected {MODEL_PATH} and {PREPROCESS_PATH}"
        )

    preprocess = json.loads(PREPROCESS_PATH.read_text(encoding="utf-8"))
    numeric_features = list(preprocess["numeric_features"])
    numeric_means = {str(k): float(v) for k, v in preprocess["numeric_means"].items()}
    numeric_stds = {str(k): float(v) for k, v in preprocess["numeric_stds"].items()}
    city_labels = [str(item) for item in preprocess["city_labels"]]
    city_to_index = {label: idx for idx, label in enumerate(city_labels)}
    probability_threshold = float(preprocess.get("probability_threshold", 0.55))

    booster = xgb.Booster()
    booster.load_model(MODEL_PATH)

    per_city_baselines, global_baselines = compute_baselines(DATASET_PATH)

    vectors: list[np.ndarray] = []
    meta: list[dict[str, Any]] = []

    with DATASET_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            city = (row.get("city") or "").strip()
            if not city:
                continue
            if args.city and city != args.city:
                continue

            date_iso = to_iso_date(row.get("time") or "")
            if not date_iso:
                continue

            def get_float(name: str, fallback: float = 0.0) -> float:
                try:
                    return float(row.get(name) or fallback)
                except ValueError:
                    return fallback

            latitude = get_float("latitude")
            longitude = get_float("longitude")
            elevation = get_float("elevation")

            scaled_numeric: list[float] = []
            for feature in numeric_features:
                if feature == "latitude":
                    value = latitude
                elif feature == "longitude":
                    value = longitude
                elif feature == "elevation":
                    value = elevation
                else:
                    value = get_float(feature)

                mean = float(numeric_means.get(feature, 0.0))
                std = float(numeric_stds.get(feature, 1.0)) or 1.0
                scaled_numeric.append((value - mean) / std)

            one_hot = [0.0] * len(city_labels)
            index = city_to_index.get(city)
            if index is not None:
                one_hot[index] = 1.0

            vectors.append(np.asarray(scaled_numeric + one_hot, dtype=np.float32))
            meta.append(
                {
                    "city": city,
                    "date": date_iso,
                    "latitude": latitude,
                    "longitude": longitude,
                    "elevation": elevation,
                    "raw": {
                        "temperature_2m_mean": get_float("temperature_2m_mean"),
                        "precipitation_sum": get_float("precipitation_sum"),
                        "precipitation_hours": get_float("precipitation_hours"),
                        "windspeed_10m_max": get_float("windspeed_10m_max"),
                        "winddirection_10m_dominant": get_float("winddirection_10m_dominant"),
                        "shortwave_radiation_sum": get_float("shortwave_radiation_sum"),
                        "et0_fao_evapotranspiration": get_float("et0_fao_evapotranspiration"),
                    },
                }
            )

    if not vectors:
        raise SystemExit("No dataset rows matched. Check --city and the dataset contents.")

    matrix = np.stack(vectors, axis=0)
    probabilities = booster.predict(xgb.DMatrix(matrix))

    anomalies: list[dict[str, Any]] = []
    for info, prob in zip(meta, probabilities, strict=True):
        probability = float(prob)
        is_anomaly = probability >= probability_threshold
        if not is_anomaly:
            continue

        z_scores = z_scores_for_row(
            {
                **info["raw"],
                "temperature_2m_mean": info["raw"]["temperature_2m_mean"],
                "precipitation_sum": info["raw"]["precipitation_sum"],
                "windspeed_10m_max": info["raw"]["windspeed_10m_max"],
                "shortwave_radiation_sum": info["raw"]["shortwave_radiation_sum"],
            },
            city=info["city"],
            per_city=per_city_baselines,
            global_baselines=global_baselines,
        )
        dominant = dominant_signal_label(z_scores)

        signals_sorted = sorted(z_scores.items(), key=lambda item: item[1], reverse=True)
        top_signals = [{"metric": metric, "zScore": round(float(score), 2)} for metric, score in signals_sorted[:3]]

        anomalies.append(
            {
                "city": info["city"],
                "date": info["date"],
                "probability": round(probability, 4),
                "severity": severity(probability),
                "categoryLabel": category_from_signal(dominant),
                "dominantSignal": dominant,
                "signals": top_signals,
                "features": {
                    "temperatureMean": round(float(info["raw"]["temperature_2m_mean"]), 2),
                    "precipitationSum": round(float(info["raw"]["precipitation_sum"]), 2),
                    "precipitationHours": round(float(info["raw"]["precipitation_hours"]), 2),
                    "windSpeedMax": round(float(info["raw"]["windspeed_10m_max"]), 2),
                    "windDirectionDominant": round(float(info["raw"]["winddirection_10m_dominant"]), 0),
                    "shortwaveRadiationSum": round(float(info["raw"]["shortwave_radiation_sum"]), 2),
                    "et0FaoEvapotranspiration": round(float(info["raw"]["et0_fao_evapotranspiration"]), 2),
                },
            }
        )

    anomalies.sort(key=lambda item: item["probability"], reverse=True)
    anomalies = anomalies[: max(1, int(args.top))]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"threshold": probability_threshold, "items": anomalies}, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(anomalies)} anomalies)")


if __name__ == "__main__":
    main()

