"""
app/core/tenant.py
──────────────────────────────────────────────────────────────────────────────
Sistema de isolamento Multi-Tenant para o ambiente de STAGING (PROD=False).

Como funciona:
  1. `TenantModelMixin`  →  herdado por todos os modelos que possuem company_id.
  2. `current_company_id_ctx` → ContextVar injetado pelo middleware/dependency
     a cada requisição autenticada em staging.
  3. Event listener `auto_filter_by_company_in_staging` → ativado APENAS quando
     PROD=False. A cada execução ORM, adiciona automaticamente o critério
     `WHERE company_id = :company_id` em qualquer query que envolva um modelo
     com TenantModelMixin — sem que o desenvolvedor precise escrever isso
     manualmente em cada rota.

Segurança em camadas:
  - Em PROD (PROD=True) este arquivo é importado mas o listener NÃO é
    registrado. Zero overhead, zero interferência no banco de produção.
  - Em STAGING (PROD=False) o filtro é automático e global. Um desenvolvedor
    não consegue "esquecer" de filtrar por empresa.
"""

import logging
from contextvars import ContextVar
from typing import Optional

from sqlalchemy import event
from sqlalchemy.orm import Session, ORMExecuteState, with_loader_criteria

from config import settings

logger = logging.getLogger(__name__)


# ─── Mixin de Tenant ─────────────────────────────────────────────────────────

class TenantModelMixin:
    """
    Herde este mixin em qualquer modelo SQLAlchemy que possua a coluna
    `company_id`. O event listener abaixo usa essa classe como seletor
    para injetar o filtro automático de empresa.

    Exemplo:
        class Appointment(Base, TenantModelMixin):
            __tablename__ = 'appointments'
            company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), ...)
    """
    company_id: object  # Coluna definida no modelo concreto


# ─── Context Variable ─────────────────────────────────────────────────────────

# Armazena o company_id da requisição atual de forma isolada por corrotina/thread.
# Injetado pela dependency `set_tenant_context` nas rotas mobile em staging.
current_company_id_ctx: ContextVar[Optional[str]] = ContextVar(
    "current_company_id", default=None
)


# ─── Event Listener (HOMOLOGATION ONLY) ───────────────────────────────────────

if settings.is_homologation:
    logger.warning(
        "[HOMOLOGATION] Isolamento multi-tenant via ORM ATIVADO. "
        "Todas as queries em modelos com TenantModelMixin serão "
        "automaticamente filtradas por company_id."
    )

    @event.listens_for(Session, "do_orm_execute")
    def auto_filter_by_company_in_homologation(execute_state: ORMExecuteState):
        """
        Intercepta toda execução ORM em sessões SQLAlchemy.
        Se `current_company_id_ctx` tiver valor, adiciona automaticamente
        a cláusula WHERE company_id = :company_id em qualquer query que
        envolva um modelo herdeiro de TenantModelMixin.
        """
        company_id = current_company_id_ctx.get()

        if company_id and execute_state.is_select and execute_state.is_orm_statement:
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(
                    TenantModelMixin,
                    lambda cls: cls.company_id == company_id,
                    include_aliases=True,
                )
            )
else:
    logger.info(f"[{settings.ENVIRONMENT.upper()}] Isolamento multi-tenant via ORM inativo.")
