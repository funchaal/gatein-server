import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import CompanyUser, Submission

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/submissions",
    summary="List/Search Submissions Received by Company",
)
def list_submissions(
    tax_id: Optional[str] = Query(None, description="Filtrar por CPF do motorista"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CompanyUser = Depends(require_permission('submissions', 'read')),
    db: Session = Depends(get_db),
):
    query = db.query(Submission).filter(
        Submission.company_id == current_user.company_id,
        Submission.is_active == True
    )

    if tax_id:
        clean_tax_id = tax_id.replace(".", "").replace("-", "").strip()
        query = query.filter(Submission.user_tax_id.like(f"%{clean_tax_id}%"))

    total = query.count()
    submissions = query.order_by(Submission.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for s in submissions:
        attachments_count = len(s.attachments) if isinstance(s.attachments, list) else 0
        fields_count = len(s.field_data) if isinstance(s.field_data, dict) else 0

        items.append({
            "id": s.id,
            "user_tax_id": s.user_tax_id,
            "user_name": s.user_name or "Motorista",
            "type_title": s.type_title,
            "status": s.status,
            "attachments_count": attachments_count,
            "fields_count": fields_count,
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
    "/submissions/{submission_id}",
    summary="Get Detailed Submission Information",
)
def get_submission_detail(
    submission_id: int,
    current_user: CompanyUser = Depends(require_permission('submissions', 'read')),
    db: Session = Depends(get_db),
):
    sub = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.company_id == current_user.company_id,
        Submission.is_active == True
    ).first()

    if not sub:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Envio não encontrado."}
        )

    return {
        "success": True,
        "data": {
            "id": sub.id,
            "company_id": sub.company_id,
            "submission_type_id": sub.submission_type_id,
            "user_tax_id": sub.user_tax_id,
            "user_name": sub.user_name,
            "type_title": sub.type_title,
            "status": sub.status,
            "field_data": sub.field_data or {},
            "attachments": sub.attachments or [],
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
            "edited_at": sub.edited_at.isoformat() if sub.edited_at else None,
        }
    }
