"""one reply draft per comment

Revision ID: 4720ee0c2e61
Revises: 3f7edd645b32
Create Date: 2026-09-09 22:45:27.553701

The application already assumed this: `GET /comments/{id}` reads the draft with
`scalar_one_or_none()` and `CommentWithDraft.draft` is singular. A 300-comment
replay produced a second draft for one comment — the orchestrator's guard is
check-then-act, so two overlapping attempts both read `new` — and that endpoint
then returned 500 while the Inbox listed the comment twice.

The guard now takes a row lock. This constraint is the backstop: it turns the
same race from a silent duplicate into a failed job with a visible error.

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4720ee0c2e61'
down_revision: Union[str, Sequence[str], None] = '3f7edd645b32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing duplicates have to go first, or ADD CONSTRAINT fails. Keeping the
    # LOWEST id keeps the draft a human may already have seen and acted on; the
    # later one is the artefact of the re-run. This deletes data, deliberately
    # and narrowly: rows the application could not render anyway, since the
    # endpoint that reads them raised on more than one.
    op.execute(
        sa.text(
            """
            DELETE FROM reply_drafts d
            USING reply_drafts keep
            WHERE d.comment_id = keep.comment_id
              AND d.id > keep.id
            """
        )
    )

    # The unique constraint is backed by a unique index, so dropping the plain
    # index loses no lookup performance on comment_id.
    op.drop_index(op.f('ix_reply_drafts_comment_id'), table_name='reply_drafts')
    op.create_unique_constraint('one_draft_per_comment', 'reply_drafts', ['comment_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('one_draft_per_comment', 'reply_drafts', type_='unique')
    op.create_index(
        op.f('ix_reply_drafts_comment_id'), 'reply_drafts', ['comment_id'], unique=False
    )
