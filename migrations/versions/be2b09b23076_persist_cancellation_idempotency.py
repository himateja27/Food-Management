"""persist cancellation idempotency

Revision ID: be2b09b23076
Revises: 41ea1fee7da9
Create Date: 2026-11-25 10:45:43.531290
"""
from alembic import op
import sqlalchemy as sa


revision = 'be2b09b23076'
down_revision = '41ea1fee7da9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("cancel_idempotency_key", sa.String(length=128), nullable=True))
        batch_op.create_unique_constraint(
            "uq_orders_user_cancel_idempotency",
            ["user_id", "cancel_idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("uq_orders_user_cancel_idempotency", type_="unique")
        batch_op.drop_column("cancel_idempotency_key")
