"""The declarative base and the constraint naming convention.

The naming convention has to exist BEFORE the first migration is generated. Add
it later and Postgres has already invented names like `comments_pkey`, so every
future migration that drops a constraint needs a hand-written RENAME first.

`%(column_0_N_name)s` is the multi-column token: it expands to every column in
the constraint. The single-column `%(column_0_name)s` would name D9's constraint
`uq_comments_post_id`, which says nothing about external_id and would collide
with any other unique constraint starting on post_id.
"""

from typing import Annotated

from sqlalchemy import BigInteger, Identity, MetaData
from sqlalchemy.orm import DeclarativeBase, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Every table's primary key. Identity() is the SQL-standard form and what
# SQLAlchemy 2 prefers over SERIAL; BigInteger because a viral post's comments
# are the row source and 2^31 is not a limit worth discovering in production.
PrimaryKey = Annotated[int, mapped_column(BigInteger, Identity(), primary_key=True)]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
