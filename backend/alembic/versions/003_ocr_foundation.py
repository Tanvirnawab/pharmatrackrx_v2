"""OCR foundation

Revision ID: 003
Revises: 002
Create Date: 2026-06-04 18:15:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("ocr_jobs"):
        op.create_table(
        "ocr_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_upload_id", sa.Uuid(), sa.ForeignKey("file_uploads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transfer_order_id", sa.Uuid(), sa.ForeignKey("transfer_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("engine", sa.String(50), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    _create_index_if_missing("ocr_jobs", "ix_ocr_jobs_tenant_id", ["tenant_id"])
    _create_index_if_missing("ocr_jobs", "ix_ocr_jobs_status", ["status"])
    _create_index_if_missing("ocr_jobs", "ix_ocr_jobs_transfer_order_id", ["transfer_order_id"])
    _create_index_if_missing("ocr_jobs", "ix_ocr_jobs_created_at", ["created_at"])

    if not inspector.has_table("ocr_results"):
        op.create_table(
        "ocr_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("ocr_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("medicine_name", sa.String(500), nullable=True),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("pack_size", sa.String(100), nullable=True),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("corrected_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    _create_index_if_missing("ocr_results", "ix_ocr_results_job_id", ["job_id"])
    _create_index_if_missing("ocr_results", "ix_ocr_results_item_name", ["medicine_name"])
    _create_index_if_missing("ocr_results", "ix_ocr_results_batch_number", ["batch_number"])
    _create_index_if_missing("ocr_results", "ix_ocr_results_expiry_date", ["expiry_date"])

    if not inspector.has_table("ocr_match_results"):
        op.create_table(
        "ocr_match_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("ocr_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ocr_result_id", sa.Uuid(), sa.ForeignKey("ocr_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transfer_item_id", sa.Uuid(), sa.ForeignKey("transfer_order_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("match_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("mismatch_fields", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    _create_index_if_missing("ocr_match_results", "ix_ocr_match_results_job_id", ["job_id"])
    _create_index_if_missing("ocr_match_results", "ix_ocr_match_results_ocr_result_id", ["ocr_result_id"])
    _create_index_if_missing("ocr_match_results", "ix_ocr_match_results_transfer_item_id", ["transfer_item_id"])
    _create_index_if_missing("ocr_match_results", "ix_ocr_match_results_status", ["match_status"])


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    inspector = inspect(op.get_bind())
    existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    op.drop_table("ocr_match_results")
    op.drop_table("ocr_results")
    op.drop_table("ocr_jobs")
