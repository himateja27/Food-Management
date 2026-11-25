"""add domain checks

Revision ID: 41ea1fee7da9
Revises: 1b3bb5b70289
Create Date: 2026-11-25 10:39:06.333200
"""
from alembic import op
import sqlalchemy as sa


revision = '41ea1fee7da9'
down_revision = '1b3bb5b70289'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_check_constraint("ck_users_role", "role IN ('USER', 'ADMIN')")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.create_check_constraint(
            "ck_orders_status",
            "status IN ('PLACED', 'ACCEPTED', 'PREPARING', 'READY', 'COMPLETED', 'CANCELLED')",
        )
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.create_check_constraint("ck_chat_messages_role", "role IN ('USER', 'ASSISTANT')")
        batch_op.create_check_constraint(
            "ck_chat_messages_mode",
            "mode IS NULL OR mode IN ('GENERAL', 'RAG', 'AGENT', 'MIXED')",
        )
    with op.batch_alter_table("pending_actions") as batch_op:
        batch_op.create_check_constraint("ck_pending_action_type", "action_type IN ('CREATE_ORDER', 'CANCEL_ORDER')")
        batch_op.create_check_constraint(
            "ck_pending_action_status",
            "status IN ('PENDING', 'PROCESSING', 'CONFIRMED', 'REJECTED', 'EXPIRED')",
        )
    with op.batch_alter_table("documents") as batch_op:
        batch_op.create_check_constraint("ck_documents_positive_version", "version > 0")


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("ck_documents_positive_version", type_="check")
    with op.batch_alter_table("pending_actions") as batch_op:
        batch_op.drop_constraint("ck_pending_action_status", type_="check")
        batch_op.drop_constraint("ck_pending_action_type", type_="check")
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_constraint("ck_chat_messages_mode", type_="check")
        batch_op.drop_constraint("ck_chat_messages_role", type_="check")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("ck_orders_status", type_="check")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
