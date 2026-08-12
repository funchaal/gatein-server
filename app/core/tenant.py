"""
app/core/tenant.py
──────────────────────────────────────────────────────────────────────────────
Sistema de isolamento Multi-Tenant para o ambiente de STAGING (PROD=False).

Como funciona:
  1. `current_company_id_ctx` → ContextVar injetado pela autenticação mobile/web
     a cada requisição autenticada em staging.
  2. Event listener `auto_filter_by_company_in_homologation` → ativado APENAS quando
     PROD=False. A cada execução ORM, adiciona automaticamente os critérios
     de filtro por empresa em qualquer query dos modelos da aplicação — sem que o
     desenvolvedor precise escrever isso manualmente em cada rota.

Segurança em camadas:
  - Em PROD (PROD=True) este arquivo é importado mas o listener NÃO é
    registrado. Zero overhead, zero interferência no banco de produção.
  - Em STAGING (PROD=False) o filtro é automático e global.
"""

import logging
from contextvars import ContextVar
from typing import Optional

from sqlalchemy import event
from sqlalchemy.orm import Session, ORMExecuteState, with_loader_criteria

from config import settings

logger = logging.getLogger(__name__)


# ─── Context Variable ─────────────────────────────────────────────────────────

# Armazena o company_id da requisição atual de forma isolada por corrotina/thread.
# Injetado pela dependência de autenticação nas rotas mobile em staging.
current_company_id_ctx: ContextVar[Optional[str]] = ContextVar(
    "current_company_id", default=None
)


# ─── Event Listener (STAGING / DEV / HOMOLOGATION) ───────────────────────────

if not settings.is_production:
    logger.warning(
        "[STAGING/DEV] Isolamento multi-tenant via ORM ATIVADO. "
        "Todas as queries em modelos de empresa serão "
        "automaticamente filtradas por company_id quando o contexto estiver preenchido."
    )

    @event.listens_for(Session, "do_orm_execute")
    def auto_filter_by_company_in_homologation(execute_state: ORMExecuteState):
        """
        Intercepta toda execução ORM em sessões SQLAlchemy.
        Se `current_company_id_ctx` tiver valor, adiciona automaticamente
        as cláusulas WHERE correspondentes aos modelos de empresa.
        """
        company_id_str = current_company_id_ctx.get()

        if company_id_str and execute_state.is_select and execute_state.is_orm_statement:
            from app.models import (
                Appointment, Trip, Company, CompanyService, Announcement,
                Submission, SubmissionType, AppointmentLayout, TicketLayout,
                TripLayout, Ticket, SafetyIntegration
            )

            try:
                cid = int(company_id_str)
            except (ValueError, TypeError):
                cid = company_id_str

            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(Appointment, lambda cls: cls.terminal_id == cid, include_aliases=True),
                with_loader_criteria(Trip, lambda cls: cls.trucking_company_id == cid, include_aliases=True),
                with_loader_criteria(Company, lambda cls: cls.id == cid, include_aliases=True),
                with_loader_criteria(CompanyService, lambda cls: cls.company_id == cid, include_aliases=True),
                with_loader_criteria(Announcement, lambda cls: cls.company_id == cid, include_aliases=True),
                with_loader_criteria(Submission, lambda cls: cls.company_id == cid, include_aliases=True),
                with_loader_criteria(SubmissionType, lambda cls: cls.company_id == cid, include_aliases=True),
                with_loader_criteria(AppointmentLayout, lambda cls: cls.terminal_id == cid, include_aliases=True),
                with_loader_criteria(TicketLayout, lambda cls: cls.terminal_id == cid, include_aliases=True),
                with_loader_criteria(TripLayout, lambda cls: cls.trucking_company_id == cid, include_aliases=True),
                with_loader_criteria(Ticket, lambda cls: cls.terminal_id == cid, include_aliases=True),
                with_loader_criteria(SafetyIntegration, lambda cls: cls.company_id == cid, include_aliases=True),
            )
else:
    logger.info(f"[{settings.ENVIRONMENT.upper()}] Isolamento multi-tenant via ORM inativo.")
