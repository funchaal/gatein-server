"""rename_fields

Revision ID: 0e81d0b569a8
Revises: d604102778d8
Create Date: 2026-07-21 20:33:13.416098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e81d0b569a8'
down_revision: Union[str, Sequence[str], None] = 'd604102778d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename columns in appointments
    op.alter_column('appointments', 'vehicle_plate', new_column_name='license_plate')
    op.alter_column('appointments', 'schedule_start_time', new_column_name='window_start')
    op.alter_column('appointments', 'schedule_end_time', new_column_name='window_end')
    op.alter_column('appointments', 'schedule_start_tolerance', new_column_name='start_tolerance')
    op.alter_column('appointments', 'schedule_end_tolerance', new_column_name='end_tolerance')
    
    # Add last_ping_at and deactivated_at if they don't exist
    op.add_column('appointments', sa.Column('last_ping_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True))
    
    # Update indexes for appointments
    op.drop_index('ix_appointments_vehicle_plate', table_name='appointments')
    op.create_index(op.f('ix_appointments_license_plate'), 'appointments', ['license_plate'], unique=False)
    
    # Notifications index adjustments
    op.drop_index('idx_notifications_created_at', table_name='notifications')
    op.drop_index('idx_notifications_user_id', table_name='notifications')
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    
    # Rename columns in trips
    op.alter_column('trips', 'vehicle_plate', new_column_name='license_plate')
    op.alter_column('trips', 'schedule_start_time', new_column_name='window_start')
    op.alter_column('trips', 'schedule_end_time', new_column_name='window_end')
    op.alter_column('trips', 'schedule_start_tolerance', new_column_name='start_tolerance')
    op.alter_column('trips', 'schedule_end_tolerance', new_column_name='end_tolerance')
    
    # Update indexes for trips
    op.drop_index('ix_trips_vehicle_plate', table_name='trips')
    op.create_index(op.f('ix_trips_license_plate'), 'trips', ['license_plate'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Rename columns back in trips
    op.alter_column('trips', 'license_plate', new_column_name='vehicle_plate')
    op.alter_column('trips', 'window_start', new_column_name='schedule_start_time')
    op.alter_column('trips', 'window_end', new_column_name='schedule_end_time')
    op.alter_column('trips', 'start_tolerance', new_column_name='schedule_start_tolerance')
    op.alter_column('trips', 'end_tolerance', new_column_name='schedule_end_tolerance')
    
    # Update indexes for trips
    op.drop_index(op.f('ix_trips_license_plate'), table_name='trips')
    op.create_index('ix_trips_vehicle_plate', 'trips', ['vehicle_plate'], unique=False)
    
    # Notifications index adjustments
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.create_index('idx_notifications_user_id', 'notifications', ['user_id'], unique=False)
    op.create_index('idx_notifications_created_at', 'notifications', ['created_at'], unique=False)
    
    # Rename columns back in appointments
    op.alter_column('appointments', 'license_plate', new_column_name='vehicle_plate')
    op.alter_column('appointments', 'window_start', new_column_name='schedule_start_time')
    op.alter_column('appointments', 'window_end', new_column_name='schedule_end_time')
    op.alter_column('appointments', 'start_tolerance', new_column_name='schedule_start_tolerance')
    op.alter_column('appointments', 'end_tolerance', new_column_name='schedule_end_tolerance')
    
    # Remove columns last_ping_at and deactivated_at
    op.drop_column('appointments', 'deactivated_at')
    op.drop_column('appointments', 'last_ping_at')
    
    # Update indexes for appointments
    op.drop_index(op.f('ix_appointments_license_plate'), table_name='appointments')
    op.create_index('ix_appointments_vehicle_plate', 'appointments', ['vehicle_plate'], unique=False)
