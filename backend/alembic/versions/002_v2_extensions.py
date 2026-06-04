"""V2 extensions — barcode, batch registry, OCR columns

Revision ID: 002
Revises: 001
Create Date: 2026-01-02 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend inward_items with V2 barcode/OCR/batch fields ─────────────────
    op.add_column("inward_items", sa.Column("barcode_value", sa.String(500), nullable=True))
    op.add_column("inward_items", sa.Column("barcode_type", sa.String(50), nullable=True))
    # 'match' | 'mismatch' | 'unknown' | null = not scanned
    op.add_column("inward_items", sa.Column("scan_result", sa.String(20), nullable=True))
    op.add_column("inward_items", sa.Column("batch_number", sa.String(100), nullable=True))
    # OCR suggestion (not yet confirmed by user)
    op.add_column("inward_items", sa.Column("ocr_suggested_expiry", sa.Date(), nullable=True))
    op.add_column("inward_items", sa.Column("ocr_raw_text", sa.Text(), nullable=True))

    op.create_index("ix_inward_items_scan_result", "inward_items", ["scan_result"])

    # ── batch_records — optional multi-batch detail per medicine line ─────────
    op.create_table(
        "batch_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inward_item_id", sa.Uuid(), sa.ForeignKey("inward_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("barcode_value", sa.String(500), nullable=True),
        # 'scan' | 'manual' | 'ocr' | 'import'
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_batch_records_inward_item_id", "batch_records", ["inward_item_id"])
    op.create_index("ix_batch_records_tenant_id", "batch_records", ["tenant_id"])
    op.create_index("ix_batch_records_batch_number", "batch_records", ["batch_number"])
    op.create_index("ix_batch_records_expiry_date", "batch_records", ["expiry_date"])


def downgrade() -> None:
    op.drop_table("batch_records")
    op.drop_index("ix_inward_items_scan_result", table_name="inward_items")
    op.drop_column("inward_items", "ocr_raw_text")
    op.drop_column("inward_items", "ocr_suggested_expiry")
    op.drop_column("inward_items", "batch_number")
    op.drop_column("inward_items", "scan_result")
    op.drop_column("inward_items", "barcode_type")
    op.drop_column("inward_items", "barcode_value")
