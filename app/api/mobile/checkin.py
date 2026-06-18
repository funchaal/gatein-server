import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Appointment, Ticket, TicketLayout
from app.schemas.checkin import TicketItem
from app.sockets import sio, active_terminals 

router = APIRouter()

@router.post("/{terminal_id}", response_model=List[TicketItem])
async def process_checkin(
    terminal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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

    # --- NOVA VALIDAÇÃO FAIL-FAST: TICKET LAYOUTS ---
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
    # ------------------------------------------------

    created_tickets = []

    for item in terminal_response:
        appointment_ref = item.get("appointment_ref")
        layout_ref = item.get('ticket', {}).get('layout_ref')
        ticket_content = item.get('ticket', {}).get('content', {})

        appointment = (
            db.query(Appointment)
            .filter(
                Appointment.terminal_id == terminal_id,
                Appointment.ref == appointment_ref
            )
            .first()
        )

        if not appointment:
            continue 

        new_ticket = Ticket(
            appointment_id=appointment.id,
            appointment_ref=appointment_ref,
            terminal_id=terminal_id,
            layout_ref=layout_ref,
            content=ticket_content
        )
        db.add(new_ticket)
        
        created_tickets.append(
            TicketItem(
                appointment_ref=appointment_ref,
                ticket={
                    "layout_ref": layout_ref,
                    "content": ticket_content
                }
            )
        )

    db.commit()
    return created_tickets