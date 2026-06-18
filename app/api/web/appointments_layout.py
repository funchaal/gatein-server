from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import CompanyUser, AppointmentLayout

router = APIRouter()

class LayoutUpsertRequest(BaseModel):
    ref: str = Field(..., description="Referência única do layout")
    layout_data: Any = Field(..., description="JSON contendo a estrutura do layout")
    title: Optional[str] = None

@router.get("/appointment/layouts")
def get_appointment_layouts(
    current_user: CompanyUser = Depends(require_permission('appointment_layouts', 'read')),
    db: Session = Depends(get_db)
):

    layouts = db.query(AppointmentLayout).filter_by(terminal_id=current_user.company_id).all()
    
    return {"success": True, "data": [
        {
            "id": l.id,
            "ref": l.ref,
            "title": l.title,
            "layout": l.layout,
            "created_at": l.created_at.isoformat() + "Z" if l.created_at else None,
            "updated_at": l.updated_at.isoformat() + "Z" if l.updated_at else None,
        }
        for l in layouts
    ]}


@router.get("/appointment/layouts/{ref}")
def get_appointment_layout(
    ref: str,
    current_user: CompanyUser = Depends(require_permission('appointment_layouts', 'read')),
    db: Session = Depends(get_db)
):

    layout_obj = db.query(AppointmentLayout).filter_by(
        terminal_id=current_user.company_id,
        ref=ref
    ).first()

    if not layout_obj:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    return {"success": True, "data": {
        "id": layout_obj.id,
        "ref": layout_obj.ref,
        "title": layout_obj.title,
        "layout": layout_obj.layout,
        "created_at": layout_obj.created_at.isoformat() + "Z" if layout_obj.created_at else None,
        "updated_at": layout_obj.updated_at.isoformat() + "Z" if layout_obj.updated_at else None,
    }}


@router.put("/appointment/layouts")
def upsert_appointment_layout(
    body: LayoutUpsertRequest,
    current_user: CompanyUser = Depends(require_permission('appointment_layouts', 'write')),
    db: Session = Depends(get_db)
):

    layout_obj = db.query(AppointmentLayout).filter_by(
        terminal_id=current_user.company_id,
        ref=body.ref
    ).first()

    try:
        if layout_obj:
            layout_obj.layout = body.layout_data
            if body.title is not None:
                layout_obj.title = body.title
            action = "updated"
        else:
            layout_obj = AppointmentLayout(
                terminal_id=current_user.company_id,
                ref=body.ref,
                title=body.title or body.ref,
                layout=body.layout_data,
            )
            db.add(layout_obj)
            action = "created"

        db.commit()
        return {"success": True, "data": {
            "ref": layout_obj.ref,
            "title": layout_obj.title,
            "status": action,
        }}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.delete("/appointment/layouts/{ref}")
def delete_appointment_layout(
    ref: str,
    current_user: CompanyUser = Depends(require_permission('appointment_layouts', 'write')),
    db: Session = Depends(get_db)
):

    layout_obj = db.query(AppointmentLayout).filter_by(
        terminal_id=current_user.company_id,
        ref=ref
    ).first()

    if not layout_obj:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    try:
        db.delete(layout_obj)
        db.commit()
        return {"success": True, "data": {"status": "deleted", "ref": ref}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})
