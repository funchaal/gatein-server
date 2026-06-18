from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field
from app.models import AppointmentLayout
from pydantic import model_validator

from app.core.database import get_db
from app.core.dependencies import get_company_from_api_key
from app.models import Company, Driver, Appointment

router = APIRouter()

# --- SCHEMAS (Pydantic) ---

class DriverSchema(BaseModel):
    tax_id: str = Field(..., description="CPF ou CNPJ do motorista (Apenas números)")
    license_number: Optional[str] = Field(None, description="Número da CNH")
    license_category: Optional[str] = Field(None, description="Categoria da CNH (ex: E)")

class AppointmentBaseSchema(BaseModel):
    # 1. Defina os campos primeiro
    ref: str = Field(..., description="ID ou referência única...")
    layout_ref: Optional[str] = Field(None)
    operation_type: str = Field(...)
    schedule_start_time: Optional[datetime] = None
    schedule_end_time: Optional[datetime] = None
    schedule_start_tolerance_min: int = Field(0)
    schedule_end_tolerance_min: int = Field(0)
    summary: Optional[str] = None
    vehicle_plate: Optional[str] = Field(None)
    custom_data: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # 2. O validador vem depois (precisa do cls)
    @model_validator(mode='after')
    def check_dates(self) -> 'AppointmentBaseSchema':
        if self.schedule_start_time and self.schedule_end_time:
            if self.schedule_end_time <= self.schedule_start_time:
                raise ValueError("O horário de término deve ser após o início.")
        return self


class CreateAppointmentPayload(BaseModel):
    driver: DriverSchema
    appointment: AppointmentBaseSchema

class UpdateAppointmentPayload(BaseModel):
    ref: str = Field(..., description="Referência do agendamento que será atualizado")
    # Campos opcionais para permitir atualização parcial
    appointment: Dict[str, Any] = Field(..., description="Objeto contendo apenas os campos a atualizar")

# --- ROTAS ---

@router.post("/appointments", status_code=201)
def create_appointments(
    items: List[CreateAppointmentPayload],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    # ... (validação de EMPTY_PAYLOAD e DUPLICATE_KEY continuam iguais) ...

    # --- NOVA VALIDAÇÃO FAIL-FAST: APPOINTMENT LAYOUTS ---
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
    if not items:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "A lista de agendamentos enviada está vazia.",
                "suggestion": "Envie um array JSON contendo pelo menos um objeto com 'driver' e 'appointment'."
            }
        )

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

    created_refs = []

    for item in items:
        # Processamento do Driver
        driver = db.query(Driver).filter_by(tax_id=item.driver.tax_id).first()
        if not driver:
            driver = Driver(
                tax_id=item.driver.tax_id,
                driver_license_number=item.driver.license_number,
                driver_license_category=item.driver.license_category,
                validated_by=company.id
            )
            db.add(driver)
            db.flush() 
        else:
            if item.driver.license_number and driver.driver_license_number != item.driver.license_number:
                driver.driver_license_number = item.driver.license_number
            else:
                driver.updated_at = datetime.utcnow()
            driver.validated_by = company.id

        # Processamento do Agendamento
        appt = Appointment(
            terminal_id=company.id,
            user_tax_id=driver.tax_id,
            ref=item.appointment.ref,
            layout_ref=item.appointment.layout_ref,
            schedule_start_tolerance_min=item.appointment.schedule_start_tolerance_min,
            schedule_end_tolerance_min=item.appointment.schedule_end_tolerance_min,
            operation_type=item.appointment.operation_type,
            schedule_start_time=item.appointment.schedule_start_time, 
            schedule_end_time=item.appointment.schedule_end_time,
            summary=item.appointment.summary,
            vehicle_plate=item.appointment.vehicle_plate,
            custom_data=item.appointment.custom_data,
        )
        db.add(appt)
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


@router.put("/appointments")
def update_appointments(
    items: List[UpdateAppointmentPayload],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
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
        
        updated_refs.append(item.ref)

    if not_found_refs:
        # Fazer rollback caso a regra de negócio exija que ALL tenham que existir
        # Se puder ignorar os que não existem, remova o rollback e o raise
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
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.delete("/appointments")
def delete_appointments(
    refs: List[str],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    if not refs:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "Lista de referências vazia.",
                "suggestion": "Envie um array de strings contendo as referências (ref) dos agendamentos a deletar."
            }
        )

    affected_rows = db.query(Appointment).filter(
        Appointment.terminal_id == company.id,
        Appointment.ref.in_(refs)
    ).update({"status": "DELETED"}, synchronize_session=False)
    
    if not affected_rows:
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "NOT_FOUND",
                "message": "Nenhum agendamento encontrado para as referências informadas.",
                "suggestion": "Garanta que as referências enviadas pertencem ao seu terminal e estão corretas."
            }
        )

    db.commit()
    return {"success": True, "data": {"deleted_count": affected_rows, "status": "deleted"}}