import json
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_company_from_api_key
from app.models import Company, Appointment, Ticket, TicketLayout, AppointmentLog

router = APIRouter()


# --- HELPER LOGS ---
def create_appointment_log(db: Session, company_id: Any, appointment_id: Any, event: str, message: str, data: dict):
    """
    Utility function to log ticket-related changes on the parent appointment.
    Serializes datetime objects to ISO format for JSON storage.
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


# --- SCHEMAS ---

class TicketContentSchema(BaseModel):
    """Free-form key-value content object for ticket data."""
    pass

    class Config:
        extra = "allow"

class CreateTicketPayload(BaseModel):
    """Payload to create a single ticket linked to an appointment reference."""
    appointment_ref: str = Field(..., description="Referência (ref) do agendamento ao qual o ticket pertence")
    layout_ref: str = Field(..., description="Referência do layout de ticket a ser usado na renderização")
    content: Dict[str, Any] = Field(default_factory=dict, description="Dados chave-valor do ticket, renderizados conforme o layout")

class UpdateTicketPayload(BaseModel):
    """Payload to update fields of an existing ticket by its ID."""
    ticket_id: str = Field(..., description="UUID do ticket a ser atualizado")
    content: Optional[Dict[str, Any]] = Field(None, description="Novos dados do conteúdo do ticket")
    layout_ref: Optional[str] = Field(None, description="Nova referência de layout (se necessário trocar)")

# Response schemas

class TicketResponseItem(BaseModel):
    id: str
    appointment_id: str
    appointment_ref: str
    terminal_id: str
    layout_ref: Optional[str] = None
    content: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class CreateTicketsResponseData(BaseModel):
    created_ids: List[str]
    status: str

class CreateTicketsResponse(BaseModel):
    success: bool = True
    data: CreateTicketsResponseData

class UpdateTicketsResponseData(BaseModel):
    updated_ids: List[str]
    status: str

class UpdateTicketsResponse(BaseModel):
    success: bool = True
    data: UpdateTicketsResponseData

class DeleteTicketsResponseData(BaseModel):
    deleted_count: int
    status: str

class DeleteTicketsResponse(BaseModel):
    success: bool = True
    data: DeleteTicketsResponseData

class TicketLogsResponseItem(BaseModel):
    ref: str
    found: bool
    data: Optional[List[TicketResponseItem]] = None

class TicketLogsResponse(BaseModel):
    success: bool = True
    data: List[TicketLogsResponseItem]


# --- ROTAS ---

@router.post(
    "/tickets",
    status_code=201,
    response_model=CreateTicketsResponse,
    summary="Criar Ticket(s)",
    description=(
        "Cria um ou mais tickets digitais vinculados a agendamentos existentes. "
        "Aceita um único objeto ou um array (lote) de objetos. "
        "Valida a existência do layout de ticket e do agendamento antes de criar."
    )
)
def create_tickets(
    payload: Union[CreateTicketPayload, List[CreateTicketPayload]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Creates one or more digital tickets linked to existing appointments.
    Validates layout references and appointment existence before insertion.
    """
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "A lista de tickets enviada está vazia.",
                "suggestion": "Envie um array JSON com pelo menos um objeto contendo 'appointment_ref', 'layout_ref' e 'content'."
            }
        )

    # --- FAIL-FAST: TICKET LAYOUTS ---
    incoming_layout_refs = {item.layout_ref for item in items if item.layout_ref}
    if incoming_layout_refs:
        existing_layouts = db.query(TicketLayout.ref).filter(
            TicketLayout.terminal_id == company.id,
            TicketLayout.ref.in_(incoming_layout_refs)
        ).all()
        existing_layout_refs = {e[0] for e in existing_layouts}
        missing = incoming_layout_refs - existing_layout_refs
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_LAYOUT_REF",
                    "message": "Um ou mais layouts de ticket informados não existem no seu terminal.",
                    "missing_layouts": list(missing)
                }
            )

    # --- BATCH APPOINTMENTS LOOKUP ---
    incoming_refs = [item.appointment_ref for item in items]
    appointments = db.query(Appointment).filter(
        Appointment.terminal_id == company.id,
        Appointment.ref.in_(incoming_refs)
    ).all()
    appt_map = {a.ref: a for a in appointments}

    not_found = [ref for ref in incoming_refs if ref not in appt_map]
    if not_found:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "APPOINTMENT_NOT_FOUND",
                "message": "Um ou mais agendamentos referenciados não foram encontrados.",
                "missing_refs": not_found
            }
        )

    created_ids = []
    for item in items:
        appt = appt_map[item.appointment_ref]
        ticket = Ticket(
            appointment_id=appt.id,
            appointment_ref=item.appointment_ref,
            terminal_id=company.id,
            layout_ref=item.layout_ref,
            content=item.content
        )
        db.add(ticket)
        db.flush()

        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=appt.id,
            event="ticket_created",
            message="Ticket criado via API.",
            data={"layout_ref": item.layout_ref, "appointment_ref": item.appointment_ref}
        )
        created_ids.append(str(ticket.id))

    try:
        db.commit()
        return {"success": True, "data": {"created_ids": created_ids, "status": "created"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Erro inesperado ao salvar os tickets.",
                "error_details": str(e)
            }
        )


