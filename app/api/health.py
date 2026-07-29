from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from config import settings

router = APIRouter(tags=["Health"])


class LivenessCheckResponse(BaseModel):
    status: str = Field("ok", description="Liveness status: 'ok'")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    environment: str = Field(..., description="Application environment")
    version: str = Field("1.0.0", description="Application version")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Overall health status: 'ok' or 'unhealthy'")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    environment: str = Field(..., description="Application environment")
    version: str = Field("1.0.0", description="Application version")
    database: str = Field(..., description="Database connection status: 'connected' or 'disconnected'")


@router.get(
    "/health/live",
    response_model=LivenessCheckResponse,
    summary="Liveness Check Endpoint",
    description="Returns 200 OK as long as the API server process is up (without DB test). Designed for Render health checks.",
)
def get_liveness():
    return LivenessCheckResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment=settings.ENVIRONMENT,
        version="1.0.0",
    )


@router.get(
    "/health/ready",
    response_model=HealthCheckResponse,
    summary="Readiness Check Endpoint",
    description="Tests the database connection. Returns 200 OK if healthy or 503 Service Unavailable if unhealthy.",
)
def get_readiness(response: Response, db: Session = Depends(get_db)):
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    is_healthy = db_status == "connected"
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthCheckResponse(
        status="ok" if is_healthy else "unhealthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment=settings.ENVIRONMENT,
        version="1.0.0",
        database=db_status,
    )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check Endpoint (Alias to Readiness)",
    description="Returns readiness status (testing DB connection).",
)
def get_health(response: Response, db: Session = Depends(get_db)):
    return get_readiness(response=response, db=db)


@router.get("/healthz", response_model=HealthCheckResponse, include_in_schema=False)
def get_healthz(response: Response, db: Session = Depends(get_db)):
    return get_readiness(response=response, db=db)


@router.get("/api/v1/health", response_model=HealthCheckResponse, include_in_schema=False)
def get_api_health(response: Response, db: Session = Depends(get_db)):
    return get_readiness(response=response, db=db)

