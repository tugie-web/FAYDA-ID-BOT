from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FAYDA ID BOT"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "fayda-id-bot"}


@app.get("/api/v1/status", tags=["system"])
async def status() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "environment": settings.app_env,
        "mode": "foundation",
        "identity_integration": "disabled_until_authorized",
        "payments": "not_configured",
    }
