import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import Literal, List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import hash_secret, APIKeyManager
from app.core.dependencies import get_current_super_admin
from app.models import Terminal, TruckingCompany, CompanyUser, AllowedDomain, Appointment, AppointmentLog, Trip, TripLog, Company, CompanyService, Driver
from app.tools import extract_domain
from config import settings 

router = APIRouter(tags=["System Root"])


# --- REQUEST SCHEMAS ---

class AdminUserCreate(BaseModel):
    """Schema representing company administrator user creation."""
    name: str = Field(..., description="Nome do usuário administrador")
    username: str = Field(..., description="Login de acesso web (ex: admin.porto)")
    password: str = Field(..., description="Senha de acesso web")

class SystemCompanyCreate(BaseModel):
    """Schema representing bootstrap request for a new company."""
    type: Literal["terminal", "trucking_company"] = Field(..., description="Tipo de empresa")
    company_username: str = Field(..., description="Identificador único da empresa (ex: porto_sul)")
    name: str = Field(..., description="Razão Social ou Nome Fantasia")
    tax_id: str = Field(..., description="CNPJ")
    phone: str
    email: EmailStr
    admin_user: AdminUserCreate

class AllowedDomainCreate(BaseModel):
    """Schema for requesting domain validation list access."""
    url: HttpUrl 
    is_active: Optional[bool] = True

class CompanyUserPasswordUpdate(BaseModel):
    """Schema representing administrator password reset request payload."""
    password: str = Field(..., description="Nova senha de acesso do usuário da empresa")


# --- RESPONSE SCHEMAS ---

class SystemCompanyCreateResponseData(BaseModel):
    """Metadata detailing the created company and credentials details."""
    company_id: str
    type: str
    name: str
    admin_username: str
    initial_api_key: str
    message: str

class SystemCompanyCreateResponse(BaseModel):
    """Response returned upon successful company bootstrapping."""
    success: bool = True
    data: SystemCompanyCreateResponseData

class AllowedDomainResponseData(BaseModel):
    """Metadata outlining registered domain status settings."""
    id: Optional[int] = None
    domain: str
    is_active: Optional[bool] = True

class AllowedDomainResponse(BaseModel):
    """Response containing allowed domain profile information."""
    success: bool = True
    message: str
    data: AllowedDomainResponseData

class SimpleSuccessResponse(BaseModel):
    """Standard success model containing success flag and message details."""
    success: bool = True
    message: str

class AdminAppointmentLogItem(BaseModel):
    """Schema mapping appointment audit log item details."""
    id: str
    event: str
    message: str
    json_data: Optional[Dict[str, Any]] = Field(None, validation_alias="json", serialization_alias="json")
    created_at: Optional[str] = None

class AdminAppointmentData(BaseModel):
    """Schema containing administrative appointment profile details."""
    id: str
    terminal_id: str
    ref: str
    layout_ref: Optional[str] = None
    user_tax_id: str
    status: str
    summary: str
    vehicle_plate: Optional[str] = None
    schedule_start_time: Optional[str] = None
    schedule_end_time: Optional[str] = None
    schedule_start_tolerance: Optional[int] = None
    schedule_end_tolerance: Optional[int] = None
    custom_data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class DriverLogResponseItem(BaseModel):
    """Schema representing driver profile details associated with the log search."""
    tax_id: str
    driver_license_number: Optional[str] = None
    driver_license_category: Optional[str] = None

class AdminAppointmentLogDataContent(BaseModel):
    """Nested container holding administrative appointment details, driver profile, and historical logs."""
    appointment: AdminAppointmentData
    driver: Optional[DriverLogResponseItem] = None
    logs: List[AdminAppointmentLogItem]

class AdminAppointmentLogsResponseItem(BaseModel):
    """Unified container mapping appointment and its audit logs history."""
    ref: str
    found: bool
    data: Optional[AdminAppointmentLogDataContent] = None

