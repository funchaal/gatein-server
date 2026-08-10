"""
timezone.py — Utilitários de conversão e manipulação de fuso horário.

Trata datas sem fuso horário (naive) considerando o fuso padrão da aplicação
(America/Sao_Paulo) e convertendo para UTC consciente (timezone-aware UTC).
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Union

# Fuso horário padrão operacional (América/São Paulo: UTC-3)
DEFAULT_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def ensure_utc(dt_val: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """
    Garante que a data/hora recebida seja um datetime timezone-aware em UTC.
    Se a data for 'naive' (sem timezone info) ou uma string sem offset, assume o fuso
    horário local (America/Sao_Paulo) e realiza a conversão correta para UTC.
    """
    if dt_val is None or dt_val == "":
        return None

    if isinstance(dt_val, str):
        try:
            clean_str = dt_val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
        except Exception:
            return None
    else:
        dt = dt_val

    if dt.tzinfo is None:
        # Se for naive, atribui o fuso padrão local (America/Sao_Paulo)
        dt = dt.replace(tzinfo=DEFAULT_TIMEZONE)

    # Converte para UTC consciente
    return dt.astimezone(timezone.utc)
