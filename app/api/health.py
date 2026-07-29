from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from config import settings

router = APIRouter(tags=["Health"])


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Overall health status: 'ok' or 'unhealthy'")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    environment: str = Field(..., description="Application environment")
    version: str = Field("1.0.0", description="Application version")
    database: str = Field(..., description="Database connection status: 'connected' or 'disconnected'")


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check Endpoint",
    description="Returns the health status of the application and database connection.",
)
def get_health(response: Response, db: Session = Depends(get_db)):
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


@router.get("/healthz", response_model=HealthCheckResponse, include_in_schema=False)
def get_healthz(response: Response, db: Session = Depends(get_db)):
    return get_health(response=response, db=db)


@router.get("/api/v1/health", response_model=HealthCheckResponse, include_in_schema=False)
def get_api_health(response: Response, db: Session = Depends(get_db)):
    return get_health(response=response, db=db)
