import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, BigInteger, Float, DateTime, Date, ForeignKey, Index, UniqueConstraint, text, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.active import ActiveModelMixin
from sqlalchemy import Text


# --- ENUMS DE EVENTOS DE LOG ---

class AppointmentEvent(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_DELETED = "ticket_deleted"
    TERMINAL_PING = "terminal_ping"
    NOTIFICATION_SENT = "notification_sent"
    AUTO_DEACTIVATED = "auto_deactivated"
    CHECKIN_CANCELLED = "checkin_cancelled"
    VIEWED = "viewed"
    CLICKED = "clicked"

class TripEvent(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    VIEWED = "viewed"
    CLICKED = "clicked"

class AnnouncementEvent(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    VIEWED = "viewed"


# --- MODELO BASE COM HERANÇA ---

class Company(Base, ActiveModelMixin):
    __tablename__ = 'companies'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)  # 'terminal' ou 'trucking_company'
    
    username = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    branch_name = Column(String(100))  # Ex: "Filial Macaé", "Terminal Cabiúnas"
    unit_code = Column(String(50), index=True) # Ex: "MAC-01". Indexado caso a busca ocorra por código
    tax_id = Column(String(20), nullable=False, unique=True)
    phone = Column(String(20), nullable=False)
    email = Column(String(100), nullable=False)

    api_key_hash = Column(String(255), nullable=True)
    api_key_prefix = Column(String(50), unique=True, index=True, nullable=True)
    api_key_secondary_hash = Column(String(255), nullable=True)
    api_key_secondary_prefix = Column(String(50), unique=True, index=True, nullable=True)

    config = Column(JSONB, default={})

    address_street = Column(String(150))
    address_number = Column(String(20))
    address_city = Column(String(100))
    address_state = Column(String(50))
    address_country = Column(String(50))
    address_zip = Column(String(20))
    address_lat = Column(Float)
    address_lng = Column(Float)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': 'company'
    }

    __table_args__ = (
        Index(
            'idx_company_trgm_search',
            text("f_unaccent(name || ' ' || COALESCE(branch_name, '')) gin_trgm_ops"),
            postgresql_using='gin'
        ),
    )


class Terminal(Company):
    __tablename__ = 'terminals'

    id = Column(BigInteger, ForeignKey('companies.id'), primary_key=True)
    
    geofence = Column(JSONB, default={})
    appointment_layouts = Column(JSONB, default={})
    ticket_layouts = Column(JSONB, default={})
    use_remote_checkin = Column(Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'terminal'
    }


class TruckingCompany(Company):
    __tablename__ = 'trucking_companies'

    id = Column(BigInteger, ForeignKey('companies.id'), primary_key=True)
    
    trip_layouts = Column(JSONB, default={})

    __mapper_args__ = {
        'polymorphic_identity': 'trucking_company'
    }


# --- OUTROS MODELOS ---

class Driver(Base, ActiveModelMixin):
    __tablename__ = 'drivers'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tax_id = Column(String(14), unique=True, index=True, nullable=False)
    driver_license_number = Column(String(20))
    driver_license_category = Column(String(10))
    driver_license_expiration = Column(Date)

    # FK correta apontando para a tabela base
    validated_by = Column(BigInteger, ForeignKey('companies.id'))
    validated_by_company = relationship("Company")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class User(Base, ActiveModelMixin):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tax_id = Column(String(14), unique=True, nullable=False)
    name = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255))

    validated_device = Column(String(100))

    driver_id = Column(BigInteger, ForeignKey('drivers.id'), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    fcm_tokens = relationship("UserFCMToken", back_populates="user", cascade="all, delete-orphan")


class RegisterRequest(Base, ActiveModelMixin):
    __tablename__ = 'register_requests'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tax_id = Column(String(14), unique=True, index=True, nullable=False)
    name = Column(String(100))
    phone = Column(String(20))
    trusted_device = Column(String(100))

    register_step = Column(String(50), default='new')

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Appointment(Base, ActiveModelMixin):
    __tablename__ = 'appointments'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    terminal_id = Column(BigInteger, ForeignKey('terminals.id'), nullable=False)
    
    ref = Column(String(100), index=True, nullable=True)
    layout_ref = Column(String(50), nullable=True)
    
    user_tax_id = Column(String(14), index=True)
    status = Column(String(20), default='ACTIVE')
    summary = Column(String(150))
    license_plate = Column(String(10), index=True)
    window_start = Column(DateTime(timezone=True))
    window_end = Column(DateTime(timezone=True))
    start_tolerance = Column(Integer, default=0)
    end_tolerance = Column(Integer, default=0)
    custom_data = Column(JSONB)
    last_ping_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tickets = relationship("Ticket", back_populates="appointment", cascade="all, delete-orphan")
    terminal = relationship("Terminal")

    __table_args__ = (
        UniqueConstraint('terminal_id', 'ref', name='unique_appointment_ref_per_company'),
        Index('idx_appointment_terminal_ref', 'terminal_id', 'ref'),
    )

# Mapa estático — fonte da verdade por tipo de empresa
COMPANY_TYPE_MODULES = {
    'terminal':         {'geofence', 'appointment_layouts', 'ticket_layouts', 'services', 'company_information', 'users', 'api_keys', 'announcements'},
    'trucking_company': {'trip_layouts', 'services', 'company_information', 'users', 'api_keys', 'announcements'},
}

class CompanyUser(Base, ActiveModelMixin):
    __tablename__ = 'companies_users'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # FK correta apontando para a tabela base para aceitar ambos os tipos
    company_id = Column(BigInteger, ForeignKey('companies.id'), nullable=False)

    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100))

    is_admin = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    permissions = Column(JSONB, default={
        'services':             'read',
        'company_information':  'read',
        'users':                'none',
        'api_keys':             'none',
        'announcements':        'write',
        # módulos específicos são adicionados conforme o tipo da empresa
        # terminal:         geofence, appointment_layouts, ticket_layouts
        # trucking_company: trip_layouts
    })

    company = relationship("Company", lazy="joined")  # joined evita N+1

    def _module_allowed_for_company(self, module: str) -> bool:
        """Verifica se o módulo existe para o tipo desta empresa."""
        if not self.company:
            return False
        allowed = COMPANY_TYPE_MODULES.get(self.company.type, set())
        return module in allowed

    def can(self, module: str, action: str = 'write') -> bool:
        # 1. Módulo não existe para este tipo de empresa — bloqueia sempre,
        #    mesmo admin. É uma restrição estrutural, não de permissão.
        if not self._module_allowed_for_company(module):
            return False

        # 2. Admin passa em tudo que a empresa suporta
        if self.is_admin:
            return True

        # 3. Checa permissão individual
        perm = self.permissions.get(module, 'none')
        if action == 'read':
            return perm in ('read', 'write', 'read/write')
        if action == 'write':
            return perm in ('write', 'read/write')
        return False

