# Lightweight model artifacts (Vercel)

This backend can run inference with only `xgboost` + `numpy` at runtime.

## Files

- `anomaly_xgb.json` (or `.ubj`): XGBoost `Booster` model.
- `preprocess.json`: numeric scaler params, feature order, and city one-hot mapping.

These files are **not generated on Vercel**. Generate them locally and commit them.

## Generate

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src-python/requirements-dev.txt
python src-python/scripts/export_xgb_lite.py
```

