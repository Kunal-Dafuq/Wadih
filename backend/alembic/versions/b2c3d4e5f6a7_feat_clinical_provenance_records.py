"""feat(clinical): create clinical_residual_risk_records table for server-side provenance

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-28 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'clinical_residual_risk_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('condition_code', sa.String(length=64), nullable=False),
        sa.Column('residual_carrier_probability', sa.Float(), nullable=False),
        sa.Column('clinical_source_reference', sa.String(length=255), nullable=False),
        sa.Column('reviewing_clinician_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['screening_cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewing_clinician_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_clinical_residual_risk_records_case_id'),
        'clinical_residual_risk_records',
        ['case_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_clinical_residual_risk_records_condition_code'),
        'clinical_residual_risk_records',
        ['condition_code'],
        unique=False,
    )
    op.create_index(
        op.f('ix_clinical_residual_risk_records_id'),
        'clinical_residual_risk_records',
        ['id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_clinical_residual_risk_records_id'), table_name='clinical_residual_risk_records')
    op.drop_index(op.f('ix_clinical_residual_risk_records_condition_code'), table_name='clinical_residual_risk_records')
    op.drop_index(op.f('ix_clinical_residual_risk_records_case_id'), table_name='clinical_residual_risk_records')
    op.drop_table('clinical_residual_risk_records')
