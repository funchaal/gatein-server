"""
app/core/sqids.py
──────────────────────────────────────────────────────────────────────────────
Módulo centralizado para encode/decode de IDs usando Sqids.

Usa um alphabet sem vogais para evitar geração acidental de palavras ofensivas.
min_length=6 garante que os hashes tenham pelo menos 6 caracteres.

Uso:
    from app.core.sqids import encode_id, decode_id

    hash = encode_id(42)          # ex: "k3f8mn"
    original = decode_id("k3f8mn")  # 42
"""

from sqids import Sqids

_sqids = Sqids(
    alphabet="bcdfghjkmnpqrstvwxyz23456789",
    min_length=6,
)


def encode_id(id_value: int) -> str:
    """Encoda um BigInt ID para um hash Sqids curto."""
    return _sqids.encode([id_value])


def decode_id(hash_str: str) -> int:
    """Decoda um hash Sqids de volta para o BigInt ID original."""
    result = _sqids.decode(hash_str)
    if not result:
        raise ValueError(f"Invalid Sqid hash: {hash_str}")
    return result[0]
