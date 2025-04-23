"""add wallet column

Revision ID: add_wallet_column
Revises: initial_migration
Create Date: 2024-04-16 19:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_wallet_column'
down_revision = 'initial_migration'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('wallet', sa.Integer(), nullable=False, server_default='20'))


def downgrade():
    op.drop_column('users', 'wallet') 