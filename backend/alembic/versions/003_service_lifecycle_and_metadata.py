"""Add service metadata and an explicit active lifecycle state."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_service_lifecycle_metadata"
down_revision: Union[str, None] = "002_service_repository_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("services", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("services", sa.Column("framework", sa.String(length=80), nullable=True))
    op.add_column("services", sa.Column("language", sa.String(length=40), nullable=True))
    op.add_column("services", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    op.drop_column("services", "is_active")
    op.drop_column("services", "language")
    op.drop_column("services", "framework")
    op.drop_column("services", "description")
