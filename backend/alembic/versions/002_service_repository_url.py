"""Add optional linked GitHub repository URL to monitored services."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_service_repository_url"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("services", sa.Column("repository_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("services", "repository_url")
