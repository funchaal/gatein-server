from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import CompanyUser, TripLayout

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
    "/trip/layouts", 
    response_model=LayoutListResponse,
    summary="Get Trip Layouts",
    description="Lists all trip layouts created for the operator's active trucking company."
)
def get_trip_layouts(
    current_user: CompanyUser = Depends(require_permission('trip_layouts', 'read')),
    db: Session = Depends(get_db)
):
    """
    Fetches all registered trip layouts for the active company.
    """
    layouts = db.query(TripLayout).filter_by(trucking_company_id=current_user.company_id).all()
    
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
    "/trip/layouts/{ref}", 
    response_model=LayoutSingleResponse,
    summary="Get Trip Layout by Reference",
    description="Retrieves a specific trip layout matching the provided reference value."
)
def get_trip_layout(
    ref: str,
    current_user: CompanyUser = Depends(require_permission('trip_layouts', 'read')),
    db: Session = Depends(get_db)
):
    """
    Looks up and returns details of a single trip layout by its reference.
    """
    layout_obj = db.query(TripLayout).filter_by(
        trucking_company_id=current_user.company_id,
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
    "/trip/layouts", 
    response_model=LayoutUpsertResponse,
    summary="Upsert Trip Layout",
    description="Registers a new trip layout or modifies an existing one by matching reference."
)
def upsert_trip_layout(
    body: LayoutUpsertRequest,
    current_user: CompanyUser = Depends(require_permission('trip_layouts', 'write')),
    db: Session = Depends(get_db)
):
    """
    Saves layout details to the database (performs an UPDATE or INSERT action depending on existence).
    """
    layout_obj = db.query(TripLayout).filter_by(
        trucking_company_id=current_user.company_id,
        ref=body.ref
    ).first()

    try:
        if layout_obj:
            layout_obj.layout = body.layout_data
            if body.title is not None:
                layout_obj.title = body.title
            action = "updated"
        else:
            layout_obj = TripLayout(
                trucking_company_id=current_user.company_id,
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
    "/trip/layouts/{ref}", 
    response_model=LayoutDeleteResponse,
    summary="Delete Trip Layout",
    description="Deletes a trip layout identified by reference."
)
def delete_trip_layout(
    ref: str,
    current_user: CompanyUser = Depends(require_permission('trip_layouts', 'write')),
    db: Session = Depends(get_db)
):
    """
    Removes a trip layout configuration by matching reference.
    """
    layout_obj = db.query(TripLayout).filter_by(
        trucking_company_id=current_user.company_id,
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
