from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models import Company
from app.core.dependencies import get_company_from_api_key
from app.api.web.apiKey import validate_api_key_endpoint


router = APIRouter()
bearer_scheme = None  # kept for backward compat

# --- SCHEMAS (Pydantic) ---

class APIKeyValidateResponseData(BaseModel):
    """Schema representing the validated API key company information."""
    type: str
    username: str
    name: str
    tax_id: str

class APIKeyValidateResponse(BaseModel):
    """Schema representing the validated API key response structure."""
    success: bool = True
    data: APIKeyValidateResponseData


# --- ROTAS ---

# Map validate-api-key to validate_api_key_endpoint from apiKey.py with proper response schema
router.add_api_route(
    "/validate-api-key", 
    endpoint=validate_api_key_endpoint, 
    methods=["GET"],
    response_model=APIKeyValidateResponse,
    summary="Validate API Key",
    description="Validates the provided API key and returns information about the owner company (type, username, name, tax_id)."
)
