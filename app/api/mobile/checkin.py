"""
checkin.py — Check-in remoto via Socket.IO e cancelamento de check-in.

Endpoints:
    POST /{terminal_id}          → Processa check-in remoto (via Socket.IO)
    POST /cancel/{appointment_id} → Cancela um check-in, revertendo para SCHEDULED
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db, SessionLocal
from app.core.dependencies import get_current_user
from app.models import User, Appointment, AppointmentLog, Ticket, TicketLayout
from app.schemas.checkin import TicketItem, CheckinResponse
from app.api.sockets.connection import sio
from app.api.sockets.handlers.checkin import active_terminals

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CancelCheckinRequest(BaseModel):
    """Payload para cancelamento de check-in."""
    reason: str


class CancelCheckinResponse(BaseModel):
    """Resposta ao cancelar check-in."""
    success: bool = True
    message: str
    appointment_id: str
    new_status: str


# ---------------------------------------------------------------------------
# POST /{terminal_id} — Processar check-in remoto
# ---------------------------------------------------------------------------

async def run_async_checkin(terminal_id: UUID, target_sid: str, tax_id: str):
    """
    Executa o handshake com o terminal físico em segundo plano.
    Salva os tickets, atualiza o status dos agendamentos e envia notificações de sucesso ou falha.
    """
    db = SessionLocal()
    try:
        try:
            terminal_response = await sio.call(
                'request_checkin',
                {'tax_id': tax_id},
                to=target_sid,
                namespace='/checkin',
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            try:
                from app.core.firebase import notify_user_by_tax_id
                notify_user_by_tax_id(
                    db,
                    tax_id,
                    "❌ Tempo limite excedido",
                    "O terminal demorou para responder ao check-in. Tente novamente.",
                    data={"type": "CHECKIN_FAILED"},
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Falha ao enviar push de timeout: {e}")
            return
        except Exception as e:
            try:
                from app.core.firebase import notify_user_by_tax_id
                notify_user_by_tax_id(
                    db,
                    tax_id,
                    "❌ Falha no check-in",
                    f"Erro de comunicação com o terminal: {str(e)}",
                    data={"type": "CHECKIN_FAILED"},
                )
            except Exception as e_push:
                import logging
                logging.getLogger(__name__).warning(f"Falha ao enviar push de erro: {e_push}")
            return

        if not isinstance(terminal_response, list):
            return

        # --- FAIL-FAST: TICKET LAYOUTS INTEGRITY ---
        incoming_layout_refs = {
            item.get('ticket', {}).get('layout_ref')
            for item in terminal_response
            if item.get('ticket', {}).get('layout_ref')
        }

        if incoming_layout_refs:
            existing_layouts = db.query(TicketLayout.ref).filter(
                TicketLayout.terminal_id == terminal_id,
                TicketLayout.ref.in_(incoming_layout_refs),
            ).all()

            existing_layout_refs = {e[0] for e in existing_layouts}
            missing_layouts = incoming_layout_refs - existing_layout_refs

            if missing_layouts:
                return

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
                    Appointment.ref.in_(incoming_appointment_refs),
                )
                .all()
            )
            appointments_map = {appt.ref: appt for appt in appointments}

        created_tickets = []
        checked_in_terminal_name: str | None = None

        for item in terminal_response:
            appointment_ref = item.get("appointment_ref")
            layout_ref = item.get('ticket', {}).get('layout_ref')
            ticket_content = item.get('ticket', {}).get('content', {})

            appointment = appointments_map.get(appointment_ref)
            if not appointment:
                continue

            appointment.status = "CHECKED-IN"

            if checked_in_terminal_name is None and appointment.terminal:
                checked_in_terminal_name = appointment.terminal.name

            now = datetime.now(timezone.utc)
            new_ticket = Ticket(
                appointment_id=appointment.id,
                appointment_ref=appointment_ref,
                terminal_id=terminal_id,
                layout_ref=layout_ref,
                content=ticket_content,
                created_at=now,
            )
            db.add(new_ticket)

            created_tickets.append(
                TicketItem(
                    appointment_ref=appointment_ref,
                    ticket={
                        "layout_ref": layout_ref,
                        "content": ticket_content,
                        "created_at": now.isoformat(),
                    },
                )
            )

        db.commit()

        # --- PUSH NOTIFICATION: CHECKED_IN ---
        if created_tickets and tax_id:
            try:
                from app.core.firebase import notify_user_by_tax_id
                terminal_display = checked_in_terminal_name or "terminal"
                notify_user_by_tax_id(
                    db,
                    tax_id,
                    "✅ Check-in realizado!",
                    f"Seu acesso foi liberado em {terminal_display}.",
                    data={"type": "CHECKED-IN"},
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Falha ao enviar push pós-checkin: {e}")
    finally:
        db.close()


@router.post(
    "/{terminal_id}",
    response_model=CheckinResponse,
    summary="Process Remote Check-in",
    description=(
        "Initiates check-in sequence with physical terminal hardware via sockets. "
        "Validates terminal presence and triggers check-in asynchronously in the background."
    ),
)
async def process_checkin(
    terminal_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers remote check-in for the driver user at the specified terminal.
    Delegates Socket.IO handshake to a background task and responds immediately.
    """
    terminal_id_str = str(terminal_id)

    if terminal_id_str not in active_terminals:
        raise HTTPException(status_code=503, detail="Terminal encontra-se offline.")

    target_sid = active_terminals[terminal_id_str]

    background_tasks.add_task(run_async_checkin, terminal_id, target_sid, current_user.tax_id)

    return CheckinResponse(
        success=True,
        message="Check-in solicitado, aguardando retorno do servidor. Quando o check-in for confirmado você será notificado."
    )


