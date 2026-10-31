"""Initial schema for all 27 platform tables.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-10-30 22:00:00
"""

from typing import Sequence, Union
from alembic import op
from app.core.database import Base
import app.models  # noqa: F401

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
