import logging
import uuid
from typing import Literal, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError

from app.core.dependencies import require_permission
from app.core.sqids import encode_id
from app.models import CompanyUser
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_s3_client():
    """Creates a boto3 S3 client configured for Cloudflare R2."""
    if not settings.R2_ACCOUNT_ID or not settings.R2_ACCESS_KEY_ID:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "R2_NOT_CONFIGURED",
                "message": "Cloudflare R2 não está configurado no servidor."
            }
        )
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
    )


def delete_r2_image(image_url_or_key: Optional[str]) -> bool:
    """
    Exclui um arquivo do Cloudflare R2 a partir de sua URL pública ou chave de objeto (Key).
    Ex: image_path = "announcements/uuid.webp"
    """
    if not image_url_or_key:
        return False

    clean_path = urlparse(image_url_or_key).path
    # Extrai a key (ex: "announcements/uuid.webp")
    if "announcements/" in clean_path:
        object_key = "announcements/" + clean_path.split("announcements/")[-1]
    elif "companies-profile-pictures/" in clean_path:
        object_key = "companies-profile-pictures/" + clean_path.split("companies-profile-pictures/")[-1]
    elif "submissions/" in clean_path:
        object_key = "submissions/" + clean_path.split("submissions/")[-1]
    else:
        object_key = clean_path.lstrip('/')

    if not object_key:
        return False

    try:
        s3 = _get_s3_client()
        s3.delete_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_key,
        )
        logger.info(f"[R2] Imagem excluída com sucesso do Cloudflare R2: {object_key}")
        return True
    except Exception as exc:
        logger.warning(f"[R2] Erro/falha ao excluir imagem do Cloudflare R2 (Key: {object_key}): {exc}")
        return False


# --- Response Schemas ---

class PresignedUrlResponse(BaseModel):
    """Response with a pre-signed upload URL and the resulting public image path."""
    success: bool = True
    upload_url: str
    image_path: str
    public_url: str


# --- Endpoints ---

@router.get(
    "/uploads/presign/company-logo",
    response_model=PresignedUrlResponse,
    summary="Get Pre-signed URL for Company Logo Upload",
    description=(
        "Generates a temporary pre-signed PUT URL for uploading a company profile picture directly to Cloudflare R2. "
        "Accepts image/webp or image/svg+xml. The frontend must PUT the binary directly to the returned upload_url."
    )
)
def presign_company_logo(
    content_type: str = Query(
        "image/webp",
        description="MIME type of the file being uploaded. Must be image/webp or image/svg+xml."
    ),
    current_user: CompanyUser = Depends(require_permission('company_information', 'write')),
):
    """
    Generates a pre-signed PUT URL for company logo uploads.
    - SVG:  stored under companies-profile-pictures/{company_id}.svg
    - WebP: stored under companies-profile-pictures/{company_id}.webp
    Expires in 1 hour.
    """
    allowed_types = {"image/webp", "image/svg+xml"}
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_CONTENT_TYPE",
                "message": f"content_type deve ser um de: {', '.join(allowed_types)}"
            }
        )

    extension = "svg" if content_type == "image/svg+xml" else "webp"
    # Include company_id only — prevents collisions and gives a stable, predictable path
    object_key = f"companies-profile-pictures/{encode_id(current_user.company_id)}.{extension}"

    s3 = _get_s3_client()
    try:
        upload_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.R2_BUCKET_NAME,
                'Key': object_key,
                'ContentType': content_type,
            },
            ExpiresIn=3600,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "R2_PRESIGN_ERROR", "message": str(exc)}
        )

    public_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{object_key}"

    return {
        "success": True,
        "upload_url": upload_url,
        "image_path": object_key,
        "public_url": public_url,
    }


@router.get(
    "/uploads/presign/announcement-image",
    response_model=PresignedUrlResponse,
    summary="Get Pre-signed URL for Announcement Image Upload",
    description=(
        "Generates a temporary pre-signed PUT URL for uploading an announcement banner image directly to Cloudflare R2. "
        "Only image/webp is accepted. The frontend must PUT the binary directly to the returned upload_url."
    )
)
def presign_announcement_image(
    current_user: CompanyUser = Depends(require_permission('announcements', 'write')),
):
    """
    Generates a pre-signed PUT URL for announcement image uploads.
    - Stored under announcements/{uuid}.webp
    - Expires in 1 hour.
    """
    object_key = f"announcements/{uuid.uuid4()}.webp"

    s3 = _get_s3_client()
    try:
        upload_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.R2_BUCKET_NAME,
                'Key': object_key,
                'ContentType': 'image/webp',
            },
            ExpiresIn=3600,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "R2_PRESIGN_ERROR", "message": str(exc)}
        )

    public_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{object_key}"

    return {
        "success": True,
        "upload_url": upload_url,
        "image_path": object_key,
        "public_url": public_url,
    }
