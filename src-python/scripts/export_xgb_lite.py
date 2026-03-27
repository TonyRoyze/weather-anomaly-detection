from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = REPO_ROOT / "src-python" / "data" / "SriLanka_Weather_Dataset_V1.csv"
OUTPUT_DIR = REPO_ROOT / "src-python" / "models-lite"
MODEL_PATH = OUTPUT_DIR / "anomaly_xgb.json"
PREPROCESS_PATH = OUTPUT_DIR / "preprocess.json"

NUMERIC_FEATURES = [
    "latitude",
    "longitude",
    "elevation",
    "temperature_2m_mean",
    "precipitation_sum",
    "precipitation_hours",
    "windspeed_10m_max",
    "winddirection_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
]

SIGNAL_FEATURES = [
    "temperature_2m_mean",
    "shortwave_radiation_sum",
    "precipitation_sum",
    "windspeed_10m_max",
]


def main() -> None:
    if not DATASET_PATH.exists():
        raise SystemExit(f"Dataset not found at {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["city", "time"]).copy()
    df["city"] = df["city"].astype(str)

    # Build a simple training label: anomaly if any signal feature is >= 3 std-dev from
    # its city's mean. (Keeps training script free of scikit-learn.)
    grouped = df.groupby("city", sort=True)
    means = grouped[SIGNAL_FEATURES].mean()
    stds = grouped[SIGNAL_FEATURES].std().replace(0, 1.0)

    def is_anomaly(row: pd.Series) -> int:
        city = row["city"]
        mu = means.loc[city]
        sigma = stds.loc[city]
        z = ((row[SIGNAL_FEATURES] - mu).abs() / sigma).max()
        return int(float(z) >= 3.0)

    df["is_anomaly"] = df.apply(is_anomaly, axis=1)

    cities = sorted(df["city"].unique().tolist())
    city_to_index = {city: idx for idx, city in enumerate(cities)}

    numeric = df[NUMERIC_FEATURES].astype(float)
    numeric_means = numeric.mean()
    numeric_stds = numeric.std().replace(0, 1.0)
    scaled_numeric = (numeric - numeric_means) / numeric_stds

    one_hot = np.zeros((len(df), len(cities)), dtype=np.float32)
    for i, city in enumerate(df["city"].tolist()):
        one_hot[i, city_to_index[city]] = 1.0

    X = np.concatenate([scaled_numeric.to_numpy(dtype=np.float32), one_hot], axis=1)
    y = df["is_anomaly"].to_numpy(dtype=np.float32)

    dtrain = xgb.DMatrix(X, label=y)
    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "max_depth": 6,
        "eta": 0.1,
        "subsample": 1.0,
        "colsample_bytree": 1.0,
        "seed": 42,
    }

    booster = xgb.train(params, dtrain, num_boost_round=150)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    booster.save_model(MODEL_PATH)

    preprocess = {
        "version": 1,
        "numeric_features": NUMERIC_FEATURES,
        "numeric_means": {k: float(v) for k, v in numeric_means.to_dict().items()},
        "numeric_stds": {k: float(v) for k, v in numeric_stds.to_dict().items()},
        "city_labels": cities,
        "probability_threshold": 0.55,
    }
    PREPROCESS_PATH.write_text(json.dumps(preprocess, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {MODEL_PATH}")
    print(f"Wrote {PREPROCESS_PATH}")


if __name__ == "__main__":
    main()

