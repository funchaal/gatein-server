import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_admin_company_user
from app.core.security import hash_secret
from app.models import CompanyUser

router = APIRouter()

# --- SCHEMAS ---

class CreateUserRequest(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    is_admin: bool = False
    permissions: Dict[str, Any] = {}

class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    is_admin: Optional[bool] = None
    permissions: Optional[Dict[str, Any]] = None
    password: Optional[str] = None

class UserResponseData(BaseModel):
    id: str
    username: str
    name: Optional[str]
    is_admin: bool
    permissions: Dict[str, Any]
    created_at: Optional[str] = None

class UserListResponse(BaseModel):
    success: bool = True
    data: List[UserResponseData]

class UserSingleResponse(BaseModel):
    success: bool = True
    data: UserResponseData


# --- ROTAS ---

@router.get("/users", response_model=UserListResponse)
def get_users(
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    users = db.query(CompanyUser).filter_by(company_id=current_user.company_id).all()
    return {"success": True, "data": [
        {
            "id": str(u.id),
            "username": u.username,
            "name": u.name,
            "is_admin": u.is_admin,
            "permissions": u.permissions,
            "created_at": u.created_at.isoformat() + "Z" if u.created_at else None,
        }
        for u in users
    ]}


@router.post("/users", status_code=201, response_model=UserSingleResponse)
def create_user(
    body: CreateUserRequest,
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    if db.query(CompanyUser).filter_by(username=body.username).first():
        raise HTTPException(
            status_code=409, 
            detail={
                "code": "USERNAME_EXISTS", 
                "message": "Este nome de usuário já está em uso."
            }
        )

    try:
        new_user = CompanyUser(
            company_id=current_user.company_id,
            username=body.username,
            password_hash=hash_secret(body.password),
            name=body.name,
            is_admin=body.is_admin,
            permissions=body.permissions,
        )
        db.add(new_user)
        db.commit()
        return {"success": True, "data": {
            "id": str(new_user.id),
            "username": new_user.username,
            "name": new_user.name,
            "is_admin": new_user.is_admin,
            "permissions": new_user.permissions,
            "created_at": new_user.created_at.isoformat() + "Z" if new_user.created_at else None,
        }}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )


@router.put("/users/{user_id}", response_model=UserSingleResponse)
def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    target = db.query(CompanyUser).filter_by(id=user_id, company_id=current_user.company_id).first()
    if not target:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Usuário não encontrado."}
        )

    # Verifica colisão se o username estiver sendo alterado
    if body.username is not None and body.username != target.username:
        if db.query(CompanyUser).filter_by(username=body.username).first():
            raise HTTPException(
                status_code=409, 
                detail={
                    "code": "USERNAME_EXISTS", 
                    "message": "Este nome de usuário já está em uso."
                }
            )

    try:
        if body.name is not None:        target.name = body.name
        if body.username is not None:    target.username = body.username
        if body.is_admin is not None:    target.is_admin = body.is_admin
        if body.permissions is not None: target.permissions = body.permissions
        if body.password:                target.password_hash = hash_secret(body.password)

        db.commit()
        return {"success": True, "data": {
            "id": str(target.id),
            "username": target.username,
            "name": target.name,
            "is_admin": target.is_admin,
            "permissions": target.permissions,
            "created_at": target.created_at.isoformat() + "Z" if target.created_at else None,
        }}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: uuid.UUID,
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    if current_user.id == user_id:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "ACTION_NOT_ALLOWED", 
                "message": "Você não pode deletar sua própria conta."
            }
        )

    target = db.query(CompanyUser).filter_by(id=user_id, company_id=current_user.company_id).first()
    if not target:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Usuário não encontrado."}
        )

    try:
        db.delete(target)
        db.commit()
        return {"success": True, "data": {"status": "deleted", "id": str(user_id)}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )