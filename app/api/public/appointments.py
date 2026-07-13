import json
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

from app.core.database import get_db
from app.core.dependencies import get_company_from_api_key
from app.models import Company, Driver, Appointment, AppointmentLog, AppointmentLayout

router = APIRouter()

# --- HELPER LOGS ---
def create_appointment_log(db: Session, company_id: Any, appointment_id: Any, event: str, message: str, data: dict):
    """
    Utility function to log changes and events for an appointment in the database.
    Serializes date/time elements dynamically to JSON format.
    """
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
        
    serialized_data = json.loads(json.dumps(data, default=json_serializer))
    
    log = AppointmentLog(
        company_id=company_id,
        appointment_id=appointment_id,
        event=event,
        message=message,
        json=serialized_data
    )
    db.add(log)


# --- SCHEMAS (Pydantic Request/Response) ---

class DriverSchema(BaseModel):
    """Schema representing driver profile details."""
    tax_id: str = Field(..., description="CPF ou CNPJ do motorista (Apenas números)")
    driver_license_number: str = Field(..., description="Número da CNH")
    license_category: str = Field(..., description="Categoria da CNH (ex: E)")

class AppointmentBaseSchema(BaseModel):
    """Schema representing core parameters of an appointment."""
    ref: str = Field(..., description="ID ou referência única externa do agendamento")
    layout_ref: str = Field(..., description="Referência do layout de agendamento a ser aplicado")
    schedule_start_time: Optional[datetime] = Field(None, description="Data/hora de início agendada")
    schedule_end_time: Optional[datetime] = Field(None, description="Data/hora de término agendada")
    schedule_start_tolerance: int = Field(0, description="Tolerância de início em minutos")
    schedule_end_tolerance: int = Field(0, description="Tolerância de término em minutos")
    summary: Optional[str] = Field(None, description="Resumo ou observações do agendamento")
    vehicle_plate: Optional[str] = Field(None, description="Placa do veículo associado")
    custom_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadados dinâmicos adicionais")

    @model_validator(mode='after')
    def check_dates(self) -> 'AppointmentBaseSchema':
        """Validates that schedule end time is strictly after the start time."""
        if self.schedule_start_time and self.schedule_end_time:
            if self.schedule_end_time <= self.schedule_start_time:
                raise ValueError("O horário de término deve ser após o início.")
        return self

class CreateAppointmentPayload(BaseModel):
    """Payload to create an appointment containing driver and appointment details."""
    driver: DriverSchema
    appointment: AppointmentBaseSchema

class UpdateAppointmentPayload(BaseModel):
    """Payload to partially update an existing appointment."""
    ref: str = Field(..., description="Referência única do agendamento que será atualizado")
    appointment: Dict[str, Any] = Field(..., description="Objeto contendo apenas os campos a atualizar")

# Response Schemas

class CreateAppointmentsResponseData(BaseModel):
    created_refs: List[str]
    status: str

class CreateAppointmentsResponse(BaseModel):
    success: bool = True
    data: CreateAppointmentsResponseData

class UpdateAppointmentsResponseData(BaseModel):
    updated_refs: List[str]
    status: str

class UpdateAppointmentsResponse(BaseModel):
    success: bool = True
    data: UpdateAppointmentsResponseData

class DeleteAppointmentsResponseData(BaseModel):
    deleted_count: int
    status: str

class DeleteAppointmentsResponse(BaseModel):
    success: bool = True
    data: DeleteAppointmentsResponseData

class AppointmentLogResponseItem(BaseModel):
    """Item schema representing a log trace of an appointment."""
    id: str
    event: str
    message: str
    json_data: Optional[Dict[str, Any]] = Field(None, validation_alias="json", serialization_alias="json")
    created_at: Optional[str] = None

class AppointmentDataResponseItem(BaseModel):
    """Item schema representing deep details of an appointment."""
    id: str
    terminal_id: str
    ref: str
    layout_ref: Optional[str] = None
    user_tax_id: str
    status: str
    summary: Optional[str] = None
    vehicle_plate: Optional[str] = None
    schedule_start_time: Optional[str] = None
    schedule_end_time: Optional[str] = None
    schedule_start_tolerance: int
    schedule_end_tolerance: int
    custom_data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class DriverLogResponseItem(BaseModel):
    """Schema representing driver profile details associated with the log search."""
    tax_id: str
    driver_license_number: Optional[str] = None
    driver_license_category: Optional[str] = None

class AppointmentLogDataContent(BaseModel):
    """Nested container holding appointment details, driver profile, and historical logs."""
    appointment: AppointmentDataResponseItem
    driver: Optional[DriverLogResponseItem] = None
    logs: List[AppointmentLogResponseItem]

class AppointmentLogQueryResult(BaseModel):
    """Item schema mapping query response including availability state and logs."""
    ref: str
    found: bool
    data: Optional[AppointmentLogDataContent] = None

class AppointmentLogsResponse(BaseModel):
    success: bool = True
    data: List[AppointmentLogQueryResult]


