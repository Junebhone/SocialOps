"""brand timezone

Revision ID: b7c1d2e3f4a5
Revises: 792ac3d5d638
Create Date: 2026-09-23

ADR-0005: analytics buckets days in each brand's own time zone.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c1d2e3f4a5'
down_revision: Union[str, Sequence[str], None] = '792ac3d5d638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'brands',
        sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('brands', 'timezone')
