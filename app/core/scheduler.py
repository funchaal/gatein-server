"""
scheduler.py — Jobs recorrentes de notificações push (APScheduler).

Jobs registrados:
  - check_1day_reminders   : a cada hora    → agendamentos que começam amanhã
  - check_12h_reminders    : a cada 15min   → agendamentos que começam em ~12h
  - check_window_open      : a cada 5min    → agendamentos SCHEDULED dentro da janela
  - check_in_progress      : a cada 5min    → agendamentos IN_PROGRESS em andamento
  - cleanup_dead_tokens    : diário (03:00) → remove tokens não atualizados há 90 dias
"""

import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ---------------------------------------------------------------------------
# Job 1: Lembretes de 1 dia
# ---------------------------------------------------------------------------

def check_1day_reminders():
    """
    Dispara notificações para agendamentos que começam amanhã.
    Agrupa múltiplos agendamentos do mesmo dia em uma única notificação por usuário.
    Garante envio único por agendamento.
    Roda a cada hora.
    """
    from app.models import Appointment, AppointmentLog
    from app.core.firebase import notify_user_by_tax_id

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Janela: entre 23h e 25h a partir de agora (evita duplo envio)
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.status == "ACTIVE",
                Appointment.window_start >= window_start,
                Appointment.window_start <= window_end,
                Appointment.user_tax_id != None,
            )
            .all()
        )

        if not appointments:
            return

        appt_ids = [appt.id for appt in appointments]
        sent_logs = (
            db.query(AppointmentLog.appointment_id, AppointmentLog.json)
            .filter(
                AppointmentLog.appointment_id.in_(appt_ids),
                AppointmentLog.event == "notification_sent",
            )
            .all()
        )
        already_sent_ids = {
            log.appointment_id
            for log in sent_logs
            if log.json and log.json.get("push_type") == "REMINDER_1DAY"
        }

        unsent_appointments = [a for a in appointments if a.id not in already_sent_ids]
        if not unsent_appointments:
            return

        # Agrupa por usuário
        by_user: dict[str, list] = defaultdict(list)
        for appt in unsent_appointments:
            by_user[appt.user_tax_id].append(appt)

        for tax_id, appts in by_user.items():
            terminal_name = appts[0].terminal.name if appts[0].terminal else "terminal"
            count = len(appts)
            if count == 1:
                appt = appts[0]
                hora = appt.window_start.strftime("%H:%M") if appt.window_start else "?"
                title = "📌 Lembrete: amanhã"
                body = f"Você tem um agendamento em {terminal_name} às {hora}"
            else:
                title = "📌 Lembrete: amanhã"
                body = f"Você tem {count} agendamentos amanhã"

            notify_user_by_tax_id(
                db, tax_id, title, body,
                data={"type": "REMINDER_1DAY", "count": str(count)}
            )

            # Registra no log de cada agendamento envolvido
            for appt in appts:
                if appt.terminal_id:
                    db.add(AppointmentLog(
                        company_id=appt.terminal_id,
                        appointment_id=appt.id,
                        event="notification_sent",
                        message="Notificação de lembrete (1 dia) enviada ao motorista.",
                        json={"push_type": "REMINDER_1DAY", "sent_at": now.isoformat()}
                    ))
        db.commit()

        logger.info(f"[scheduler] 1-day reminders: {len(by_user)} usuários notificados.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em check_1day_reminders: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 2: Lembretes de 12h (notificação fixa com countdown no app)
# ---------------------------------------------------------------------------

def check_12h_reminders():
    """
    Dispara notificações para agendamentos que começam em ~12h.
    O data payload inclui type=COUNTDOWN e o timestamp exato de início
    para que o app exiba um countdown local.
    Garante envio único por agendamento.
    Roda a cada 15 minutos.
    """
    from app.models import Appointment, AppointmentLog
    from app.core.firebase import notify_user_by_tax_id

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Janela de ±7.5 minutos ao redor das 12h
        window_start = now + timedelta(hours=11, minutes=52, seconds=30)
        window_end = now + timedelta(hours=12, minutes=7, seconds=30)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.status == "ACTIVE",
                Appointment.window_start >= window_start,
                Appointment.window_start <= window_end,
                Appointment.user_tax_id != None,
            )
            .all()
        )

        if not appointments:
            return

        appt_ids = [appt.id for appt in appointments]
        sent_logs = (
            db.query(AppointmentLog.appointment_id, AppointmentLog.json)
            .filter(
                AppointmentLog.appointment_id.in_(appt_ids),
                AppointmentLog.event == "notification_sent",
            )
            .all()
        )
        already_sent_ids = {
            log.appointment_id
            for log in sent_logs
            if log.json and log.json.get("push_type") == "COUNTDOWN"
        }

        unsent_appointments = [a for a in appointments if a.id not in already_sent_ids]
        if not unsent_appointments:
            return

        by_user: dict[str, list] = defaultdict(list)
        for appt in unsent_appointments:
            by_user[appt.user_tax_id].append(appt)

        for tax_id, appts in by_user.items():
            if len(appts) == 1:
                appt = appts[0]
                terminal_name = appt.terminal.name if appt.terminal else "terminal"
                hora = appt.window_start.strftime("%H:%M") if appt.window_start else "?"
                title = "⏱ Em breve!"
                body = f"Agendamento em {terminal_name} às {hora}"
                target_ts = appt.window_start.isoformat() if appt.window_start else ""
                appt_id = str(appt.id)
            else:
                count = len(appts)
                title = "⏱ Em breve!"
                body = f"Você tem {count} agendamentos em ~12 horas"
                target_ts = appts[0].window_start.isoformat() if appts[0].window_start else ""
                appt_id = str(appts[0].id)

            notify_user_by_tax_id(
                db, tax_id, title, body,
                data={
                    "type": "COUNTDOWN",
                    "appointment_id": appt_id,
                    "target_timestamp": target_ts,
                    "count": str(len(appts)),
                }
            )

            # Registra no log de cada agendamento
            for appt in appts:
                if appt.terminal_id:
                    db.add(AppointmentLog(
                        company_id=appt.terminal_id,
                        appointment_id=appt.id,
                        event="notification_sent",
                        message="Notificação de countdown (12h) enviada ao motorista.",
                        json={"push_type": "COUNTDOWN", "sent_at": now.isoformat()}
                    ))
        db.commit()

        logger.info(f"[scheduler] 12h reminders: {len(by_user)} usuários notificados.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em check_12h_reminders: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 3: Janela aberta (SCHEDULED dentro da janela de check-in)
# ---------------------------------------------------------------------------

def check_window_open():
    """
    Verifica agendamentos SCHEDULED que estão dentro da janela de check-in
    (window_start - tolerance até window_end + tolerance) e notifica.
    Garante que a notificação de janela aberta seja enviada uma única vez por agendamento.
    Roda a cada 5 minutos.
    """
    from app.models import Appointment, AppointmentLog
    from app.core.firebase import notify_user_by_tax_id

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.status == "ACTIVE",
                Appointment.user_tax_id != None,
            )
            .all()
        )

        if not appointments:
            return

        appt_ids = [appt.id for appt in appointments]
        sent_logs = (
            db.query(AppointmentLog.appointment_id, AppointmentLog.json)
            .filter(
                AppointmentLog.appointment_id.in_(appt_ids),
                AppointmentLog.event == "notification_sent",
            )
            .all()
        )
        already_sent_ids = {
            log.appointment_id
            for log in sent_logs
            if log.json and log.json.get("push_type") == "WINDOW_OPEN"
        }

        sent_count = 0
        for appt in appointments:
            if appt.id in already_sent_ids:
                continue

            if not appt.window_start or not appt.window_end:
                continue

            window_open = appt.window_start - timedelta(minutes=appt.start_tolerance)
            window_close = appt.window_end + timedelta(minutes=appt.end_tolerance)

            if window_open <= now <= window_close:
                until = window_close.strftime("%H:%M")
                terminal_name = appt.terminal.name if appt.terminal else "terminal"
                notify_user_by_tax_id(
                    db, appt.user_tax_id,
                    "🟢 Janela aberta!",
                    f"Você tem até {until} para fazer check-in em {terminal_name}",
                    data={
                        "type": "WINDOW_OPEN",
                        "appointment_id": str(appt.id),
                        "window_close": window_close.isoformat(),
                    }
                )

                db.add(AppointmentLog(
                    company_id=appt.terminal_id,
                    appointment_id=appt.id,
                    event="notification_sent",
                    message="Notificação de janela de check-in aberta enviada ao motorista.",
                    json={"push_type": "WINDOW_OPEN", "sent_at": now.isoformat()}
                ))
                sent_count += 1

        db.commit()
        logger.info(f"[scheduler] check_window_open executado em {now.isoformat()}: {sent_count} notificações enviadas.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em check_window_open: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 4: Em progresso (IN_PROGRESS → instrução na notificação)
# ---------------------------------------------------------------------------

def check_in_progress():
    """
    Para agendamentos em status IN_PROGRESS, envia notificação com instrução.
    Garante que a notificação seja enviada uma única vez ao entrar em andamento.
    Roda a cada 5 minutos.
    """
    from app.models import Appointment, AppointmentLog
    from app.core.firebase import notify_user_by_tax_id

    db = SessionLocal()
    try:
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.status == "ON_GOING",
                Appointment.user_tax_id != None,
            )
            .all()
        )

        if not appointments:
            return

        appt_ids = [appt.id for appt in appointments]
        sent_logs = (
            db.query(AppointmentLog.appointment_id, AppointmentLog.json)
            .filter(
                AppointmentLog.appointment_id.in_(appt_ids),
                AppointmentLog.event == "notification_sent",
            )
            .all()
        )
        already_sent_ids = {
            log.appointment_id
            for log in sent_logs
            if log.json and log.json.get("push_type") == "ON_GOING"
        }

        sent_count = 0
        for appt in appointments:
            if appt.id in already_sent_ids:
                continue

            terminal_name = appt.terminal.name if appt.terminal else "terminal"
            notify_user_by_tax_id(
                db, appt.user_tax_id,
                "🏭 Em andamento",
                f"Siga as instruções do terminal {terminal_name}",
                data={
                    "type": "ON_GOING",
                    "appointment_id": str(appt.id),
                }
            )

            now = datetime.now(timezone.utc)
            db.add(AppointmentLog(
                company_id=appt.terminal_id,
                appointment_id=appt.id,
                event="notification_sent",
                message="Notificação de operação em andamento enviada ao motorista.",
                json={"push_type": "ON_GOING", "sent_at": now.isoformat()}
            ))
            sent_count += 1

        db.commit()
        logger.info(f"[scheduler] check_in_progress: {sent_count} notificações enviadas.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em check_in_progress: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 5: Limpeza de tokens mortos por antiguidade
# ---------------------------------------------------------------------------

def cleanup_dead_tokens():
    """
    Remove tokens FCM que não foram atualizados nos últimos 90 dias.
    Um token pode ficar inativo por tempo prolongado se o usuário não abrir o app.
    Roda diariamente às 03:00.
    """
    from app.models import UserFCMToken

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        deleted = (
            db.query(UserFCMToken)
            .filter(UserFCMToken.last_updated < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"[scheduler] cleanup_dead_tokens: {deleted} token(s) removidos.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em cleanup_dead_tokens: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 6: Desativar agendamentos abandonados
# ---------------------------------------------------------------------------

def deactivate_abandoned_appointments():
    """
    Desativa agendamentos por inatividade ou estouro de tolerância (2 horas sem ping):
    1. Status ACTIVE cuja janela encerrou há mais de 2 horas e não recebeu ping.
    2. Status CHECKED-IN, ON_GOING, PAUSED que estão há mais de 2 horas sem ping do terminal.
    Ao desativar, registra deactivated_at = now() para que o app exiba em 'Atividades' por 12h.
    Roda a cada 5 minutos.
    """
    from app.models import Appointment, AppointmentLog
    from app.core.firebase import notify_user_by_tax_id

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        two_hours_ago = now - timedelta(hours=2)

        active_candidates = (
            db.query(Appointment)
            .filter(
                Appointment.status.in_(["ACTIVE", "CHECKED-IN", "ON_GOING", "PAUSED"]),
            )
            .all()
        )

        to_deactivate = []

        for appt in active_candidates:
            last_activity = appt.last_ping_at or appt.updated_at or appt.created_at

            if appt.status == "ACTIVE":
                if appt.window_end:
                    end_window = appt.window_end + timedelta(minutes=appt.end_tolerance or 0)
                    # Janela expirou há mais de 2h e não pingou nas últimas 2h
                    if now > (end_window + timedelta(hours=2)) and (not last_activity or last_activity < two_hours_ago):
                        to_deactivate.append((appt, "Janela expirada há mais de 2h sem ping do terminal."))
                else:
                    if last_activity and last_activity < (now - timedelta(days=2)):
                        to_deactivate.append((appt, "Inatividade prolongada (> 2 dias)."))
            elif appt.status in ["CHECKED-IN", "ON_GOING", "PAUSED"]:
                # Mais de 2 horas sem ping do terminal durante operação
                if not last_activity or last_activity < two_hours_ago:
                    to_deactivate.append((appt, f"Mais de 2 horas sem ping do terminal em status '{appt.status}'."))

        for appt, reason in to_deactivate:
            old_status = appt.status
            appt.status = "DEACTIVATED"
            appt.deactivated_at = now
            appt.updated_at = now
            
            db.add(AppointmentLog(
                company_id=appt.terminal_id,
                appointment_id=appt.id,
                event="auto_deactivated",
                message=f"Agendamento desativado automaticamente: {reason}",
                json={"previous_status": old_status, "deactivated_at": now.isoformat()}
            ))
            
            # Notifica motorista sobre desativação (invalida cache e gera alerta)
            if appt.user_tax_id:
                try:
                    terminal_name = appt.terminal.name if appt.terminal else "terminal"
                    notify_user_by_tax_id(
                        db, appt.user_tax_id,
                        "Agendamento Desativado",
                        f"Seu agendamento em {terminal_name} foi desativado por inatividade.",
                        data={"type": "CANCELLED", "appointment_id": str(appt.id)}
                    )
                except Exception:
                    pass

        db.commit()
        if to_deactivate:
            logger.info(f"[scheduler] {len(to_deactivate)} agendamento(s) desativado(s) por inatividade/tolerância.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em deactivate_abandoned_appointments: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 7: Excluir anúncios vencidos por data de expiração (e do Cloudflare R2)
# ---------------------------------------------------------------------------

def cleanup_expired_announcements():
    """
    Desativa anúncios vencidos por data de expiração (is_active = False, onde end_at < agora).
    Exclui a imagem do Cloudflare R2 para economizar espaço e remove image_url.
    Roda a cada 30 minutos.
    """
    from app.models import Announcement
    from app.api.web.uploads import delete_r2_image

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired_announcements = (
            db.query(Announcement)
            .filter(
                Announcement.is_active == True,
                Announcement.end_at != None,
                Announcement.end_at < now
            )
            .all()
        )

        if not expired_announcements:
            return

        count = 0
        for ann in expired_announcements:
            if ann.image_url:
                delete_r2_image(ann.image_url)
                ann.image_url = None
            ann.is_active = False
            count += 1

        db.commit()
        logger.info(f"[scheduler] cleanup_expired_announcements: {count} anúncio(s) vencido(s) desativado(s) (is_active=False) e imagem(ns) removida(s) do R2.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em cleanup_expired_announcements: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Registro dos jobs
# ---------------------------------------------------------------------------

def start_scheduler():
    """Inicia o scheduler com todos os jobs registrados. Chamado no startup do FastAPI."""
    if scheduler.running:
        return

    # Job 1 — Lembretes de 1 dia (a cada hora, no minuto 0)
    scheduler.add_job(
        check_1day_reminders,
        "cron",
        minute=0,
        id="job_1day_reminders",
        replace_existing=True,
    )

    # Job 2 — Lembretes de 12h (a cada 15 minutos)
    scheduler.add_job(
        check_12h_reminders,
        "interval",
        minutes=15,
        id="job_12h_reminders",
        replace_existing=True,
    )

    # Job 3 — Janela aberta (a cada 5 minutos)
    scheduler.add_job(
        check_window_open,
        "interval",
        minutes=5,
        id="job_window_open",
        replace_existing=True,
    )

    # Job 4 — Em progresso (a cada 5 minutos)
    scheduler.add_job(
        check_in_progress,
        "interval",
        minutes=5,
        id="job_in_progress",
        replace_existing=True,
    )

    # Job 5 — Limpeza de tokens mortos (diariamente às 03:00)
    scheduler.add_job(
        cleanup_dead_tokens,
        "cron",
        hour=3,
        minute=0,
        id="job_cleanup_tokens",
        replace_existing=True,
    )

    # Job 6 — Desativar agendamentos por inatividade/tolerância (a cada 5 minutos)
    scheduler.add_job(
        deactivate_abandoned_appointments,
        "interval",
        minutes=5,
        id="job_deactivate_abandoned",
        replace_existing=True,
    )

    # Job 7 — Limpeza de anúncios vencidos por data (a cada 30 minutos)
    scheduler.add_job(
        cleanup_expired_announcements,
        "interval",
        minutes=30,
        id="job_cleanup_expired_announcements",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler iniciado com 7 jobs configurados.")


def stop_scheduler():
    """Para o scheduler graciosamente. Chamado no shutdown do FastAPI."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler parado.")
