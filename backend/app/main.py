from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.database import Base, engine
from app import models  # noqa: F401 - registers ORM models with Base.metadata
from app.routes.payments import router as payments_router


class Settings(BaseSettings):
    app_name: str = "FAYDA ID BOT"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Convenient for local development. Production schema changes must use migrations.
    if settings.app_env.lower() != "production":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(payments_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "fayda-id-bot"}


@app.get("/api/v1/status", tags=["system"])
async def status() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "environment": settings.app_env,
        "mode": "payment_api_foundation",
        "identity_integration": "disabled_until_authorized",
        "payments": "customer_api_available_when_configured",
    }