class Ticket(Base, ActiveModelMixin):
    __tablename__ = 'tickets'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    appointment_id = Column(BigInteger, ForeignKey('appointments.id'), nullable=False)
    appointment_ref = Column(String(100), nullable=False)
    
    terminal_id = Column(BigInteger, ForeignKey('terminals.id'), nullable=False)

    layout_ref = Column(String(50), nullable=True) 
    content = Column(JSONB, nullable=False, default={})
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    appointment = relationship("Appointment", back_populates="tickets")
    terminal = relationship("Terminal")


# --- MODELOS DE LAYOUTS ---

class AppointmentLayout(Base, ActiveModelMixin):
    __tablename__ = 'appointments_layouts'

    id = Column(Integer, primary_key=True)
    terminal_id = Column(BigInteger, ForeignKey('terminals.id'), nullable=False)

    ref = Column(String(50), nullable=False)
    title = Column(String(100))
    layout = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_appointment_layout_lookup', 'terminal_id', 'ref', 'title'),
    )


class TicketLayout(Base, ActiveModelMixin):
    __tablename__ = 'tickets_layouts'

    id = Column(Integer, primary_key=True)
    terminal_id = Column(BigInteger, ForeignKey('terminals.id'), nullable=False)

    ref = Column(String(50), nullable=False)
    title = Column(String(100))
    layout = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_ticket_layout_lookup', 'terminal_id', 'ref', 'title'),
    )


