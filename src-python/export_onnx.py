#!/usr/bin/env python3
"""
Phase 1 – Export the trained ModelBundle to ONNX.

Strategy
--------
* XGBoost models  → onnxmltools.convert_xgboost  (reads tree dump, works with XGBoost 3.x)
  ZipMap is stripped from the output graph so probabilities are a plain float32 tensor.
* BalancedRF      → skl2onnx via sklearn RF shim  (already proved to work)

Outputs (src-python/models/onnx/):
  anomaly_xgb.onnx      – XGBoost anomaly classifier  (conservative)
  anomaly_brf.onnx      – Balanced-RF anomaly classifier (sensitive)
  category_xgb.onnx     – XGBoost category classifier
  bundle_metadata.json  – preprocessor params + city / baseline metadata

Run from the repo root:
  source .venv/bin/activate
  python src-python/export_onnx.py
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import onnx
from onnx import TensorProto, helper
from onnxmltools.convert import convert_xgboost
from onnxmltools.convert.common.data_types import FloatTensorType as oml_Float
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from sklearn.ensemble import RandomForestClassifier

# ── paths ──────────────────────────────────────────────────────────────────────
MODELS_DIR  = Path(__file__).resolve().parent / "models"
OUT_DIR     = MODELS_DIR / "onnx"
BUNDLE_PATH = MODELS_DIR / "anomaly_prediction_bundle.joblib"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── helpers ────────────────────────────────────────────────────────────────────

def extract_preprocessor_params(pipeline) -> dict:
    ct         = pipeline.named_steps["preprocessor"]
    scaler     = ct.transformers_[0][1]
    num_feats  = list(ct.transformers_[0][2])
    ohe        = ct.transformers_[1][1]
    ohe_cities = ohe.categories_[0].tolist()
    return {
        "numeric_features": num_feats,
        "scaler_mean":      scaler.mean_.tolist(),
        "scaler_scale":     scaler.scale_.tolist(),
        "ohe_cities":       ohe_cities,
    }


def n_preprocessed(pipeline) -> int:
    p = extract_preprocessor_params(pipeline)
    return len(p["numeric_features"]) + len(p["ohe_cities"])


def strip_zipmap(onnx_model: onnx.ModelProto) -> onnx.ModelProto:
    """
    Remove the trailing ZipMap node (if present) so probabilities are emitted
    as a plain float32 tensor [N, n_classes] instead of Sequence<Map<int64,float>>.
    """
    graph = onnx_model.graph

    # Find the ZipMap node
    zipmap_node = next((n for n in graph.node if n.op_type == "ZipMap"), None)
    if zipmap_node is None:
        return onnx_model          # already clean

    float_proba_name  = zipmap_node.input[0]   # raw float tensor feeding ZipMap
    zipmap_output_name = zipmap_node.output[0]  # what downstream outputs reference

    # Remove ZipMap node
    graph.node.remove(zipmap_node)

    # Rebuild graph outputs: swap the ZipMap output for the raw probabilities name
    new_outputs = []
    for out in graph.output:
        if out.name == zipmap_output_name:
            new_outputs.append(
                helper.make_tensor_value_info(float_proba_name, TensorProto.FLOAT, [None, None])
            )
        else:
            new_outputs.append(out)

    del graph.output[:]
    graph.output.extend(new_outputs)

    onnx.checker.check_model(onnx_model)
    return onnx_model


def export_xgb_to_onnx(pipeline, n_features: int, label: str) -> bytes:
    """Convert a fitted XGBClassifier (inside a Pipeline) to ONNX bytes."""
    xgb_clf = pipeline.named_steps["classifier"]
    booster  = xgb_clf.get_booster()

    raw_model = convert_xgboost(
        booster,
        initial_types=[("float_input", oml_Float([None, n_features]))],
    )
    clean_model = strip_zipmap(raw_model)
    print(f"  ✓ {label}")
    return clean_model.SerializeToString()


def export_brf_to_onnx(pipeline, n_features: int) -> bytes:
    """Convert BalancedRandomForestClassifier to ONNX via a sklearn RF shim."""
    from imblearn.ensemble import BalancedRandomForestClassifier

    brf = pipeline.named_steps["classifier"]

    # Attempt 1: direct skl2onnx (needs registered converter)
    try:
        onnx_model = convert_sklearn(
            brf,
            initial_types=[("float_input", FloatTensorType([None, n_features]))],
            options={BalancedRandomForestClassifier: {"zipmap": False}},
        )
        print("  ✓ BRF (direct skl2onnx conversion)")
        return onnx_model.SerializeToString()
    except Exception:
        pass

    # Attempt 2: copy BRF internals into vanilla RandomForestClassifier
    fake_rf = RandomForestClassifier.__new__(RandomForestClassifier)
    for attr in [
        "estimators_", "classes_", "n_classes_", "n_features_in_",
        "n_outputs_", "estimators_features_",
    ]:
        try:
            setattr(fake_rf, attr, getattr(brf, attr))
        except AttributeError:
            pass

    onnx_model = convert_sklearn(
        fake_rf,
        initial_types=[("float_input", FloatTensorType([None, n_features]))],
        options={RandomForestClassifier: {"zipmap": False}},
    )
    print("  ✓ BRF (sklearn-RF shim conversion)")
    return onnx_model.SerializeToString()


# ── load bundle ────────────────────────────────────────────────────────────────
print("Loading joblib bundle …")
payload         = joblib.load(BUNDLE_PATH)
anomaly_xgb_pl  = payload["anomaly_models"]["conservative"]
anomaly_brf_pl  = payload["anomaly_models"]["sensitive"]
category_pl     = payload["category_model"]
category_enc    = payload["category_encoder"]

n_anomaly  = n_preprocessed(anomaly_xgb_pl)
n_category = n_preprocessed(category_pl)

print(f"\nPreprocessed feature counts:  anomaly={n_anomaly}  category={n_category}")

# ── export ─────────────────────────────────────────────────────────────────────
print("\nExporting ONNX models …")
(OUT_DIR / "anomaly_xgb.onnx").write_bytes(
    export_xgb_to_onnx(anomaly_xgb_pl, n_anomaly, "anomaly_xgb"))
(OUT_DIR / "category_xgb.onnx").write_bytes(
    export_xgb_to_onnx(category_pl, n_category, "category_xgb"))
(OUT_DIR / "anomaly_brf.onnx").write_bytes(
    export_brf_to_onnx(anomaly_brf_pl, n_anomaly))

# ── bundle_metadata.json ───────────────────────────────────────────────────────
print("\nWriting bundle_metadata.json …")
metadata = {
    "anomaly_preprocessor":      extract_preprocessor_params(anomaly_xgb_pl),
    "category_preprocessor":     extract_preprocessor_params(category_pl),
    "category_encoder_classes":  category_enc.classes_.tolist(),
    "city_baselines":            payload["city_baselines"],
    "global_baseline":           payload["global_baseline"],
    "supported_cities":          payload["supported_cities"],
    "city_catalog":              payload["city_catalog"],
    "dataset_min_date":          payload["dataset_min_date"],
    "dataset_max_date":          payload["dataset_max_date"],
    "forecast_feature_columns":  payload["forecast_feature_columns"],
}
(OUT_DIR / "bundle_metadata.json").write_text(
    json.dumps(metadata, indent=2, ensure_ascii=False)
)

# ── summary ────────────────────────────────────────────────────────────────────
print("\n✓ ONNX export complete →", OUT_DIR)
for p in sorted(OUT_DIR.iterdir()):
    print(f"  {p.name:40s}  {p.stat().st_size / 1024:8.1f} KB")
