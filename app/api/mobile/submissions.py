import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import boto3
from botocore.exceptions import ClientError

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Submission, SubmissionType, Company
from app.api.web.uploads import delete_r2_image, _get_s3_client
from app.core.sqids import encode_id, decode_id
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Schemas ---

class AttachmentItem(BaseModel):
    url: str
    type: str  # "image" | "pdf"
    name: Optional[str] = None


class SubmissionCreateSchema(BaseModel):
    company_id: str
    submission_type_id: Optional[str] = None
    type_title: str
    field_data: dict = Field(default_factory=dict)
    attachments: List[AttachmentItem] = Field(default_factory=list)


class SubmissionUpdateSchema(BaseModel):
    field_data: dict = Field(default_factory=dict)
    attachments: List[AttachmentItem] = Field(default_factory=list)


# --- Endpoints ---

@router.get(
    "/submissions/presign-attachment",
    summary="Get Pre-signed URL for Submission Attachment Upload (Mobile)",
)
def presign_submission_attachment(
    content_type: str = Query("image/jpeg", description="MIME type of attachment"),
    current_user: User = Depends(get_current_user),
):
    """
    Generates a pre-signed PUT URL for uploading attachments directly to Cloudflare R2.
    Accepts image/* and application/pdf.
    """
    allowed_prefixes = ("image/", "application/pdf")
    if not any(content_type.startswith(p) for p in allowed_prefixes):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_CONTENT_TYPE",
                "message": "Formato de arquivo não suportado. Envie uma imagem ou arquivo PDF."
            }
        )

    ext = "pdf" if content_type == "application/pdf" else "jpg"
    if "png" in content_type:
        ext = "png"
    elif "webp" in content_type:
        ext = "webp"

    object_key = f"submissions/{uuid.uuid4()}.{ext}"

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
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "R2_INIT_ERROR", "message": str(exc)}
        )

    public_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{object_key}"

    return {
        "success": True,
        "upload_url": upload_url,
        "image_path": object_key,
        "public_url": public_url,
    }


@router.get(
    "/submissions",
    summary="List Driver Submissions",
)
def list_driver_submissions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Submission).filter(
        Submission.user_tax_id == current_user.tax_id,
        Submission.is_active == True
    )

    total = query.count()
    submissions = query.order_by(Submission.created_at.desc()).offset(offset).limit(limit).all()

    # Prefetch company names/logos
    company_ids = list(set(s.company_id for s in submissions))
    companies = {}
    if company_ids:
        comps = db.query(Company).filter(Company.id.in_(company_ids)).all()
        for c in comps:
            companies[c.id] = {
                "name": c.name,
                "branch_name": c.branch_name,
                "logo_url": c.config.get("logo_url") if c.config else None
            }

    items = []
    for s in submissions:
        comp_info = companies.get(s.company_id, {})
        items.append({
            "id": encode_id(s.id),
            "company_id": encode_id(s.company_id),
            "company_name": comp_info.get("name") or "Empresa",
            "company_branch_name": comp_info.get("branch_name"),
            "company_logo_url": comp_info.get("logo_url"),
            "submission_type_id": encode_id(s.submission_type_id) if s.submission_type_id else None,
            "type_title": s.type_title,
            "status": s.status,
            "field_data": s.field_data or {},
            "attachments": s.attachments or [],
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "edited_at": s.edited_at.isoformat() if s.edited_at else None,
        })

    return {
        "success": True,
        "data": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/submissions/types/{company_id}",
    summary="Get Submission Types Available for a Company",
)
def get_company_submission_types(
    company_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id_int = decode_id(company_id)
    types = db.query(SubmissionType).filter(
        SubmissionType.company_id == company_id_int,
        SubmissionType.is_active == True
    ).order_by(SubmissionType.created_at.asc()).all()

    formatted_types = [
        {
            "id": encode_id(t.id),
            "title": t.title,
            "ref": t.ref,
            "allow_edit": t.allow_edit,
            "accepts_attachment": t.accepts_attachment,
            "multiple_attachments": t.multiple_attachments,
            "allowed_formats": t.allowed_formats or [],
            "attachment_required": t.attachment_required,
            "fields": t.fields or [],
        }
        for t in types
    ]

    # Always include standard default fallback option
    default_type = {
        "id": None,
        "title": "Outros envios",
        "ref": "default",
        "allow_edit": True,
        "accepts_attachment": True,
        "multiple_attachments": True,
        "allowed_formats": ["image", "pdf"],
        "attachment_required": False,
        "fields": [
            {
                "id": "description",
                "label": "Descrição / Informações (Opcional)",
                "type": "text",
                "multiline": True,
                "required": False,
                "placeholder": "Descreva o que está enviando...",
            }
        ]
    }

    return {
        "success": True,
        "has_custom_types": len(formatted_types) > 0,
        "data": formatted_types if len(formatted_types) > 0 else [default_type],
        "default_option": default_type
    }


@router.post(
    "/submissions",
    summary="Create a New Submission",
)
def create_submission(
    payload: SubmissionCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Decode IDs
        company_id_int = decode_id(payload.company_id)
        sub_type_id_int = decode_id(payload.submission_type_id) if payload.submission_type_id else None

        # Verify company exists
        company = db.query(Company).filter(Company.id == company_id_int, Company.is_active == True).first()
        if not company:
            raise HTTPException(
                status_code=404,
                detail={"code": "COMPANY_NOT_FOUND", "message": "Empresa não encontrada."}
            )

        # Validate against SubmissionType if provided
        submission_type = None
        if sub_type_id_int:
            submission_type = db.query(SubmissionType).filter(
                SubmissionType.id == sub_type_id_int,
                SubmissionType.company_id == company_id_int,
                SubmissionType.is_active == True
            ).first()
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ID", "message": f"ID codificado inválido: {str(e)}"}
        )
    except Exception as e:
        logger.error(f"Error creating submission: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

    if submission_type:
        # Check required fields
        for field in (submission_type.fields or []):
            if field.get("required"):
                field_id = field.get("id") or field.get("label")
                val = payload.field_data.get(field_id) or payload.field_data.get(field.get("label"))
                if not val or str(val).strip() == "":
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "MISSING_REQUIRED_FIELD",
                            "message": f"O campo '{field.get('label')}' é obrigatório."
                        }
                    )

        # Check attachment requirement
        if submission_type.attachment_required and len(payload.attachments) == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ATTACHMENT_REQUIRED",
                    "message": "É necessário anexar ao menos um documento."
                }
            )

    sub = Submission(
        company_id=company_id_int,
        submission_type_id=sub_type_id_int if submission_type else None,
        user_tax_id=current_user.tax_id,
        user_name=current_user.name,
        type_title=payload.type_title,
        status='SENT',
        field_data=payload.field_data,
        attachments=[a.model_dump() for a in payload.attachments],
    )

    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {
        "success": True,
        "message": "Envio realizado com sucesso!",
        "data": {
            "id": sub.id,
            "company_id": sub.company_id,
            "type_title": sub.type_title,
            "status": sub.status,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
        }
    }


