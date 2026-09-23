"""analytics summaries

Revision ID: c3d4e5f6a7b8
Revises: b7c1d2e3f4a5
Create Date: 2026-09-23

The analytics agent's weekly summaries. Also widens agent_runs.agent's CHECK to
allow 'analytics' (app/enums.py::AgentName). Alembic's autogenerate does not
diff CHECK constraint bodies, so this is written by hand, as in 792ac3d5d638.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b7c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITHOUT = "agent IN ('triage', 'response', 'content', 'media', 'ideation', 'insight')"
_WITH = "agent IN ('triage', 'response', 'content', 'media', 'ideation', 'insight', 'analytics')"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f('ck_agent_runs_agent_allowed'), 'agent_runs', type_='check')
    op.create_check_constraint(op.f('ck_agent_runs_agent_allowed'), 'agent_runs', _WITH)

    op.create_table('analytics_summaries',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('brand_id', sa.BigInteger(), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('stats_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('agent_run_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id'], name=op.f('fk_analytics_summaries_agent_run_id_agent_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], name=op.f('fk_analytics_summaries_brand_id_brands'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_analytics_summaries'))
    )
    op.create_index(op.f('ix_analytics_summaries_brand_id'), 'analytics_summaries', ['brand_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_analytics_summaries_brand_id'), table_name='analytics_summaries')
    op.drop_table('analytics_summaries')
    op.drop_constraint(op.f('ck_agent_runs_agent_allowed'), 'agent_runs', type_='check')
    op.create_check_constraint(op.f('ck_agent_runs_agent_allowed'), 'agent_runs', _WITHOUT)