@router.put(
    "/tickets",
    response_model=UpdateTicketsResponse,
    summary="Atualizar Ticket(s)",
    description=(
        "Atualiza o conteúdo e/ou layout de um ou mais tickets existentes, identificados por UUID. "
        "Aceita um único objeto ou um array (lote) de objetos."
    )
)
def update_tickets(
    payload: Union[UpdateTicketPayload, List[UpdateTicketPayload]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Partially updates content or layout_ref of existing tickets by their UUIDs.
    """
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "Nenhum dado de atualização enviado.",
                "suggestion": "Envie um array JSON com os objetos a serem atualizados."
            }
        )

    ticket_ids = [item.ticket_id for item in items]
    tickets = db.query(Ticket).filter(
        Ticket.terminal_id == company.id,
        Ticket.id.in_(ticket_ids)
    ).all()
    ticket_map = {str(t.id): t for t in tickets}

    not_found = [tid for tid in ticket_ids if tid not in ticket_map]
    if not_found:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TICKETS_NOT_FOUND",
                "message": "Um ou mais tickets não foram encontrados.",
                "missing_ids": not_found
            }
        )

    updated_ids = []
    for item in items:
        ticket = ticket_map[item.ticket_id]
        if item.content is not None:
            ticket.content = item.content
        if item.layout_ref is not None:
            ticket.layout_ref = item.layout_ref

        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=ticket.appointment_id,
            event="ticket_updated",
            message="Ticket atualizado via API.",
            data={"ticket_id": item.ticket_id}
        )
        updated_ids.append(item.ticket_id)

    try:
        db.commit()
        return {"success": True, "data": {"updated_ids": updated_ids, "status": "updated"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": "Erro ao atualizar tickets.", "error_details": str(e)}
        )


@router.delete(
    "/tickets",
    response_model=DeleteTicketsResponse,
    summary="Excluir Ticket(s)",
    description=(
        "Remove permanentemente um ou mais tickets pelo seu UUID. "
        "Aceita uma única string de UUID ou um array (lote) de strings."
    )
)
def delete_tickets(
    payload: Union[str, List[str]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Hard-deletes tickets by their UUID (single or batch).
    """
    ticket_ids = payload if isinstance(payload, list) else [payload]
    if not ticket_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "Lista de IDs de tickets vazia.",
                "suggestion": "Envie um array de strings com os UUIDs dos tickets a deletar."
            }
        )

    tickets = db.query(Ticket).filter(
        Ticket.terminal_id == company.id,
        Ticket.id.in_(ticket_ids)
    ).all()

    if not tickets:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "message": "Nenhum ticket encontrado para os IDs informados.",
                "suggestion": "Verifique se os UUIDs enviados pertencem ao seu terminal."
            }
        )

    for ticket in tickets:
        create_appointment_log(
            db=db,
            company_id=company.id,
            appointment_id=ticket.appointment_id,
            event="ticket_deleted",
            message="Ticket removido via API.",
            data={"ticket_id": str(ticket.id), "appointment_ref": ticket.appointment_ref}
        )
        ticket.is_active = False

    db.commit()
    return {"success": True, "data": {"deleted_count": len(tickets), "status": "deleted"}}


@router.get(
    "/tickets",
    response_model=TicketLogsResponse,
    summary="Consultar Tickets por Referência de Agendamento",
    description=(
        "Retorna todos os tickets vinculados a um ou mais agendamentos, identificados pela referência (ref) do agendamento. "
        "Repita o parâmetro 'appointment_refs' para consultar em lote."
    )
)
def get_tickets(
    appointment_refs: List[str] = Query(..., description="Referências dos agendamentos cujos tickets serão retornados"),
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Fetches tickets for one or more appointment references belonging to the authenticated terminal.
    """
    if not appointment_refs:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_PAYLOAD", "message": "A lista de referências não pode estar vazia."}
        )

    tickets = db.query(Ticket).filter(
        Ticket.terminal_id == company.id,
        Ticket.appointment_ref.in_(appointment_refs)
    ).all()

    # Group tickets by appointment_ref
    tickets_by_ref: Dict[str, List] = {ref: [] for ref in appointment_refs}
    for ticket in tickets:
        if ticket.appointment_ref in tickets_by_ref:
            tickets_by_ref[ticket.appointment_ref].append({
                "id": str(ticket.id),
                "appointment_id": str(ticket.appointment_id),
                "appointment_ref": ticket.appointment_ref,
                "terminal_id": str(ticket.terminal_id),
                "layout_ref": ticket.layout_ref,
                "content": ticket.content,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            })

    result = []
    for ref in appointment_refs:
        found_tickets = tickets_by_ref.get(ref, [])
        result.append({
            "ref": ref,
            "found": len(found_tickets) > 0,
            "data": found_tickets if found_tickets else None
        })

    return {"success": True, "data": result}