@router.put(
    "/submissions/{submission_id}",
    summary="Edit an Existing Submission",
)
def update_submission(
    submission_id: str,
    payload: SubmissionUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub_id_int = decode_id(submission_id)
    sub = db.query(Submission).filter(
        Submission.id == sub_id_int,
        Submission.user_tax_id == current_user.tax_id,
        Submission.is_active == True
    ).first()

    if not sub:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Envio não encontrado."}
        )

    # Check if type allows edit
    if sub.submission_type_id:
        st = db.query(SubmissionType).filter(SubmissionType.id == sub.submission_type_id).first()
        if st and not st.allow_edit:
            raise HTTPException(
                status_code=403,
                detail={"code": "EDIT_NOT_ALLOWED", "message": "Este tipo de envio não permite alterações após a entrega."}
            )

    # Handle attachments delta: identify removed attachments and delete them from R2
    old_urls = {
        (att.get("url") if isinstance(att, dict) else getattr(att, "url", None))
        for att in (sub.attachments or [])
    }
    old_urls = {u for u in old_urls if u}
    new_urls = {att.url for att in payload.attachments if att.url}

    removed_urls = old_urls - new_urls
    for url in removed_urls:
        try:
            delete_r2_image(url)
        except Exception as exc:
            logger.warning(f"Erro ao deletar anexo removido do R2: {exc}")

    sub.field_data = payload.field_data
    sub.attachments = [a.model_dump() for a in payload.attachments]
    sub.status = 'EDITED'
    sub.edited_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(sub)

    return {
        "success": True,
        "message": "Envio atualizado com sucesso!",
        "data": {
            "id": encode_id(sub.id),
            "status": sub.status,
            "edited_at": sub.edited_at.isoformat() if sub.edited_at else None,
        }
    }


@router.patch(
    "/submissions/{submission_id}/cancel",
    summary="Cancel a Submission",
)
def cancel_submission(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub_id_int = decode_id(submission_id)
    sub = db.query(Submission).filter(
        Submission.id == sub_id_int,
        Submission.user_tax_id == current_user.tax_id,
        Submission.is_active == True
    ).first()

    if not sub:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Envio não encontrado."}
        )

    # Delete all attachments from Cloudflare R2
    for att in (sub.attachments or []):
        url = att.get("url") if isinstance(att, dict) else getattr(att, "url", None)
        if url:
            try:
                delete_r2_image(url)
            except Exception as exc:
                logger.warning(f"Erro ao excluir anexo do R2 no cancelamento: {exc}")

    sub.is_active = False
    sub.status = 'CANCELLED'
    sub.cancelled_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "success": True,
        "message": "Envio cancelado com sucesso."
    }