# --- ROTAS ---

@router.post(
    "/appointments", 
    status_code=201, 
    response_model=CreateAppointmentsResponse,
    summary="Criar Agendamento(s)",
    description="Registra um único agendamento ou uma lista de agendamentos juntamente com os perfis dos motoristas associados. Aceita tanto um objeto individual quanto um array (lote) de objetos. Realiza validações Fail-Fast."
)
def create_appointments(
    payload: Union[CreateAppointmentPayload, List[CreateAppointmentPayload]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Processes and registers new appointments (single or batch).
    Validates layout references and references uniqueness before database insertion.
    """
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "A lista de agendamentos enviada está vazia.",
                "suggestion": "Envie um array JSON contendo pelo menos um objeto com 'driver' e 'appointment'."
            }
        )

    # --- FAIL-FAST: APPOINTMENT LAYOUTS ---
    incoming_layout_refs = {
        item.appointment.layout_ref 
        for item in items 
        if item.appointment.layout_ref
    }

    if incoming_layout_refs:
        existing_layouts = db.query(AppointmentLayout.ref).filter(
            AppointmentLayout.terminal_id == company.id,
            AppointmentLayout.ref.in_(incoming_layout_refs)
        ).all()
        
        existing_layout_refs = {e[0] for e in existing_layouts}
        missing_layouts = incoming_layout_refs - existing_layout_refs
        
        if missing_layouts:
            raise HTTPException(
                status_code=400, 
                detail={
                    "code": "INVALID_LAYOUT_REF",
                    "message": "Um ou mais layouts informados não existem no seu terminal.",
                    "missing_layouts": list(missing_layouts)
                }
            )

    # --- FAIL-FAST: DUPLICATE REFERENCE KEYS ---
    incoming_refs = [item.appointment.ref for item in items]
    existing = db.query(Appointment.ref).filter(
        Appointment.terminal_id == company.id,
        Appointment.ref.in_(incoming_refs)
    ).all()

    if existing:
        existing_refs = [e[0] for e in existing]
        raise HTTPException(
            status_code=409, 
            detail={
                "code": "DUPLICATE_KEY",
                "message": "Um ou mais agendamentos já existem com as referências enviadas.",
                "suggestion": "Verifique se você já não enviou estes agendamentos antes. Para alterá-los, utilize a rota PUT /appointments.",
                "conflicting_refs": existing_refs
            }
        )

    # --- OPTIMIZATION: BATCH DRIVERS QUERY ---
    incoming_driver_tax_ids = {item.driver.tax_id for item in items}
    existing_drivers = db.query(Driver).filter(Driver.tax_id.in_(incoming_driver_tax_ids)).all()
    driver_map = {d.tax_id: d for d in existing_drivers}

    created_refs = []

    for item in items:
        # Process and retrieve Driver using pre-queried dictionary cache
        driver = driver_map.get(item.driver.tax_id)
        if not driver:
            driver = Driver(
                tax_id=item.driver.tax_id,
                driver_license_number=item.driver.driver_license_number,
                driver_license_category=item.driver.license_category,
                validated_by=company.id
            )
            db.add(driver)
            db.flush() 
            driver_map[item.driver.tax_id] = driver
        else:
            if item.driver.driver_license_number and driver.driver_license_number != item.driver.driver_license_number:
                driver.driver_license_number = item.driver.driver_license_number
            else:
                driver.updated_at = datetime.utcnow()
            driver.validated_by = company.id

        # Process and link Appointment
        appt = Appointment(
            terminal_id=company.id,
            user_tax_id=driver.tax_id,
            ref=item.appointment.ref,
            layout_ref=item.appointment.layout_ref,
            schedule_start_tolerance=item.appointment.schedule_start_tolerance,
            schedule_end_tolerance=item.appointment.schedule_end_tolerance,
            schedule_start_time=item.appointment.schedule_start_time, 
            schedule_end_time=item.appointment.schedule_end_time,
            summary=item.appointment.summary,
            vehicle_plate=item.appointment.vehicle_plate,
            custom_data=item.appointment.custom_data,
        )
        db.add(appt)
        db.flush()

        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=appt.id,
            event="created",
            message="Agendamento criado via API.",
            data={
                "ref": appt.ref,
                "vehicle_plate": appt.vehicle_plate,
                "schedule_start_time": appt.schedule_start_time.isoformat() if appt.schedule_start_time else None,
                "schedule_end_time": appt.schedule_end_time.isoformat() if appt.schedule_end_time else None,
            }
        )
        created_refs.append(appt.ref)

    try:
        db.commit()
        return {"success": True, "data": {"created_refs": created_refs, "status": "created"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Erro inesperado ao salvar os dados no banco.",
                "suggestion": "Contate o suporte técnico enviando o horário da requisição e os dados que tentou enviar.",
                "error_details": str(e)
            }
        )


@router.put(
    "/appointments",
    response_model=UpdateAppointmentsResponse,
    summary="Atualizar Agendamento(s)",
    description="Atualiza parcialmente detalhes de agendamentos existentes mapeados por suas referências externas exclusivas. Aceita tanto um objeto individual quanto um array (lote) de objetos. Apenas campos não protegidos podem ser atualizados."
)
def update_appointments(
    payload: Union[UpdateAppointmentPayload, List[UpdateAppointmentPayload]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Partially updates metadata details of existing appointments (single or batch).
    Performs validation ensuring all supplied references already exist in company context.
    """
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "Nenhum dado enviado para atualização.",
                "suggestion": "Envie um array JSON contendo os objetos a serem atualizados."
            }
        )

    incoming_refs = [item.ref for item in items]
    
    appts = db.query(Appointment).filter(
        Appointment.terminal_id == company.id,
        Appointment.ref.in_(incoming_refs)
    ).all()
    
    appt_map = {appt.ref: appt for appt in appts}
    protected_fields = {"id", "terminal_id", "ref", "user_tax_id"}
    updated_refs = []
    not_found_refs = []

    for item in items:
        if item.ref not in appt_map:
            not_found_refs.append(item.ref)
            continue
        
        appt = appt_map[item.ref]
        
        for key, value in item.appointment.items():
            if key not in protected_fields and hasattr(appt, key):
                setattr(appt, key, value)
        
        db.flush()
        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=appt.id,
            event="updated",
            message="Agendamento atualizado via API.",
            data=item.appointment
        )
        
        updated_refs.append(item.ref)

    if not_found_refs:
        db.rollback() 
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "REFS_NOT_FOUND",
                "message": "Um ou mais agendamentos não foram encontrados no banco.",
                "suggestion": "Verifique se as referências (ref) enviadas estão corretas e se os agendamentos já foram criados previamente via POST.",
                "missing_refs": not_found_refs
            }
        )

    try:
        db.commit()
        return {"success": True, "data": {"updated_refs": updated_refs, "status": "updated"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": "Erro ao atualizar agendamentos.", "error_details": str(e)}
        )


@router.delete(
    "/appointments",
    response_model=DeleteAppointmentsResponse,
    summary="Excluir/Cancelar Agendamento(s)",
    description="Marca agendamentos existentes como DELETED (cancelados) no banco de dados. Aceita tanto uma única string de referência quanto um array (lote) de strings."
)
def delete_appointments(
    payload: Union[str, List[str]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Cancels or soft-deletes appointments (single or batch). Sets status to DELETED and writes log records.
    """
    refs = payload if isinstance(payload, list) else [payload]
    if not refs:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "Lista de referências vazia.",
                "suggestion": "Envie um array de strings contendo as referências (ref) dos agendamentos a deletar."
            }
        )

    appts = db.query(Appointment).filter(
        Appointment.terminal_id == company.id,
        Appointment.ref.in_(refs)
    ).all()
    
    if not appts:
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "NOT_FOUND",
                "message": "Nenhum agendamento encontrado para as referências informadas.",
                "suggestion": "Garanta que as referências enviadas pertencem ao seu terminal e estão corretas."
            }
        )

    for appt in appts:
        appt.status = "DELETED"
        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=appt.id,
            event="deleted",
            message="Agendamento deletado/cancelado.",
            data={"ref": appt.ref, "status": "DELETED"}
        )

    db.commit()
    return {"success": True, "data": {"deleted_count": len(appts), "status": "deleted"}}


@router.get(
    "/appointments/logs",
    response_model=AppointmentLogsResponse,
    summary="Consultar Logs e Detalhes dos Agendamentos",
    description="Consulta logs históricos detalhados de execução e parâmetros de dados de agendamentos em lote usando suas referências."
)
def get_appointments_logs(
    refs: List[str] = Query(..., description="Lista de referências de agendamentos"),
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Fetches appointment database information along with their execution log traces.
    """
    if not refs:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_PAYLOAD", "message": "A lista de referências (refs) não pode estar vazia."}
        )

    # Fetch corresponding appointments in batch
    appointments = db.query(Appointment).filter(
        Appointment.terminal_id == company.id,
        Appointment.ref.in_(refs)
    ).all()

    appt_map = {appt.ref: appt for appt in appointments}

    # Optimization: Batch query drivers to prevent N+1 queries
    user_tax_ids = [appt.user_tax_id for appt in appointments if appt.user_tax_id]
    drivers = db.query(Driver).filter(Driver.tax_id.in_(user_tax_ids)).all() if user_tax_ids else []
    driver_map = {d.tax_id: d for d in drivers}

    result = []
    for ref in refs:
        appt = appt_map.get(ref)
        if not appt:
            result.append({
                "ref": ref,
                "found": False,
                "data": None
            })
            continue

        # Fetch logs for each matching appointment
        logs = db.query(AppointmentLog).filter(
            AppointmentLog.appointment_id == appt.id,
            AppointmentLog.company_id == company.id
        ).order_by(AppointmentLog.created_at.desc()).all()

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