class AdminAppointmentLogsResponse(BaseModel):
    """Response returned upon administrative query for appointment logs."""
    success: bool = True
    data: List[AdminAppointmentLogsResponseItem]

class AdminTripLogItem(BaseModel):
    """Schema mapping trip audit log item details."""
    id: str
    event: str
    message: str
    json_data: Optional[Dict[str, Any]] = Field(None, validation_alias="json", serialization_alias="json")
    created_at: Optional[str] = None

class AdminTripData(BaseModel):
    """Schema containing administrative trip profile details."""
    id: str
    trucking_company_id: str
    ref: str
    layout_ref: Optional[str] = None
    driver_id: Optional[str] = None
    vehicle_plate: Optional[str] = None
    status: str
    summary: str
    schedule_start_time: Optional[str] = None
    schedule_end_time: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = None
    origin_street: Optional[str] = None
    origin_number: Optional[str] = None
    origin_city: Optional[str] = None
    origin_state: Optional[str] = None
    origin_country: Optional[str] = None
    origin_zip: Optional[str] = None
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    destiny_street: Optional[str] = None
    destiny_number: Optional[str] = None
    destiny_city: Optional[str] = None
    destiny_state: Optional[str] = None
    destiny_country: Optional[str] = None
    destiny_zip: Optional[str] = None
    destiny_lat: Optional[float] = None
    destiny_lng: Optional[float] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class AdminTripLogDataContent(BaseModel):
    """Nested container holding administrative trip details, driver profile, and historical logs."""
    trip: AdminTripData
    driver: Optional[DriverLogResponseItem] = None
    logs: List[AdminTripLogItem]

class AdminTripLogsResponseItem(BaseModel):
    """Unified container mapping trip and its audit logs history."""
    ref: str
    found: bool
    data: Optional[AdminTripLogDataContent] = None

class AdminTripLogsResponse(BaseModel):
    """Response returned upon administrative query for trip logs."""
    success: bool = True
    data: List[AdminTripLogsResponseItem]


# --- ROTAS ---

@router.post(
    "/companies", 
    status_code=201, 
    response_model=SystemCompanyCreateResponse,
    summary="Bootstrap Company",
    description="Registers a new terminal or trucking company, hashes an administrator profile, and provisions initial API Key keys."
)
def bootstrap_company(
    body: SystemCompanyCreate,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(get_current_super_admin)
):
    """
    Super Admin endpoint to bootstrap companies and their initial settings.
    """
    # 1. Verifica se a empresa já existe (tax_id ou username)
    if db.query(Company).filter((Company.tax_id == body.tax_id) | (Company.username == body.company_username)).first():
        raise HTTPException(status_code=409, detail={"code": "COMPANY_EXISTS", "message": "CNPJ ou Username da empresa já cadastrado."})

    # 2. Verifica se o username do admin já existe
    if db.query(CompanyUser).filter_by(username=body.admin_user.username).first():
        raise HTTPException(status_code=409, detail={"code": "USER_EXISTS", "message": "O username do administrador já está em uso."})

    try:
        # 3. Gera a API Key inicial
        full_key, prefix, key_hash = APIKeyManager.generate_key_pair()

        # 4. Instancia o modelo correto baseado no tipo
        CompanyModel = Terminal if body.type == "terminal" else TruckingCompany
        
        new_company = CompanyModel(
            username=body.company_username,
            name=body.name,
            tax_id=body.tax_id,
            phone=body.phone,
            email=body.email,
            api_key_hash=key_hash,
            api_key_prefix=prefix
        )
        db.add(new_company)
        db.flush() # Gera o ID da empresa para usar no CompanyUser

        # 5. Cria o usuário administrador vinculado à empresa
        new_admin = CompanyUser(
            company_id=new_company.id,
            username=body.admin_user.username,
            name=body.admin_user.name,
            password_hash=hash_secret(body.admin_user.password),
            is_admin=True,
            permissions={
                'geofence': 'read/write',
                'appointment_layouts': 'read/write',
                'company_information': 'read/write',
                'trip_layouts': 'read/write'
            }
        )
        db.add(new_admin)
        db.commit()

        # 6. Retorna os dados necessários para entregar ao cliente
        return {
            "success": True,
            "data": {
                "company_id": str(new_company.id),
                "type": new_company.type,
                "name": new_company.name,
                "admin_username": new_admin.username,
                "initial_api_key": full_key,
                "message": "Empresa e administrador criados com sucesso."
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})
    

