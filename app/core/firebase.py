"""
firebase.py — Módulo singleton de integração com o Firebase Admin SDK.

Inicializa o app uma única vez na importação.
Expõe send_push_notification() para envio multicast com auto-cleanup de tokens mortos.
"""

import os
import logging
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inicialização única do Firebase Admin SDK
# ---------------------------------------------------------------------------

_cred_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", settings.FIREBASE_CREDENTIALS_PATH)
)

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(_cred_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK inicializado com sucesso.")
    except Exception as e:
        logger.error(f"Falha ao inicializar Firebase Admin SDK: {e}")


# ---------------------------------------------------------------------------
# Função principal de envio
# ---------------------------------------------------------------------------

def send_push_notification(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
    android_priority: str = "high",
) -> dict:
    """
    Envia uma notificação push para um ou mais tokens FCM.

    Retorna um dict com:
        - sent (int): notificações enviadas com sucesso
        - failed (int): falhas de envio
        - dead_tokens (list[str]): tokens inválidos que devem ser removidos do banco

    Args:
        tokens: Lista de FCM tokens de destino.
        title: Título da notificação.
        body: Corpo/texto da notificação.
        data: Payload de dados extras (dict de str→str). Usado para deep-links
              e lógica customizada no app (ex: type="COUNTDOWN").
        android_priority: Prioridade Android ('high' ou 'normal').
    """
    if not tokens:
        return {"sent": 0, "failed": 0, "dead_tokens": []}

    # Garante que todos os valores do data payload são strings (requisito FCM)
    str_data = {k: str(v) for k, v in (data or {}).items()}

    messages = [
        messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=str_data if str_data else None,
            android=messaging.AndroidConfig(
                priority=android_priority,
                notification=messaging.AndroidNotification(
                    sound="default",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default")
                )
            ),
            token=token,
        )
        for token in tokens
    ]

    try:
        batch_response = messaging.send_each(messages)
    except Exception as e:
        logger.error(f"Erro ao chamar messaging.send_each: {e}")
        return {"sent": 0, "failed": len(tokens), "dead_tokens": []}

    sent = 0
    failed = 0
    dead_tokens: list[str] = []

    for idx, response in enumerate(batch_response.responses):
        if response.success:
            sent += 1
        else:
            failed += 1
            error = response.exception
            token = tokens[idx]
            # Tokens mortos: dispositivo desinstalou o app ou token expirou
            if isinstance(error, messaging.UnregisteredError):
                dead_tokens.append(token)
                logger.info(f"Token morto detectado e marcado para remoção: {token[:30]}...")
            else:
                logger.warning(f"Falha ao enviar para token {token[:30]}...: {error}")

    logger.info(f"Push enviado — enviados: {sent}, falhas: {failed}, mortos: {len(dead_tokens)}")
    return {"sent": sent, "failed": failed, "dead_tokens": dead_tokens}


def notify_user_by_tax_id(
    db,
    tax_id: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict:
    """
    Busca todos os tokens FCM de um usuário pelo tax_id e dispara a notificação.
    Remove automaticamente tokens mortos do banco após o envio.

    Args:
        db: Sessão SQLAlchemy.
        tax_id: CPF do motorista (chave de busca no User).
        title, body, data: Parâmetros da notificação.
    """
    from app.models import User, UserFCMToken

    user = db.query(User).filter_by(tax_id=tax_id).first()
    if not user:
        logger.warning(f"notify_user_by_tax_id: usuário não encontrado para tax_id {tax_id}")
        return {"sent": 0, "failed": 0, "dead_tokens": []}

    token_rows = db.query(UserFCMToken).filter_by(user_id=user.id).all()
    tokens = [row.fcm_token for row in token_rows]

    if not tokens:
        return {"sent": 0, "failed": 0, "dead_tokens": []}

    result = send_push_notification(tokens, title, body, data)

    # Limpeza automática de tokens mortos
    if result["dead_tokens"]:
        db.query(UserFCMToken).filter(
            UserFCMToken.fcm_token.in_(result["dead_tokens"])
        ).delete(synchronize_session=False)
        db.commit()

    return result


def notify_users_by_tax_ids(
    db,
    tax_ids: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict:
    """
    Notifica múltiplos usuários (por lista de tax_ids) em uma única chamada multicast.
    Útil para notificações em lote (ex: lembretes de 1 dia).
    """
    from app.models import User, UserFCMToken

    if not tax_ids:
        return {"sent": 0, "failed": 0, "dead_tokens": []}

    users = db.query(User).filter(User.tax_id.in_(tax_ids)).all()
    user_ids = [u.id for u in users]

    token_rows = db.query(UserFCMToken).filter(
        UserFCMToken.user_id.in_(user_ids)
    ).all()
    tokens = [row.fcm_token for row in token_rows]

    if not tokens:
        return {"sent": 0, "failed": 0, "dead_tokens": []}

    result = send_push_notification(tokens, title, body, data)

    if result["dead_tokens"]:
        db.query(UserFCMToken).filter(
            UserFCMToken.fcm_token.in_(result["dead_tokens"])
        ).delete(synchronize_session=False)
        db.commit()

    return result
