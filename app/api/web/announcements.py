import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import CompanyUser, Announcement

router = APIRouter()

# --- SCHEMAS ---

class AnnouncementCreateRequest(BaseModel):
    title: str = Field(..., max_length=100)
    subtitle: Optional[str] = Field(None, max_length=150)
    description: Optional[str] = Field(None, max_length=250)
    image_url: Optional[str] = Field(None, max_length=500)
    image_position: Optional[Dict[str, Any]] = None
    is_active: bool = True
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

class AnnouncementUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    subtitle: Optional[str] = Field(None, max_length=150)
    description: Optional[str] = Field(None, max_length=250)
    image_url: Optional[str] = Field(None, max_length=500)
    image_position: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

class AnnouncementStatusUpdateRequest(BaseModel):
    is_active: bool

class AnnouncementResponseData(BaseModel):
    id: str
    company_id: str
    title: str
    subtitle: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    image_position: Dict[str, Any]
    is_active: bool
    start_at: Optional[str]
    end_at: Optional[str]
    created_at: Optional[str]

class AnnouncementListResponse(BaseModel):
    success: bool = True
    data: List[AnnouncementResponseData]

class AnnouncementSingleResponse(BaseModel):
    success: bool = True
    data: AnnouncementResponseData
    message: Optional[str] = None


# --- ROTAS ---

@router.get("/announcements", response_model=AnnouncementListResponse)
def get_announcements(
    current_user: CompanyUser = Depends(require_permission('announcements', 'read')),
    db: Session = Depends(get_db)
):
    results = db.query(Announcement).filter(
        Announcement.company_id == current_user.company_id
    ).order_by(Announcement.created_at.desc()).all()
        
    return {"success": True, "data": [
        {
            "id": str(a.id),
            "company_id": str(a.company_id),
            "title": a.title,
            "subtitle": a.subtitle,
            "description": a.description,
            "image_url": a.image_url,
            "image_position": a.image_position or {"x": 50, "y": 50},
            "is_active": a.is_active,
            "start_at": a.start_at.isoformat() if a.start_at else None,
            "end_at": a.end_at.isoformat() if a.end_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in results
    ]}

@router.post("/announcements", status_code=201, response_model=AnnouncementSingleResponse)
def create_announcement(
    body: AnnouncementCreateRequest,
    current_user: CompanyUser = Depends(require_permission('announcements', 'write')),
    db: Session = Depends(get_db)
):
    try:
        new_announcement = Announcement(
            company_id=current_user.company_id,
            title=body.title,
            subtitle=body.subtitle,
            description=body.description,
            image_url=body.image_url,
            image_position=body.image_position or {"x": 50, "y": 50},
            is_active=body.is_active,
            start_at=body.start_at,
            end_at=body.end_at
        )
        db.add(new_announcement)
        db.commit()
        
        return {
            "success": True,
            "data": {
                "id": str(new_announcement.id),
                "company_id": str(new_announcement.company_id),
                "title": new_announcement.title,
                "subtitle": new_announcement.subtitle,
                "description": new_announcement.description,
                "image_url": new_announcement.image_url,
                "image_position": new_announcement.image_position or {"x": 50, "y": 50},
                "is_active": new_announcement.is_active,
                "start_at": new_announcement.start_at.isoformat() if new_announcement.start_at else None,
                "end_at": new_announcement.end_at.isoformat() if new_announcement.end_at else None,
                "created_at": new_announcement.created_at.isoformat() if new_announcement.created_at else None,
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

@router.put("/announcements/{announcement_id}", response_model=AnnouncementSingleResponse)
def update_announcement(
    announcement_id: uuid.UUID,
    body: AnnouncementUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('announcements', 'write')),
    db: Session = Depends(get_db)
):
    target = db.query(Announcement).filter_by(id=announcement_id, company_id=current_user.company_id).first()
    if not target:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Aviso não encontrado."}
        )

    try:
        if body.title is not None:          target.title = body.title
        if body.subtitle is not None:       target.subtitle = body.subtitle
        if body.description is not None:    target.description = body.description
        if body.image_url is not None:      target.image_url = body.image_url
        if body.image_position is not None: target.image_position = body.image_position
        if body.is_active is not None:      target.is_active = body.is_active
        if body.start_at is not None:        target.start_at = body.start_at
        if body.end_at is not None:          target.end_at = body.end_at

        db.commit()
        
        return {
            "success": True,
            "data": {
                "id": str(target.id),
                "company_id": str(target.company_id),
                "title": target.title,
                "subtitle": target.subtitle,
                "description": target.description,
                "image_url": target.image_url,
                "image_position": target.image_position or {"x": 50, "y": 50},
                "is_active": target.is_active,
                "start_at": target.start_at.isoformat() if target.start_at else None,
                "end_at": target.end_at.isoformat() if target.end_at else None,
                "created_at": target.created_at.isoformat() if target.created_at else None,
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

@router.patch("/announcements/{announcement_id}/status", response_model=AnnouncementSingleResponse)
def update_announcement_status(
    announcement_id: uuid.UUID,
    body: AnnouncementStatusUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('announcements', 'write')),
    db: Session = Depends(get_db)
):
    target = db.query(Announcement).filter_by(id=announcement_id, company_id=current_user.company_id).first()
    if not target:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Aviso não encontrado."}
        )

    try:
        target.is_active = body.is_active
        db.commit()
        
        return {
            "success": True,
            "data": {
                "id": str(target.id),
                "company_id": str(target.company_id),
                "title": target.title,
                "subtitle": target.subtitle,
                "description": target.description,
                "image_url": target.image_url,
                "image_position": target.image_position or {"x": 50, "y": 50},
                "is_active": target.is_active,
                "start_at": target.start_at.isoformat() if target.start_at else None,
                "end_at": target.end_at.isoformat() if target.end_at else None,
                "created_at": target.created_at.isoformat() if target.created_at else None,
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

@router.delete("/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: uuid.UUID,
    current_user: CompanyUser = Depends(require_permission('announcements', 'write')),
    db: Session = Depends(get_db)
):
    target = db.query(Announcement).filter_by(id=announcement_id, company_id=current_user.company_id).first()
    if not target:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Aviso não encontrado."}
        )

    try:
        db.delete(target)
        db.commit()
        return {"success": True, "data": {"status": "deleted", "id": str(announcement_id)}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )
