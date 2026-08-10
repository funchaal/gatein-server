import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission, get_current_company_user
from app.models import CompanyUser, SubmissionType

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Schemas ---

class FieldConfig(BaseModel):
    id: Optional[str] = None
    label: str
    type: str = "text"  # "text" | "number"
    multiline: bool = False
    required: bool = False
    regex: Optional[str] = None
    placeholder: Optional[str] = None


class SubmissionTypeSchema(BaseModel):
    title: str
    ref: str
    allow_edit: bool = True
    accepts_attachment: bool = False
    multiple_attachments: bool = False
    allowed_formats: List[str] = Field(default_factory=list)  # ["image", "pdf"]
    attachment_required: bool = False
    fields: List[FieldConfig] = Field(default_factory=list)


class SubmissionTypeResponse(BaseModel):
    id: int
    title: str
    ref: str
    allow_edit: bool
    accepts_attachment: bool
    multiple_attachments: bool
    allowed_formats: List[str]
    attachment_required: bool
    fields: List[dict]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.get(
    "/submission-types",
    summary="List Company Submission Types",
)
def get_submission_types(
    current_user: CompanyUser = Depends(require_permission('submissions', 'read')),
    db: Session = Depends(get_db),
):
    types = db.query(SubmissionType).filter(
        SubmissionType.company_id == current_user.company_id,
        SubmissionType.is_active == True
    ).order_by(SubmissionType.created_at.asc()).all()

    return {
        "success": True,
        "data": [
            {
                "id": t.id,
                "title": t.title,
                "ref": t.ref,
                "allow_edit": t.allow_edit,
                "accepts_attachment": t.accepts_attachment,
                "multiple_attachments": t.multiple_attachments,
                "allowed_formats": t.allowed_formats or [],
                "attachment_required": t.attachment_required,
                "fields": t.fields or [],
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in types
        ]
    }


@router.put(
    "/submission-types",
    summary="Create or Update Submission Type (Upsert by ref)",
)
def upsert_submission_type(
    payload: SubmissionTypeSchema,
    current_user: CompanyUser = Depends(require_permission('submissions', 'write')),
    db: Session = Depends(get_db),
):
    # Rule check: must have at least one required field OR attachment_required must be True
    has_required_field = any(f.required for f in payload.fields)
    if not has_required_field and not (payload.accepts_attachment and payload.attachment_required):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "É necessário ter ao menos um campo obrigatório ou o anexo ser obrigatório para salvar um tipo de envio."
            }
        )

    ref = payload.ref.strip().lower()
    title = payload.title.strip()

    if not ref or not title:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_DATA", "message": "Título e referência são obrigatórios."}
        )

    # Check existing
    existing = db.query(SubmissionType).filter(
        SubmissionType.company_id == current_user.company_id,
        SubmissionType.ref == ref,
        SubmissionType.is_active == True
    ).first()

    cleaned_fields = [f.model_dump() for f in payload.fields]

    if existing:
        existing.title = title
        existing.allow_edit = payload.allow_edit
        existing.accepts_attachment = payload.accepts_attachment
        existing.multiple_attachments = payload.multiple_attachments
        existing.allowed_formats = payload.allowed_formats
        existing.attachment_required = payload.attachment_required
        existing.fields = cleaned_fields
        st = existing
    else:
        st = SubmissionType(
            company_id=current_user.company_id,
            title=title,
            ref=ref,
            allow_edit=payload.allow_edit,
            accepts_attachment=payload.accepts_attachment,
            multiple_attachments=payload.multiple_attachments,
            allowed_formats=payload.allowed_formats,
            attachment_required=payload.attachment_required,
            fields=cleaned_fields,
        )
        db.add(st)

    db.commit()
    db.refresh(st)

    return {
        "success": True,
        "data": {
            "id": st.id,
            "title": st.title,
            "ref": st.ref,
            "allow_edit": st.allow_edit,
            "accepts_attachment": st.accepts_attachment,
            "multiple_attachments": st.multiple_attachments,
            "allowed_formats": st.allowed_formats or [],
            "attachment_required": st.attachment_required,
            "fields": st.fields or [],
        }
    }


@router.delete(
    "/submission-types/{ref}",
    summary="Delete Submission Type by Ref",
)
def delete_submission_type(
    ref: str,
    current_user: CompanyUser = Depends(require_permission('submissions', 'write')),
    db: Session = Depends(get_db),
):
    existing = db.query(SubmissionType).filter(
        SubmissionType.company_id == current_user.company_id,
        SubmissionType.ref == ref,
        SubmissionType.is_active == True
    ).first()

    if not existing:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Tipo de envio não encontrado."}
        )

    existing.is_active = False
    db.commit()

    return {"success": True, "message": "Tipo de envio excluído com sucesso."}
