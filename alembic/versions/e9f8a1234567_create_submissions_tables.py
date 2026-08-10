"""create_submissions_tables

Revision ID: e9f8a1234567
Revises: d8ae919842f6
Create Date: 2026-08-09 20:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e9f8a1234567'
down_revision: Union[str, None] = 'd8ae919842f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create submission_types table
    op.create_table(
        'submission_types',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('ref', sa.String(length=50), nullable=False),
        sa.Column('allow_edit', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('accepts_attachment', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('multiple_attachments', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('allowed_formats', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('attachment_required', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('fields', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'ref', name='unique_submission_type_ref_per_company')
    )
    op.create_index('idx_submission_type_lookup', 'submission_types', ['company_id', 'ref'], unique=False)

    # 2. Create submissions table
    op.create_table(
        'submissions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.BigInteger(), nullable=False),
        sa.Column('submission_type_id', sa.BigInteger(), nullable=True),
        sa.Column('user_tax_id', sa.String(length=14), nullable=False),
        sa.Column('user_name', sa.String(length=100), nullable=True),
        sa.Column('type_title', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='SENT', nullable=True),
        sa.Column('field_data', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['submission_type_id'], ['submission_types.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_submissions_company_tax_id', 'submissions', ['company_id', 'user_tax_id'], unique=False)
    op.create_index('idx_submissions_user_tax_id', 'submissions', ['user_tax_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_submissions_user_tax_id', table_name='submissions')
    op.drop_index('idx_submissions_company_tax_id', table_name='submissions')
    op.drop_table('submissions')

    op.drop_index('idx_submission_type_lookup', table_name='submission_types')
    op.drop_table('submission_types')
