import logging
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

from app.core.database import get_db
from app.core.dependencies import get_company_from_api_key
from app.core.sqids import encode_id, decode_id
from app.models import Company, Driver, Appointment, AppointmentLog, AppointmentLayout, AppointmentEvent, SafetyIntegration

logger = logging.getLogger(__name__)
router = APIRouter()

# --- HELPER LOGS ---
def create_appointment_log(db: Session, company_id: Any, appointment_id: Any, event: AppointmentEvent):
    """
    Utility function to log events for an appointment in the database.
    Columns message and json are kept in schema but not populated.
    """
    log = AppointmentLog(
        company_id=company_id,
        appointment_id=appointment_id,
        event=event,
    )
    db.add(log)


# --- SCHEMAS (Pydantic Request/Response) ---

class DriverSchema(BaseModel):
    """Schema representing driver profile details."""
    tax_id: str = Field(..., description="CPF ou CNPJ do motorista (Apenas números)")
    driver_license_number: str = Field(..., description="Número da CNH")
    license_category: str = Field(..., description="Categoria da CNH (ex: E)")
    safety_integration: Optional[bool] = Field(None, description="Informa se o motorista tem integração de segurança ativa")
    integration_expires_at: Optional[datetime] = Field(None, description="Data de expiração da integração (Obrigatório se safety_integration = true)")
    integration_watched_at: Optional[datetime] = Field(None, description="Data de realização da integração (Opcional)")

    @model_validator(mode='after')
    def validate_safety_integration(self):
        if self.safety_integration is True and not self.integration_expires_at:
            raise ValueError("integration_expires_at is required when safety_integration is true")
        return self

class AppointmentBaseSchema(BaseModel):
    """Schema representing core parameters of an appointment."""
    ref: str = Field(..., description="ID ou referência única externa do agendamento")
    layout_ref: str = Field(..., description="Referência do layout de agendamento a ser aplicado")
    status: Optional[str] = None
    summary: Optional[str] = None
    license_plate: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    start_tolerance: int = Field(0, description="Tolerância de início em minutos")
    end_tolerance: int = Field(0, description="Tolerância de término em minutos")
    custom_data: Optional[Dict[str, Any]] = None

class CreateAppointmentPayload(BaseModel):
    """Schema for creating appointment along with driver details."""
    driver: DriverSchema
    appointment: AppointmentBaseSchema

class UpdateAppointmentData(BaseModel):
    """Schema for fields that can be updated on an appointment."""
    class Config:
        extra = "allow"

class UpdateAppointmentPayload(BaseModel):
    """Schema representing an update operation on an appointment."""
    ref: str = Field(..., description="Referência do agendamento a ser atualizado")
    appointment: Dict[str, Any]

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

class PingAppointmentsPayload(BaseModel):
    appointment_refs: Optional[List[str]] = Field(None, description="Lista de referências dos agendamentos a pingar")
    appointment_ids: Optional[List[str]] = Field(None, description="Lista de IDs hash dos agendamentos a pingar")

class PingAppointmentsResponseData(BaseModel):
    pinged_count: int
    pinged_refs: List[str]
    pinged_at: str

class PingAppointmentsResponse(BaseModel):
    success: bool = True
    data: PingAppointmentsResponseData

