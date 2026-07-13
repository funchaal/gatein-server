from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import CompanyUser, TicketLayout

router = APIRouter()

# --- REQUEST SCHEMAS ---

class LayoutUpsertRequest(BaseModel):
    """Schema representing layout creation or update payload parameters."""
    ref: str = Field(..., description="Referência única do layout")
    layout_data: Any = Field(..., description="JSON contendo a estrutura do layout")
    title: Optional[str] = None


# --- RESPONSE SCHEMAS ---

class LayoutResponseData(BaseModel):
    """Schema detailing individual layout metadata configuration parameters."""
    id: int
    ref: str
    title: str
    layout: Any
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class LayoutListResponse(BaseModel):
    """Response containing a list of configurations layouts."""
    success: bool = True
    data: List[LayoutResponseData]

class LayoutSingleResponse(BaseModel):
    """Response containing details of a single configuration layout."""
    success: bool = True
    data: LayoutResponseData

class LayoutUpsertResponseData(BaseModel):
    """Metadata containing status details of a newly created/updated layout."""
    ref: str
    title: str
    status: str

class LayoutUpsertResponse(BaseModel):
    """Response returned upon layout configuration upsert operation."""
    success: bool = True
    data: LayoutUpsertResponseData

class LayoutDeleteResponseData(BaseModel):
    """Metadata containing details of a deleted layout configuration."""
    status: str
    ref: str

class LayoutDeleteResponse(BaseModel):
    """Response returned upon layout configuration deletion operation."""
    success: bool = True
    data: LayoutDeleteResponseData


# --- ROTAS ---

@router.get(
    "/ticket/layouts", 
    response_model=LayoutListResponse,
    summary="Get Ticket Layouts",
    description="Lists all ticket layouts created for the operator's active terminal."
)
def get_ticket_layouts(
    current_user: CompanyUser = Depends(require_permission('ticket_layouts', 'read')),
    db: Session = Depends(get_db)
):
    """
    Fetches all registered ticket layouts for the active company terminal.
    """
    layouts = db.query(TicketLayout).filter_by(terminal_id=current_user.company_id).all()
    
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


@router.get(
    "/ticket/layouts/{ref}", 
    response_model=LayoutSingleResponse,
    summary="Get Ticket Layout by Reference",
    description="Retrieves a specific ticket layout matching the provided reference value."
)
def get_ticket_layout(
    ref: str,
    current_user: CompanyUser = Depends(require_permission('ticket_layouts', 'read')),
    db: Session = Depends(get_db)
):
    """
    Looks up and returns details of a single ticket layout by its reference.
    """
    layout_obj = db.query(TicketLayout).filter_by(
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


@router.put(
    "/ticket/layouts", 
    response_model=LayoutUpsertResponse,
    summary="Upsert Ticket Layout",
    description="Registers a new ticket layout or modifies an existing one by matching reference."
)
def upsert_ticket_layout(
    body: LayoutUpsertRequest,
    current_user: CompanyUser = Depends(require_permission('ticket_layouts', 'write')),
    db: Session = Depends(get_db)
):
    """
    Saves layout details to the database (performs an UPDATE or INSERT action depending on existence).
    """
    layout_obj = db.query(TicketLayout).filter_by(
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
            layout_obj = TicketLayout(
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


@router.delete(
    "/ticket/layouts/{ref}", 
    response_model=LayoutDeleteResponse,
    summary="Delete Ticket Layout",
    description="Deletes a ticket layout identified by reference."
)
def delete_ticket_layout(
    ref: str,
    current_user: CompanyUser = Depends(require_permission('ticket_layouts', 'write')),
    db: Session = Depends(get_db)
):
    """
    Removes a ticket layout configuration by matching reference.
    """
    layout_obj = db.query(TicketLayout).filter_by(
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
