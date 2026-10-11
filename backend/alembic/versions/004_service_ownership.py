"""Associate monitored services with their creating operator."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_service_ownership"
down_revision: Union[str, None] = "003_service_lifecycle_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("services", sa.Column("owner_user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_services_owner_user_id_users",
        "services",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_services_owner_user_id", "services", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_services_owner_user_id", table_name="services")
    op.drop_constraint("fk_services_owner_user_id_users", "services", type_="foreignkey")
    op.drop_column("services", "owner_user_id")
