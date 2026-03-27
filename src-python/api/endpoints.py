from fastapi import APIRouter, HTTPException, Query

from api.services.open_meteo import get_weather_overview
from api.services.prediction import (
    export_model_artifacts,
    get_prediction_metadata,
    get_weather_prediction,
)

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/forecast")
async def forecast(
    latitude: float = Query(6.9271),
    longitude: float = Query(79.8612),
    label: str = Query("Colombo"),
):
    try:
        return await get_weather_overview(latitude=latitude, longitude=longitude, label=label)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Open-Meteo request failed") from exc


@router.get("/prediction")
async def prediction(
    latitude: float = Query(6.9271),
    longitude: float = Query(79.8612),
    label: str = Query("Colombo"),
    date: str = Query(..., description="Prediction date in YYYY-MM-DD format"),
    mode: str = Query("conservative", description="Prediction mode: conservative or sensitive"),
):
    try:
        return await get_weather_prediction(
            latitude=latitude,
            longitude=longitude,
            label=label,
            selected_date=date,
            mode=mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Prediction request failed: {exc}") from exc


@router.get("/prediction-metadata")
async def prediction_metadata():
    try:
        return get_prediction_metadata()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Prediction metadata request failed") from exc


@router.post("/prediction-models/export")
async def export_prediction_models():
    try:
        return export_model_artifacts()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Prediction model export failed") from exc