@router.post(
    "/allowed-domains", 
    response_model=AllowedDomainResponse,
    summary="Register Allowed Domain",
    description="Registers an integration URL domain in whitelist, extracting the hostname vector."
)
def create_allowed_domain(
    payload: AllowedDomainCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_super_admin)
):
    """
    Appends domain whitelisting permissions. Validates hostname to prevent duplication.
    """
    clean_domain = extract_domain(payload.url)
    
    existing_domain = db.query(AllowedDomain).filter(
        AllowedDomain.domain == clean_domain
    ).first()
    
    if existing_domain:
        if not existing_domain.is_active:
            existing_domain.is_active = True
            db.commit()
            return {
                "success": True,
                "message": "Domínio reativado com sucesso",
                "data": {
                    "domain": clean_domain
                }
            }
            
        raise HTTPException(
            status_code=400, 
            detail={"code": "DOMAIN_EXISTS", "message": f"O domínio '{clean_domain}' já está cadastrado e ativo."}
        )

    new_allowed_domain = AllowedDomain(
        domain=clean_domain,
        is_active=payload.is_active
    )
    
    db.add(new_allowed_domain)
    db.commit()
    db.refresh(new_allowed_domain)
    
    return {
        "success": True,
        "message": "Domínio validado e cadastrado com sucesso",
        "data": {
            "id": new_allowed_domain.id,
            "domain": new_allowed_domain.domain,
            "is_active": new_allowed_domain.is_active
        }
    }


@router.delete(
    "/allowed-domains/{domain_id}", 
    response_model=AllowedDomainResponse,
    summary="Deactivate Allowed Domain",
    description="Deactivates whitelisted domain configurations and sets all associated services status to inactive."
)
def deactivate_allowed_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_super_admin)
):
    """
    Sets whitelist state for domain config and cascade disables its integration services.
    """
    domain_obj = db.query(AllowedDomain).filter(AllowedDomain.id == domain_id).first()
    
    if not domain_obj:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Domínio não encontrado."}
        )
        
    domain_obj.is_active = False
    
    # Desativa também todos os serviços relacionados a este domínio
    db.query(CompanyService).filter(CompanyService.domain_id == domain_id).update(
        {"is_active": False}, synchronize_session=False
    )
    
    db.commit()
    
    return {
        "success": True,
        "message": "Domínio desativado com sucesso",
        "data": {
            "id": domain_obj.id,
            "domain": domain_obj.domain,
            "is_active": domain_obj.is_active
        }
    }


@router.put(
    "/company-users/{user_id}/password", 
    status_code=200, 
    response_model=SimpleSuccessResponse,
    summary="Update Company User Password",
    description="Allows super admins to reset credentials passwords for company-level users directly."
)
def update_company_user_password(
    user_id: uuid.UUID,
    body: CompanyUserPasswordUpdate,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(get_current_super_admin)
):
    """
    Resets credential hash password parameters on user ID.
    """
    user = db.query(CompanyUser).filter(CompanyUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": "Usuário não encontrado."}
        )

    try:
        user.password_hash = hash_secret(body.password)
        db.commit()
        return {
            "success": True,
            "message": "Senha do usuário da empresa atualizada com sucesso."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )


