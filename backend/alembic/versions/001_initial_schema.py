"""Initial schema — all V1 tables

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tenants ───────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subdomain", sa.String(100), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── depots ────────────────────────────────────────────────────────────────
    op.create_table(
        "depots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_depots_tenant_id", "depots", ["tenant_id"])
    op.create_index("ix_depots_tenant_name", "depots", ["tenant_id", "name"], unique=True)

    # ── stores ────────────────────────────────────────────────────────────────
    op.create_table(
        "stores",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_stores_tenant_id", "stores", ["tenant_id"])
    op.create_index("ix_stores_tenant_name", "stores", ["tenant_id", "name"], unique=True)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="store_staff"),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("depot_id", sa.Uuid(), sa.ForeignKey("depots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_tenant_email", "users", ["tenant_id", "email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_role", "users", ["role"])

    # ── transfer_orders ───────────────────────────────────────────────────────
    op.create_table(
        "transfer_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depot_id", sa.Uuid(), sa.ForeignKey("depots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("to_number", sa.String(100), nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_expected_qty", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("imported_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("import_filename", sa.String(255), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_to_tenant_id", "transfer_orders", ["tenant_id"])
    op.create_index("ix_to_store_id", "transfer_orders", ["store_id"])
    op.create_index("ix_to_depot_id", "transfer_orders", ["depot_id"])
    op.create_index("ix_to_status", "transfer_orders", ["status"])
    op.create_index("ix_to_number", "transfer_orders", ["to_number"])
    op.create_index("ix_to_tenant_status", "transfer_orders", ["tenant_id", "status"])

    # ── transfer_order_items ──────────────────────────────────────────────────
    op.create_table(
        "transfer_order_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("transfer_order_id", sa.Uuid(), sa.ForeignKey("transfer_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(500), nullable=False),
        sa.Column("expected_qty", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 4), nullable=True),
        sa.Column("depot_stock", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_toi_transfer_order_id", "transfer_order_items", ["transfer_order_id"])
    op.create_index("ix_toi_item_name", "transfer_order_items", ["item_name"])

    # ── inward_sessions ───────────────────────────────────────────────────────
    op.create_table(
        "inward_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transfer_order_id", sa.Uuid(), sa.ForeignKey("transfer_orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_inward_sessions_transfer_order_id", "inward_sessions", ["transfer_order_id"], unique=True)
    op.create_index("ix_inward_sessions_store_id", "inward_sessions", ["store_id"])
    op.create_index("ix_inward_sessions_status", "inward_sessions", ["status"])
    op.create_index("ix_inward_sessions_tenant_id", "inward_sessions", ["tenant_id"])

    # ── inward_session_participants ───────────────────────────────────────────
    op.create_table(
        "inward_session_participants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("inward_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("session_id", "user_id", name="uq_session_participant"),
    )
    op.create_index("ix_isp_session_id", "inward_session_participants", ["session_id"])

    # ── inward_items ──────────────────────────────────────────────────────────
    op.create_table(
        "inward_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("inward_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transfer_item_id", sa.Uuid(), sa.ForeignKey("transfer_order_items.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(500), nullable=False),
        sa.Column("expected_qty", sa.Numeric(12, 2), nullable=False),
        sa.Column("received_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("variance", sa.Numeric(12, 2), nullable=True),
        sa.Column("variance_type", sa.String(20), nullable=True),
        sa.Column("verified_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_inward_items_session_id", "inward_items", ["session_id"])
    op.create_index("ix_inward_items_transfer_item_id", "inward_items", ["transfer_item_id"], unique=True)
    op.create_index("ix_inward_items_variance_type", "inward_items", ["variance_type"])

    # ── file_uploads ──────────────────────────────────────────────────────────
    op.create_table(
        "file_uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("bucket", sa.String(255), nullable=False),
        sa.Column("key", sa.String(1024), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_file_uploads_tenant_id", "file_uploads", ["tenant_id"])

    # ── discrepancies ─────────────────────────────────────────────────────────
    op.create_table(
        "discrepancies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inward_item_id", sa.Uuid(), sa.ForeignKey("inward_items.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("transfer_order_id", sa.Uuid(), sa.ForeignKey("transfer_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depot_id", sa.Uuid(), sa.ForeignKey("depots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("raised_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("expected_qty", sa.Numeric(12, 2), nullable=False),
        sa.Column("received_qty", sa.Numeric(12, 2), nullable=False),
        sa.Column("variance_qty", sa.Numeric(12, 2), nullable=False),
        sa.Column("item_name", sa.String(500), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("depot_response", sa.Text(), nullable=True),
        sa.Column("depot_responded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("depot_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_disc_tenant_id", "discrepancies", ["tenant_id"])
    op.create_index("ix_disc_inward_item_id", "discrepancies", ["inward_item_id"], unique=True)
    op.create_index("ix_disc_transfer_order_id", "discrepancies", ["transfer_order_id"])
    op.create_index("ix_disc_depot_id", "discrepancies", ["depot_id"])
    op.create_index("ix_disc_status", "discrepancies", ["status"])
    op.create_index("ix_disc_type", "discrepancies", ["type"])
    op.create_index("ix_disc_created_at", "discrepancies", ["created_at"])

    # ── discrepancy_comments ──────────────────────────────────────────────────
    op.create_table(
        "discrepancy_comments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("discrepancy_id", sa.Uuid(), sa.ForeignKey("discrepancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_dc_discrepancy_id", "discrepancy_comments", ["discrepancy_id"])

    # ── discrepancy_attachments ───────────────────────────────────────────────
    op.create_table(
        "discrepancy_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("discrepancy_id", sa.Uuid(), sa.ForeignKey("discrepancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_upload_id", sa.Uuid(), sa.ForeignKey("file_uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_da_discrepancy_id", "discrepancy_attachments", ["discrepancy_id"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("entity_label", sa.String(255), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_notif_recipient_id", "notifications", ["recipient_id"])
    op.create_index("ix_notif_read_at", "notifications", ["read_at"])
    op.create_index("ix_notif_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("discrepancy_attachments")
    op.drop_table("discrepancy_comments")
    op.drop_table("discrepancies")
    op.drop_table("file_uploads")
    op.drop_table("inward_items")
    op.drop_table("inward_session_participants")
    op.drop_table("inward_sessions")
    op.drop_table("transfer_order_items")
    op.drop_table("transfer_orders")
    op.drop_table("users")
    op.drop_table("stores")
    op.drop_table("depots")
    op.drop_table("tenants")
