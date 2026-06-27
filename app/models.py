import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, Date, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from sqlalchemy import Text


# --- MODELO BASE COM HERANÇA ---

class Company(Base):
    __tablename__ = 'companies'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(20), nullable=False)  # 'terminal' ou 'trucking_company'
    
    username = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    branch_name = Column(String(100))  # Ex: "Filial Macaé", "Terminal Cabiúnas"
    unit_code = Column(String(50), index=True) # Ex: "MAC-01". Indexado caso a busca ocorra por código
    tax_id = Column(String(20), nullable=False, unique=True)
    phone = Column(String(20), nullable=False)
    email = Column(String(100), nullable=False)

    api_key_hash = Column(String(255), nullable=False)
    api_key_prefix = Column(String(50), unique=True, index=True, nullable=False)

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

    id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), primary_key=True)
    
    geofence = Column(JSONB, default={})
    appointment_layouts = Column(JSONB, default={})
    ticket_layouts = Column(JSONB, default={})
    use_remote_checkin = Column(Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'terminal'
    }


class TruckingCompany(Company):
    __tablename__ = 'trucking_companies'

    id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), primary_key=True)
    
    trip_layouts = Column(JSONB, default={})

    __mapper_args__ = {
        'polymorphic_identity': 'trucking_company'
    }


# --- OUTROS MODELOS ---

class Driver(Base):
    __tablename__ = 'drivers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_id = Column(String(14), unique=True, index=True, nullable=False)
    driver_license_number = Column(String(20))
    driver_license_category = Column(String(10))
    driver_license_expiration = Column(Date)

    # FK correta apontando para a tabela base
    validated_by = Column(UUID(as_uuid=True), ForeignKey('companies.id'))
    validated_by_company = relationship("Company")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_id = Column(String(14), unique=True, nullable=False)
    name = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255))

    validated_device = Column(String(100))

    driver_id = Column(UUID(as_uuid=True), ForeignKey('drivers.id'), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RegisterRequest(Base):
    __tablename__ = 'register_requests'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_id = Column(String(14), unique=True, index=True, nullable=False)
    name = Column(String(100))
    phone = Column(String(20))
    trusted_device = Column(String(100))

    register_step = Column(String(50), default='new')

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Appointment(Base):
    __tablename__ = 'appointments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # FK corrigida (era 'terminal.id', agora é 'terminals.id')
    terminal_id = Column(UUID(as_uuid=True), ForeignKey('terminals.id'), nullable=False)
    
    ref = Column(String(100), index=True, nullable=True)
    layout_ref = Column(String(50), nullable=True)
    
    user_tax_id = Column(String(14), index=True)
    operation_type = Column(String(50), nullable=False)
    status = Column(String(20), default='SCHEDULED')
    summary = Column(String(150))
    vehicle_plate = Column(String(10), index=True)
    schedule_start_time = Column(DateTime(timezone=True))
    schedule_end_time = Column(DateTime(timezone=True))
    schedule_start_tolerance_min = Column(Integer, default=0)
    schedule_end_tolerance_min = Column(Integer, default=0)
    custom_data = Column(JSONB)
    
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
    'terminal':         {'geofence', 'appointment_layouts', 'ticket_layouts', 'services', 'company_information', 'users', 'api_keys'},
    'trucking_company': {'trip_layouts', 'services', 'company_information', 'users', 'api_keys'},
}

class CompanyUser(Base):
    __tablename__ = 'companies_users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FK correta apontando para a tabela base para aceitar ambos os tipos
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False)

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

class Ticket(Base):
    __tablename__ = 'tickets'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey('appointments.id'), nullable=False)
    appointment_ref = Column(String(100), nullable=False)
    
    # FK corrigida (era 'terminal.id', agora é 'terminals.id')
    terminal_id = Column(UUID(as_uuid=True), ForeignKey('terminals.id'), nullable=False)

    layout_ref = Column(String(50), nullable=True) 
    content = Column(JSONB, nullable=False, default={})
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    appointment = relationship("Appointment", back_populates="tickets")
    terminal = relationship("Terminal")


# --- MODELOS DE LAYOUTS ---

class AppointmentLayout(Base):
    __tablename__ = 'appointments_layouts'

    id = Column(Integer, primary_key=True)
    # FK corrigida para apontar especificamente para Terminals
    terminal_id = Column(UUID(as_uuid=True), ForeignKey('terminals.id'), nullable=False)

    ref = Column(String(50), nullable=False)
    title = Column(String(100))
    layout = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_appointment_layout_lookup', 'terminal_id', 'ref', 'title'),
    )


class TicketLayout(Base):
    __tablename__ = 'tickets_layouts'

    id = Column(Integer, primary_key=True)
    terminal_id = Column(UUID(as_uuid=True), ForeignKey('terminals.id'), nullable=False)

    ref = Column(String(50), nullable=False)
    title = Column(String(100))
    layout = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_ticket_layout_lookup', 'terminal_id', 'ref', 'title'),
    )


class TripLayout(Base):
    __tablename__ = 'trips_layouts'

    id = Column(Integer, primary_key=True)
    # Trips pertencem a Trucking Companies
    trucking_company_id = Column(UUID(as_uuid=True), ForeignKey('trucking_companies.id'), nullable=False)

    ref = Column(String(50), nullable=False)
    title = Column(String(100))
    layout = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_trip_layout_lookup', 'trucking_company_id', 'ref', 'title'),
    )

class Trip(Base):
    __tablename__ = 'trips'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Vinculado à transportadora
    trucking_company_id = Column(UUID(as_uuid=True), ForeignKey('trucking_companies.id'), nullable=False)
    
    # Referência interna da transportadora e layout
    ref = Column(String(100), index=True, nullable=True)
    layout_ref = Column(String(50), nullable=True)
    
    # Dados operacionais
    driver_id = Column(UUID(as_uuid=True), ForeignKey('drivers.id'), nullable=True)
    vehicle_plate = Column(String(10), index=True)
    
    status = Column(String(20), default='PLANNED')
    summary = Column(String(150))
    
    schedule_start_time = Column(DateTime(timezone=True))
    schedule_end_time = Column(DateTime(timezone=True))
    schedule_start_tolerance_min = Column(Integer, default=0)
    schedule_end_tolerance_min = Column(Integer, default=0)
    
    # Flexibilidade via layout
    custom_data = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relacionamentos (opcional, dependendo de como você faz as queries)
    trucking_company = relationship("TruckingCompany")
    driver = relationship("Driver")

    __table_args__ = (
        UniqueConstraint('trucking_company_id', 'ref', name='unique_trip_ref_per_company'),
        Index('idx_trip_company_ref', 'trucking_company_id', 'ref'),
    )

class AllowedDomain(Base):
    __tablename__ = 'allowed_domains'

    id = Column(Integer, primary_key=True)

    domain = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_allowed_domains_lookup', 'domain', 'is_active'),
    )



class CompanyService(Base):
    __tablename__ = 'company_services'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Aponta para a tabela base para que tanto Terminals quanto TruckingCompanies possam ter serviços
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False)
    domain_id = Column(Integer, ForeignKey('allowed_domains.id'), nullable=False)
    
    title = Column(String(100), nullable=False)
    description = Column(Text)
    url = Column(String(500), nullable=False)
    icon_url = Column(String(500))
    
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relacionamento com a empresa
    company = relationship("Company")

    __table_args__ = (
        Index('idx_company_services_lookup', 'company_id', 'is_active'),
        Index('idx_company_services_ids', 'id'),
        Index('idx_company_services_domain', 'domain_id'),
    )