class TripLayout(Base, ActiveModelMixin):
    __tablename__ = 'trips_layouts'

    id = Column(Integer, primary_key=True)
    # Trips pertencem a Trucking Companies
    trucking_company_id = Column(BigInteger, ForeignKey('trucking_companies.id'), nullable=False)

    ref = Column(String(50), nullable=False)
    title = Column(String(100))
    layout = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_trip_layout_lookup', 'trucking_company_id', 'ref', 'title'),
    )

class Trip(Base, ActiveModelMixin):
    __tablename__ = 'trips'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Vinculado à transportadora
    trucking_company_id = Column(BigInteger, ForeignKey('trucking_companies.id'), nullable=False)
    
    # Referência interna da transportadora e layout
    ref = Column(String(100), index=True, nullable=True)
    layout_ref = Column(String(50), nullable=True)
    
    # Dados operacionais
    driver_id = Column(BigInteger, ForeignKey('drivers.id'), nullable=True)
    license_plate = Column(String(10), index=True)
    
    status = Column(String(20), default='PLANNED')
    summary = Column(String(150))
    
    window_start = Column(DateTime(timezone=True))
    window_end = Column(DateTime(timezone=True))
    start_tolerance = Column(Integer, default=0)
    end_tolerance = Column(Integer, default=0)
    
    # Flexibilidade via layout
    custom_data = Column(JSONB, default={})

    # origin fields
    origin_street = Column(String(150))
    origin_number = Column(String(20))
    origin_city = Column(String(100))
    origin_state = Column(String(50))
    origin_country = Column(String(50))
    origin_zip = Column(String(20))
    origin_lat = Column(Float)
    origin_lng = Column(Float)

    # destiny fields
    destiny_street = Column(String(150))
    destiny_number = Column(String(20))
    destiny_city = Column(String(100))
    destiny_state = Column(String(50))
    destiny_country = Column(String(50))
    destiny_zip = Column(String(20))
    destiny_lat = Column(Float)
    destiny_lng = Column(Float)
    
    from_location = Column(String(100))
    to_location = Column(String(100))
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relacionamentos (opcional, dependendo de como você faz as queries)
    trucking_company = relationship("TruckingCompany")
    driver = relationship("Driver")

    __table_args__ = (
        UniqueConstraint('trucking_company_id', 'ref', name='unique_trip_ref_per_company'),
        Index('idx_trip_company_ref', 'trucking_company_id', 'ref'),
    )

class AllowedDomain(Base, ActiveModelMixin):
    __tablename__ = 'allowed_domains'

    id = Column(Integer, primary_key=True)

    domain = Column(String(255), unique=True, index=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_allowed_domains_lookup', 'domain', 'is_active'),
    )



class CompanyService(Base, ActiveModelMixin):
    __tablename__ = 'company_services'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Aponta para a tabela base para que tanto Terminals quanto TruckingCompanies possam ter serviços
    company_id = Column(BigInteger, ForeignKey('companies.id'), nullable=False)
    domain_id = Column(Integer, ForeignKey('allowed_domains.id'), nullable=False)
    
    title = Column(String(100), nullable=False)
    description = Column(Text)
    url = Column(String(500), nullable=False)
    icon_url = Column(String(500))

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relacionamento com a empresa
    company = relationship("Company")

    __table_args__ = (
        Index('idx_company_services_lookup', 'company_id', 'is_active'),
        Index('idx_company_services_ids', 'id'),
        Index('idx_company_services_domain', 'domain_id'),
    )


class Announcement(Base, ActiveModelMixin):
    __tablename__ = 'announcements'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey('companies.id'), nullable=False)
    
    title = Column(String(100), nullable=False)
    subtitle = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    image_position = Column(JSONB, default=dict) # stores { x: float, y: float, scale: float }
    url = Column(String(500), nullable=True)
    
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relacionamento com a empresa
    company = relationship("Company")

    __table_args__ = (
        Index('idx_announcements_company', 'company_id'),
        Index('idx_announcements_active', 'is_active', 'start_at', 'end_at'),
    )


