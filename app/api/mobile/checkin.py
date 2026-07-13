import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Appointment, Ticket, TicketLayout
from app.schemas.checkin import TicketItem
from app.api.sockets.connection import sio
from app.api.sockets.handlers.checkin import active_terminals

router = APIRouter()

@router.post(
    "/{terminal_id}", 
    response_model=List[TicketItem],
    summary="Process Remote Check-in",
    description="Initiates check-in sequence with physical terminal hardware via sockets. Validates ticket layout integrity and registers checked-in tickets."
)
async def process_checkin(
    terminal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers remote check-in for the driver user at the specified terminal.
    Communicates via Socket.IO, validates layout constraints, and marks appointments as CHECKED_IN.
    """
    terminal_id_str = str(terminal_id)
    
    if terminal_id_str not in active_terminals:
        raise HTTPException(status_code=503, detail="Terminal encontra-se offline.")
        
    target_sid = active_terminals[terminal_id_str]

    try:
        terminal_response = await sio.call(
            'request_checkin', 
            {'tax_id': current_user.tax_id}, 
            to=target_sid, 
            namespace='/checkin', 
            timeout=10.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Tempo de resposta do terminal excedido.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na comunicação com terminal: {str(e)}")

    if not isinstance(terminal_response, list):
        raise HTTPException(status_code=502, detail="Formato de resposta do terminal inválido.")

    # --- FAIL-FAST: TICKET LAYOUTS INTEGRITY ---
    incoming_layout_refs = {
        item.get('ticket', {}).get('layout_ref') 
        for item in terminal_response 
        if item.get('ticket', {}).get('layout_ref')
    }

    if incoming_layout_refs:
        existing_layouts = db.query(TicketLayout.ref).filter(
            TicketLayout.terminal_id == terminal_id,
            TicketLayout.ref.in_(incoming_layout_refs)
        ).all()
        
        existing_layout_refs = {e[0] for e in existing_layouts}
        missing_layouts = incoming_layout_refs - existing_layout_refs
        
        if missing_layouts:
            # 502 Bad Gateway: O equipamento na ponta devolveu um dado inconsistente com o banco
            raise HTTPException(
                status_code=502, 
                detail=f"Falha de integridade: O terminal retornou layouts de ticket inexistentes {list(missing_layouts)}."
            )

    # --- OPTIMIZATION: BATCH APPOINTMENTS QUERY ---
    incoming_appointment_refs = [
        item.get("appointment_ref") 
        for item in terminal_response 
        if item.get("appointment_ref")
    ]
    
    appointments_map = {}
    if incoming_appointment_refs:
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.terminal_id == terminal_id,
                Appointment.ref.in_(incoming_appointment_refs)
            )
            .all()
        )
        appointments_map = {appt.ref: appt for appt in appointments}

    created_tickets = []

    for item in terminal_response:
        appointment_ref = item.get("appointment_ref")
        layout_ref = item.get('ticket', {}).get('layout_ref')
        ticket_content = item.get('ticket', {}).get('content', {})

        # Lookup appointment using cached map rather than querying in the loop
        appointment = appointments_map.get(appointment_ref)
        if not appointment:
            continue 
            
        appointment.status = "CHECKED_IN"

        now = datetime.now(timezone.utc)
        new_ticket = Ticket(
            appointment_id=appointment.id,
            appointment_ref=appointment_ref,
            terminal_id=terminal_id,
            layout_ref=layout_ref,
            content=ticket_content,
            created_at=now
        )
        db.add(new_ticket)
        
        created_tickets.append(
            TicketItem(
                appointment_ref=appointment_ref,
                ticket={
                    "layout_ref": layout_ref,
                    "content": ticket_content,
                    "created_at": now.isoformat()
                }
            )
        )

    db.commit()
    return created_tickets