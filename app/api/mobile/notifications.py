"""
notifications.py — Endpoints de gerenciamento de tokens FCM e envio de notificações.

Endpoints:
    POST   /api/mobile/notifications/token  → Registrar/atualizar token (upsert)
    DELETE /api/mobile/notifications/token  → Remover token do dispositivo (logout)
    GET    /api/mobile/notifications/test   → Disparar notificação de teste
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.firebase import send_push_notification
from app.models import User, UserFCMToken

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterTokenRequest(BaseModel):
    """Payload para registrar ou atualizar um FCM token do dispositivo."""
    fcm_token: str
    device_os: Optional[str] = None  # 'android' | 'ios'


class TokenResponse(BaseModel):
    """Resposta de operações com token."""
    success: bool = True
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/notifications/token",
    response_model=TokenResponse,
    summary="Register FCM Token",
    description=(
        "Registers or updates the FCM token for the current device. "
        "Performs an upsert: if the token already exists, updates `last_updated`; "
        "if not, creates a new entry linked to the authenticated user."
    ),
    tags=["Mobile Notifications"],
)
def register_fcm_token(
    body: RegisterTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upsert do token FCM:
    - Se o token já existe no banco (qualquer usuário), atualiza last_updated e user_id.
    - Se não existe, cria um novo registro associado ao usuário autenticado.
    
    Isso garante que o mesmo token nunca apareça duas vezes na tabela
    (um token FCM é único por instalação do app, não por usuário).
    """
    existing = db.query(UserFCMToken).filter_by(fcm_token=body.fcm_token).first()

    if existing:
        # Atualiza vínculo e timestamp (o usuário pode ter trocado de conta no mesmo dispositivo)
        existing.user_id = current_user.id
        existing.device_os = body.device_os or existing.device_os
        existing.last_updated = datetime.now(timezone.utc)
        db.commit()
        return {"success": True, "message": "Token atualizado com sucesso."}

    new_token = UserFCMToken(
        user_id=current_user.id,
        fcm_token=body.fcm_token,
        device_os=body.device_os,
    )
    db.add(new_token)
    db.commit()
    return {"success": True, "message": "Token registrado com sucesso."}


@router.delete(
    "/notifications/token",
    response_model=TokenResponse,
    summary="Remove FCM Token",
    description=(
        "Removes a specific FCM token from the database. "
        "Should be called on logout to prevent notifications from reaching a signed-out device."
    ),
    tags=["Mobile Notifications"],
)
def remove_fcm_token(
    body: RegisterTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove o token FCM do dispositivo atual ao fazer logout."""
    deleted = (
        db.query(UserFCMToken)
        .filter(
            UserFCMToken.fcm_token == body.fcm_token,
            UserFCMToken.user_id == current_user.id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Token não encontrado para este usuário.")

    return {"success": True, "message": "Token removido com sucesso."}


@router.get(
    "/notifications/test",
    response_model=TokenResponse,
    summary="Send Test Notification",
    description=(
        "Fires a test push notification to all registered devices of the authenticated user. "
        "Useful for validating the Firebase integration end-to-end."
    ),
    tags=["Mobile Notifications"],
)
def send_test_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dispara uma notificação de teste para todos os dispositivos do usuário autenticado."""
    token_rows = db.query(UserFCMToken).filter_by(user_id=current_user.id).all()
    tokens = [row.fcm_token for row in token_rows]

    if not tokens:
        raise HTTPException(
            status_code=404,
            detail="Nenhum token FCM registrado. Abra o app para registrar o dispositivo primeiro."
        )

    result = send_push_notification(
        tokens=tokens,
        title="🔔 GateIn — Notificação de Teste",
        body=f"Olá, {current_user.name or 'motorista'}! As notificações estão funcionando.",
        data={"type": "TEST"},
    )

    # Limpeza de tokens mortos detectados durante o envio
    if result["dead_tokens"]:
        db.query(UserFCMToken).filter(
            UserFCMToken.fcm_token.in_(result["dead_tokens"])
        ).delete(synchronize_session=False)
        db.commit()

    return {
        "success": True,
        "message": f"Notificação enviada para {result['sent']} dispositivo(s). Falhas: {result['failed']}."
    }


class NotificationHistoryResponse(BaseModel):
    id: str
    title: str
    body: str
    data: Optional[dict] = None
    created_at: datetime


@router.get(
    "/notifications",
    response_model=list[NotificationHistoryResponse],
    summary="Get Notification History",
    description="Deprecated: Notification history is now managed locally on the mobile device.",
    tags=["Mobile Notifications"],
)
def get_notifications_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint mantido por compatibilidade. O histórico de notificações é salvo localmente no celular.
    """
    return []