# ---------------------------------------------------------------------------
# POST /cancel/{appointment_id} — Cancelar check-in
# ---------------------------------------------------------------------------

@router.post(
    "/cancel/{appointment_id}",
    response_model=CancelCheckinResponse,
    summary="Cancel Check-in",
    description=(
        "Cancels an existing check-in, reverting the appointment status from "
        "CHECKED_IN or IN_PROGRESS back to SCHEDULED. "
        "Records the cancellation reason in the appointment logs and notifies the driver."
    ),
    tags=["Websocket & Checkin"],
)
def cancel_checkin(
    appointment_id: UUID,
    body: CancelCheckinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reverte o status de um agendamento de CHECKED_IN / IN_PROGRESS para SCHEDULED.

    - Valida que o agendamento pertence ao usuário autenticado.
    - Reverte o status para SCHEDULED.
    - Registra um AppointmentLog com o evento 'checkin_cancelled' e o motivo.
    - Dispara notificação push informando o motorista do cancelamento.
    """
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.user_tax_id == current_user.tax_id,
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    if appointment.status not in ("CHECKED-IN", "ON_GOING"):
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível cancelar check-in de um agendamento com status '{appointment.status}'."
        )

    old_status = appointment.status
    appointment.status = "ACTIVE"

    # Registra no log do agendamento
    log_entry = AppointmentLog(
        company_id=appointment.terminal_id,
        appointment_id=appointment.id,
        event="checkin_cancelled",
        message=f"Check-in cancelado pelo motorista. Motivo: {body.reason}",
        json={
            "previous_status": old_status,
            "reason": body.reason,
            "cancelled_by_tax_id": current_user.tax_id,
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(log_entry)
    db.commit()

    # Notifica o motorista
    try:
        from app.core.firebase import notify_user_by_tax_id
        terminal_name = appointment.terminal.name if appointment.terminal else "terminal"
        notify_user_by_tax_id(
            db,
            current_user.tax_id,
            "⚠️ Check-in cancelado",
            f"Motivo: {body.reason}. Seu agendamento em {terminal_name} voltou para Agendado.",
            data={
                "type": "CHECKIN_CANCELLED",
                "appointment_id": str(appointment.id),
                "reason": body.reason,
            },
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Falha ao enviar push de cancelamento: {e}")

    return {
        "success": True,
        "message": "Check-in cancelado com sucesso. Agendamento revertido para SCHEDULED.",
        "appointment_id": str(appointment.id),
        "new_status": "ACTIVE",
    }