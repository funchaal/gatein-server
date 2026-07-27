"""add_secondary_api_key

Revision ID: a3f9e8712b01
Revises: 8dfea8e39bfe
Create Date: 2026-07-26 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f9e8712b01'
down_revision: Union[str, Sequence[str], None] = '8dfea8e39bfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('companies', 'api_key_hash',
               existing_type=sa.String(length=255),
               nullable=True)
    op.alter_column('companies', 'api_key_prefix',
               existing_type=sa.String(length=50),
               nullable=True)
    op.add_column('companies', sa.Column('api_key_secondary_hash', sa.String(length=255), nullable=True))
    op.add_column('companies', sa.Column('api_key_secondary_prefix', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_companies_api_key_secondary_prefix'), 'companies', ['api_key_secondary_prefix'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_companies_api_key_secondary_prefix'), table_name='companies')
    op.drop_column('companies', 'api_key_secondary_prefix')
    op.drop_column('companies', 'api_key_secondary_hash')
    op.alter_column('companies', 'api_key_prefix',
               existing_type=sa.String(length=50),
               nullable=False)
    op.alter_column('companies', 'api_key_hash',
               existing_type=sa.String(length=255),
               nullable=False)
