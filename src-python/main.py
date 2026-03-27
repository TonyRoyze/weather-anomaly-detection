import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import router as weather_router

app = FastAPI(title="Anomalize API", version="0.1.0")

allowed_origins = os.getenv("ANOMALIZE_CORS_ORIGINS")
origins = (
    [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]
    if allowed_origins
    else ["http://localhost:5173", "tauri://localhost"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(weather_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