class AppointmentLogResponseItem(BaseModel):
    """Item schema representing a log trace of an appointment."""
    id: str
    event: str
    message: Optional[str] = None
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
    license_plate: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    start_tolerance: int
    end_tolerance: int
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
            start_tolerance=item.appointment.start_tolerance,
            end_tolerance=item.appointment.end_tolerance,
            window_start=item.appointment.window_start, 
            window_end=item.appointment.window_end,
            summary=item.appointment.summary,
            license_plate=item.appointment.license_plate,
            custom_data=item.appointment.custom_data,
        )
        db.add(appt)
        db.flush()

        # Process Safety Integration
        if item.driver.safety_integration is not None:
            si = db.query(SafetyIntegration).filter(
                SafetyIntegration.tax_id == driver.tax_id,
                SafetyIntegration.company_id == company.id
            ).first()
            if item.driver.safety_integration is True:
                if not si:
                    si = SafetyIntegration(
                        tax_id=driver.tax_id,
                        company_id=company.id,
                        watched_at=item.driver.integration_watched_at,
                        expires_at=item.driver.integration_expires_at
                    )
                    db.add(si)
                else:
                    if item.driver.integration_watched_at:
                        si.watched_at = item.driver.integration_watched_at
                    si.expires_at = item.driver.integration_expires_at
            else:
                if si:
                    db.delete(si)
        db.flush()

        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=appt.id,
            event=AppointmentEvent.CREATED,
        )
        created_refs.append(appt.ref)

    try:
        db.commit()

        # --- PUSH NOTIFICATIONS: Notifica cada motorista sobre o novo agendamento ---
        # Disparado depois do commit, de forma não-bloqueante.
        # Erros de push nunca afetam a resposta da API.
        try:
            from app.core.firebase import notify_user_by_tax_id
            # Re-query para ter acesso ao terminal name após o commit
            terminal_name = company.name or "terminal"

            for item in items:
                driver_tax_id = item.driver.tax_id
                start = item.appointment.window_start
                date_label = (
                    start.strftime("%d/%m às %H:%M")
                    if start else "em breve"
                )
                notify_user_by_tax_id(
                    db, driver_tax_id,
                    "📅 Novo agendamento",
                    f"Você tem um agendamento em {terminal_name} {date_label}.",
                    data={
                        "type": "SCHEDULED_CREATED",
                        "ref": item.appointment.ref,
                    },
                )
        except Exception as push_err:
            logger.warning(f"[push] Falha ao notificar criação de agendamento: {push_err}")

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
            event=AppointmentEvent.UPDATED,
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

        # --- PUSH NOTIFICATIONS: Notifica motoristas sobre a atualização ---
        try:
            from app.core.firebase import notify_user_by_tax_id
            terminal_name = company.name or "terminal"

            for ref in updated_refs:
                appt = appt_map.get(ref)
                if not appt or not appt.user_tax_id:
                    continue

                # Detecta se o update mudou horário ou apenas dados de exibição
                updated_fields = set(items[[i.ref for i in items].index(ref)].appointment.keys())
                time_fields = {"window_start", "window_end",
                               "start_tolerance", "end_tolerance"}

                if time_fields & updated_fields:
                    # Horário alterado
                    start = appt.window_start
                    date_label = start.strftime("%d/%m às %H:%M") if start else "em breve"
                    notify_user_by_tax_id(
                        db, appt.user_tax_id,
                        "⏰ Horário alterado",
                        f"Seu agendamento em {terminal_name} foi reagendado para {date_label}.",
                        data={"type": "SCHEDULED_UPDATE", "ref": ref, "change": "time"},
                    )
                else:
                    # Apenas dados de exibição alterados
                    notify_user_by_tax_id(
                        db, appt.user_tax_id,
                        "🔄 Dados atualizados",
                        f"Os detalhes do seu agendamento em {terminal_name} foram atualizados.",
                        data={"type": "SCHEDULED_UPDATE", "ref": ref, "change": "display"},
                    )
        except Exception as push_err:
            logger.warning(f"[push] Falha ao notificar atualização de agendamento: {push_err}")

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
        appt.is_active = False
        appt.status = "DELETED"
        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=appt.id,
            event=AppointmentEvent.DELETED,
        )

    db.commit()

    # --- PUSH NOTIFICATIONS: Notifica motoristas sobre o cancelamento ---
    try:
        from app.core.firebase import notify_user_by_tax_id
        terminal_name = company.name or "terminal"
        for appt in appts:
            if appt.user_tax_id:
                notify_user_by_tax_id(
                    db, appt.user_tax_id,
                    "❌ Agendamento cancelado",
                    f"Seu agendamento em {terminal_name} foi cancelado.",
                    data={"type": "CANCELLED", "ref": appt.ref},
                )
    except Exception as push_err:
        logger.warning(f"[push] Falha ao notificar cancelamento de agendamento: {push_err}")

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
                "id": encode_id(log.id),
                "event": log.event.value if log.event else None,
                "message": log.message,
                "json": log.json,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]

        appt_data = {
            "id": encode_id(appt.id),
            "terminal_id": encode_id(appt.terminal_id),
            "ref": appt.ref,
            "layout_ref": appt.layout_ref,
            "user_tax_id": appt.user_tax_id,
            "status": appt.status,
            "summary": appt.summary,
            "license_plate": appt.license_plate,
            "window_start": appt.window_start.isoformat() if appt.window_start else None,
            "window_end": appt.window_end.isoformat() if appt.window_end else None,
            "start_tolerance": appt.start_tolerance,
            "end_tolerance": appt.end_tolerance,
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


@router.post(
    "/appointments/ping",
    response_model=PingAppointmentsResponse,
    summary="Pingar Agendamento(s) pelo Terminal",
    description="Registra um ping do terminal indicando que o agendamento permanece ativo. Atualiza o timestamp de last_ping_at para evitar desativação por tempo limite de inatividade (2 horas)."
)
def ping_appointments(
    payload: PingAppointmentsPayload,
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Updates last_ping_at timestamp for specified appointments (by ref or ID).
    Rensews the 2-hour activity window for terminal check-ins and active operations.
    """
    if not payload.appointment_refs and not payload.appointment_ids:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_PAYLOAD", "message": "Forneça 'appointment_refs' ou 'appointment_ids' no corpo da requisição."}
        )

    filters = [Appointment.terminal_id == company.id]
    id_or_ref_filters = []
    
    if payload.appointment_refs:
        id_or_ref_filters.append(Appointment.ref.in_(payload.appointment_refs))
    
    if payload.appointment_ids:
        valid_ids = []
        for raw_id in payload.appointment_ids:
            try:
                valid_ids.append(decode_id(raw_id))
            except (ValueError, Exception):
                pass
        if valid_ids:
            id_or_ref_filters.append(Appointment.id.in_(valid_ids))

    if id_or_ref_filters:
        from sqlalchemy import or_
        filters.append(or_(*id_or_ref_filters))

    appts = db.query(Appointment).filter(*filters).all()

    if not appts:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Nenhum agendamento correspondente foi encontrado para esta empresa."}
        )

    now = datetime.now(timezone.utc)
    pinged_refs = []

    for appt in appts:
        appt.last_ping_at = now
        appt.updated_at = now
        ref_label = appt.ref or encode_id(appt.id)
        pinged_refs.append(ref_label)

        db.add(AppointmentLog(
            company_id=company.id,
            appointment_id=appt.id,
            event=AppointmentEvent.TERMINAL_PING,
        ))

    db.commit()

    return {
        "success": True,
        "data": {
            "pinged_count": len(pinged_refs),
            "pinged_refs": pinged_refs,
            "pinged_at": now.isoformat()
        }
    }


class DriverSafetyIntegrationPayload(BaseModel):
    tax_id: str = Field(..., description="CPF do motorista (Apenas números)")
    active: bool = Field(..., description="Se a integração de segurança está ativa")
    expires_at: Optional[datetime] = Field(None, description="Data de expiração da integração. Obrigatória se active for true.")
    watched_at: Optional[datetime] = Field(None, description="Data em que a integração foi realizada.")

    @model_validator(mode='after')
    def validate_safety_integration(self):
        if self.active is True and not self.expires_at:
            raise ValueError("expires_at is required when active is true")
        return self

@router.post(
    "/drivers/safety-integration",
    status_code=200,
    summary="Atualizar Integração de Segurança",
    description="Permite enviar diretamente o status de integração de segurança de um motorista para a empresa (terminal)."
)
def update_driver_safety_integration(
    payload: Union[DriverSafetyIntegrationPayload, List[DriverSafetyIntegrationPayload]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    items = payload if isinstance(payload, list) else [payload]
    
    for item in items:
        si = db.query(SafetyIntegration).filter(
            SafetyIntegration.tax_id == item.tax_id,
            SafetyIntegration.company_id == company.id
        ).first()

        if item.active is True:
            if not si:
                si = SafetyIntegration(
                    tax_id=item.tax_id,
                    company_id=company.id,
                    watched_at=item.watched_at,
                    expires_at=item.expires_at
                )
                db.add(si)
            else:
                if item.watched_at:
                    si.watched_at = item.watched_at
                si.expires_at = item.expires_at
        else:
            if si:
                db.delete(si)
        
        db.flush()

    try:
        db.commit()
        return {"success": True, "message": "Status de integração atualizado com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Erro ao atualizar integração.",
                "error_details": str(e)
            }
        )
