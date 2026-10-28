"""feat(consent-audit): add purpose, terms_version, case_id, expires_at to consents and outcome, request_id to audit logs

Revision ID: a1b2c3d4e5f6
Revises: 95f8e66654a2
Create Date: 2026-10-28 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '95f8e66654a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to shared_consent_grants
    op.add_column('shared_consent_grants', sa.Column('purpose', sa.String(length=128), nullable=True))
    op.add_column('shared_consent_grants', sa.Column('terms_version', sa.String(length=32), nullable=True, server_default='v1.0'))
    op.add_column('shared_consent_grants', sa.Column('case_id', sa.Integer(), nullable=True))
    op.add_column('shared_consent_grants', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))

    # Add new columns to shared_audit_logs
    op.add_column('shared_audit_logs', sa.Column('outcome', sa.String(length=32), nullable=True, server_default='SUCCESS'))
    op.add_column('shared_audit_logs', sa.Column('request_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('shared_audit_logs', 'request_id')
    op.drop_column('shared_audit_logs', 'outcome')
    op.drop_column('shared_consent_grants', 'expires_at')
    op.drop_column('shared_consent_grants', 'case_id')
    op.drop_column('shared_consent_grants', 'terms_version')
    op.drop_column('shared_consent_grants', 'purpose')
