from __future__ import annotations

from typing import Any

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def get_weather_overview(latitude: float, longitude: float, label: str) -> dict[str, Any]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "wind_speed_10m",
                "surface_pressure",
                "weather_code",
            ]
        ),
        "hourly": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "precipitation_probability",
                "precipitation",
                "wind_speed_10m",
                "cloud_cover",
            ]
        ),
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "wind_speed_10m_max",
            ]
        ),
        "past_days": 1,
        "forecast_days": 5,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(FORECAST_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    return {
        "location": {
            "label": label,
            "latitude": payload["latitude"],
            "longitude": payload["longitude"],
            "timezone": payload["timezone"],
            "elevation": payload["elevation"],
        },
        "current": payload["current"],
        "hourly": payload["hourly"],
        "daily": payload["daily"],
        "source": {
            "name": "Open-Meteo Weather Forecast API",
            "url": "https://open-meteo.com/en/docs",
        },
    }