class AppointmentLog(Base, ActiveModelMixin):
    __tablename__ = 'appointments_logs'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey('companies.id'), nullable=False)
    appointment_id = Column(BigInteger, ForeignKey('appointments.id'), nullable=False)
    event = Column(Enum(AppointmentEvent, name='appointment_event', native_enum=True), nullable=False)
    message = Column(Text, nullable=True)
    json = Column(JSONB, nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    company = relationship("Company")
    appointment = relationship("Appointment")


class TripLog(Base, ActiveModelMixin):
    __tablename__ = 'trips_logs'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey('companies.id'), nullable=False)
    trip_id = Column(BigInteger, ForeignKey('trips.id'), nullable=False)
    event = Column(Enum(TripEvent, name='trip_event', native_enum=True), nullable=False)
    message = Column(Text, nullable=True)
    json = Column(JSONB, nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    company = relationship("Company")
    trip = relationship("Trip")


class AnnouncementLog(Base, ActiveModelMixin):
    __tablename__ = 'announcements_logs'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    announcement_id = Column(BigInteger, ForeignKey('announcements.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    company_user_id = Column(BigInteger, ForeignKey('companies_users.id'), nullable=True)
    event = Column(Enum(AnnouncementEvent, name='announcement_event', native_enum=True), nullable=False)
    message = Column(Text, nullable=True)
    json = Column(JSONB, nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    announcement = relationship("Announcement")
    user = relationship("User")
    company_user = relationship("CompanyUser")


# --- MODELO FCM TOKENS ---

class UserFCMToken(Base, ActiveModelMixin):
    """Relação N:1 entre usuário e tokens FCM de dispositivos.
    Um usuário pode ter múltiplos dispositivos (celular, tablet, etc.).
    O token FCM é único por dispositivo — se o app for reinstalado, o token muda.
    """
    __tablename__ = 'user_fcm_tokens'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # O token FCM é único globalmente — não pode haver dois registros com o mesmo token
    fcm_token = Column(String(255), unique=True, nullable=False, index=True)

    # 'android' | 'ios' — opcional, útil para diagnóstico e personalização futura
    device_os = Column(String(10), nullable=True)

    last_updated = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="fcm_tokens")

    __table_args__ = (
        Index('idx_fcm_token_user_id', 'user_id'),
    )




# --- STAGING: Senha Mestra de Homologação ---

class StagingPassword(Base, ActiveModelMixin):
    """
    Armazena a senha mestra de homologação vinculada a uma empresa.
    Usada apenas em ambiente de STAGING (PROD=False).

    O painel web permite ao admin da empresa gerar/revogar essa senha.
    O app mobile a utiliza no login de staging, junto ao CPF do testador,
    para receber um JWT que inclui o company_id no payload.
    """
    __tablename__ = 'staging_passwords'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey('companies.id'), nullable=False, unique=True, index=True)

    # Hash bcrypt da senha gerada — nunca armazene a senha em texto plano
    password_hash = Column(String(255), nullable=False)

    # Gerado apenas 1 vez por empresa; ao gerar nova, a anterior é revogada
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company")

    __table_args__ = (
        Index('idx_staging_password_company', 'company_id'),
    )

class SafetyIntegration(Base, ActiveModelMixin):
    """
    Registra a integração de segurança de um motorista (por tax_id) com uma empresa (terminal).
    Pode ser enviado pelo ERP (com data de expiração) ou preenchido pelo app mobile.
    """
    __tablename__ = 'safety_integrations'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tax_id = Column(String(14), index=True, nullable=False)
    company_id = Column(BigInteger, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    
    watched_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company")

    __table_args__ = (
        UniqueConstraint('tax_id', 'company_id', name='unique_safety_integration_per_company'),
        Index('idx_safety_integrations_lookup', 'tax_id', 'company_id'),
    )