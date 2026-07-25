"""
app/core/active.py
──────────────────────────────────────────────────────────────────────────────
Sistema de filtro automático de registros ativos (`is_active = True`).

Como funciona:
  1. `ActiveModelMixin` → herdado por todos os modelos que possuem o campo `is_active`.
  2. Event listener `auto_filter_by_is_active` → intercepta todas as consultas ORM
     e injeta a cláusula `WHERE is_active = true` via `with_loader_criteria`.
  3. Para desativar temporariamente o filtro em consultas específicas (ex: relatórios/auditoria),
     utilize `.execution_options(include_inactive=True)` na query.
"""

import logging
from sqlalchemy import Column, Boolean, text, event
from sqlalchemy.orm import Session, ORMExecuteState, with_loader_criteria

logger = logging.getLogger(__name__)


# ─── Mixin de Registro Ativo ──────────────────────────────────────────────────

class ActiveModelMixin:
    """
    Herde este mixin em qualquer modelo SQLAlchemy para adicionar o campo
    `is_active` e ativar o filtro automático em consultas ORM.
    """
    is_active = Column(Boolean, default=True, server_default=text('true'), nullable=False)


# ─── Event Listener Global ────────────────────────────────────────────────────

@event.listens_for(Session, "do_orm_execute")
def auto_filter_by_is_active(execute_state: ORMExecuteState):
    """
    Intercepta toda execução ORM em sessões SQLAlchemy.
    Adiciona automaticamente a cláusula `WHERE is_active = true` em qualquer
    query SELECT que envolva um modelo herdeiro de ActiveModelMixin,
    a menos que a query tenha a opção `execution_options(include_inactive=True)`.
    """
    if (
        execute_state.is_select
        and execute_state.is_orm_statement
        and not execute_state.execution_options.get("include_inactive", False)
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                ActiveModelMixin,
                lambda cls: cls.is_active == True,
                include_aliases=True,
            )
        )