@router.get(
    "/admin/appointments/logs", 
    response_model=AdminAppointmentLogsResponse,
    summary="Query Appointments Logs",
    description="Administrative search to get appointments and their detailed logs history in batch."
)
def get_admin_appointments_logs(
    company_id: uuid.UUID = Query(..., description="ID da empresa (Terminal)"),
    refs: List[str] = Query(..., description="Lista de referências de agendamentos"),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(get_current_super_admin)
):
    """
    Retrieves appointments records and aggregates historical log details. Pre-caches logs inside a single query.
    """
    if not refs:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_PAYLOAD", "message": "A lista de referências (refs) não pode estar vazia."}
        )

    appointments = db.query(Appointment).filter(
        Appointment.terminal_id == company_id,
        Appointment.ref.in_(refs)
    ).all()

    appt_map = {appt.ref: appt for appt in appointments}

    # Optimization: Batch query logs outside the loop to prevent O(N) database queries
    appt_ids = [appt.id for appt in appointments]
    logs_map = {}
    if appt_ids:
        all_logs = db.query(AppointmentLog).filter(
            AppointmentLog.appointment_id.in_(appt_ids),
            AppointmentLog.company_id == company_id
        ).order_by(AppointmentLog.created_at.desc()).all()
        for log in all_logs:
            logs_map.setdefault(log.appointment_id, []).append(log)

    result = []
    # Optimization: Batch query drivers to avoid N+1 queries
    user_tax_ids = [appt.user_tax_id for appt in appointments if appt.user_tax_id]
    drivers = db.query(Driver).filter(Driver.tax_id.in_(user_tax_ids)).all() if user_tax_ids else []
    driver_map = {d.tax_id: d for d in drivers}

    for ref in refs:
        appt = appt_map.get(ref)
        if not appt:
            result.append({
                "ref": ref,
                "found": False,
                "data": None
            })
            continue

        logs = logs_map.get(appt.id, [])

        serialized_logs = [
            {
                "id": str(log.id),
                "event": log.event,
                "message": log.message,
                "json": log.json,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]

        appt_data = {
            "id": str(appt.id),
            "terminal_id": str(appt.terminal_id),
            "ref": appt.ref,
            "layout_ref": appt.layout_ref,
            "user_tax_id": appt.user_tax_id,
            "status": appt.status,
            "summary": appt.summary,
            "vehicle_plate": appt.vehicle_plate,
            "schedule_start_time": appt.schedule_start_time.isoformat() if appt.schedule_start_time else None,
            "schedule_end_time": appt.schedule_end_time.isoformat() if appt.schedule_end_time else None,
            "schedule_start_tolerance": appt.schedule_start_tolerance,
            "schedule_end_tolerance": appt.schedule_end_tolerance,
            "custom_data": appt.custom_data,
            "created_at": appt.created_at.isoformat() if appt.created_at else None,
            "updated_at": appt.updated_at.isoformat() if appt.updated_at else None
        }

        # Query driver metadata
        driver = driver_map.get(appt.user_tax_id)
        driver_data = {
            "tax_id": driver.tax_id,
            "driver_license_number": driver.driver_license_number,
            "driver_license_category": driver.driver_license_category
        } if driver else {
            "tax_id": appt.user_tax_id,
            "driver_license_number": None,
            "driver_license_category": None
        }

        result.append({
            "ref": ref,
            "found": True,
            "data": {
                "appointment": appt_data,
                "driver": driver_data,
                "logs": serialized_logs
            }
        })

    return {"success": True, "data": result}


@router.get(
    "/admin/trips/logs", 
    response_model=AdminTripLogsResponse,
    summary="Query Trips Logs",
    description="Administrative search to get trips and their detailed logs history in batch."
)
def get_admin_trips_logs(
    company_id: uuid.UUID = Query(..., description="ID da empresa (Transportadora)"),
    refs: List[str] = Query(..., description="Lista de referências de viagens"),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(get_current_super_admin)
):
    """
    Retrieves trip records and aggregates historical log details. Pre-caches logs inside a single query.
    """
    if not refs:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_PAYLOAD", "message": "A lista de referências (refs) não pode estar vazia."}
        )

    trips = db.query(Trip).filter(
        Trip.trucking_company_id == company_id,
        Trip.ref.in_(refs)
    ).all()

    trip_map = {t.ref: t for t in trips}

    # Optimization: Batch query logs outside the loop to prevent O(N) database queries
    trip_ids = [t.id for t in trips]
    logs_map = {}
    if trip_ids:
        all_logs = db.query(TripLog).filter(
            TripLog.trip_id.in_(trip_ids),
            TripLog.company_id == company_id
        ).order_by(TripLog.created_at.desc()).all()
        for log in all_logs:
            logs_map.setdefault(log.trip_id, []).append(log)

    result = []
    # Optimization: Batch query drivers to avoid N+1 database queries
    driver_ids = [t.driver_id for t in trips if t.driver_id]
    drivers = db.query(Driver).filter(Driver.id.in_(driver_ids)).all() if driver_ids else []
    driver_map = {d.id: d for d in drivers}

    for ref in refs:
        trip_obj = trip_map.get(ref)
        if not trip_obj:
            result.append({
                "ref": ref,
                "found": False,
                "data": None
            })
            continue

        logs = logs_map.get(trip_obj.id, [])

        serialized_logs = [
            {
                "id": str(log.id),
                "event": log.event,
                "message": log.message,
                "json": log.json,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]

        trip_data = {
            "id": str(trip_obj.id),
            "trucking_company_id": str(trip_obj.trucking_company_id),
            "ref": trip_obj.ref,
            "layout_ref": trip_obj.layout_ref,
            "driver_id": str(trip_obj.driver_id) if trip_obj.driver_id else None,
            "vehicle_plate": trip_obj.vehicle_plate,
            "status": trip_obj.status,
            "summary": trip_obj.summary,
            "schedule_start_time": trip_obj.schedule_start_time.isoformat() if trip_obj.schedule_start_time else None,
            "schedule_end_time": trip_obj.schedule_end_time.isoformat() if trip_obj.schedule_end_time else None,
            "custom_data": trip_obj.custom_data,
            "origin_street": trip_obj.origin_street,
            "origin_number": trip_obj.origin_number,
            "origin_city": trip_obj.origin_city,
            "origin_state": trip_obj.origin_state,
            "origin_country": trip_obj.origin_country,
            "origin_zip": trip_obj.origin_zip,
            "origin_lat": trip_obj.origin_lat,
            "origin_lng": trip_obj.origin_lng,
            "destiny_street": trip_obj.destiny_street,
            "destiny_number": trip_obj.destiny_number,
            "destiny_city": trip_obj.destiny_city,
            "destiny_state": trip_obj.destiny_state,
            "destiny_country": trip_obj.destiny_country,
            "destiny_zip": trip_obj.destiny_zip,
            "destiny_lat": trip_obj.destiny_lat,
            "destiny_lng": trip_obj.destiny_lng,
            "from_location": trip_obj.from_location,
            "to_location": trip_obj.to_location,
            "created_at": trip_obj.created_at.isoformat() if trip_obj.created_at else None,
            "updated_at": trip_obj.updated_at.isoformat() if trip_obj.updated_at else None
        }

        # Query driver metadata
        driver = driver_map.get(trip_obj.driver_id) if trip_obj.driver_id else None
        driver_data = {
            "tax_id": driver.tax_id,
            "driver_license_number": driver.driver_license_number,
            "driver_license_category": driver.driver_license_category
        } if driver else None

        result.append({
            "ref": ref,
            "found": True,
            "data": {
                "trip": trip_data,
                "driver": driver_data,
                "logs": serialized_logs
            }
        })

    return {"success": True, "data": result}