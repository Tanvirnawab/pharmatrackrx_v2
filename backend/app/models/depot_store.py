import uuid
from sqlalchemy import String, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID
from app.db.base import Base, UUIDMixin, TimestampMixin


class Depot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "depots"
    __table_args__ = (
        Index("ix_depots_tenant_id", "tenant_id"),
        Index("ix_depots_tenant_name", "tenant_id", "name", unique=True),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Code auto-derived from AExpert transfer number prefix (e.g., "MATD" from "26MATD/STR/...")
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="depots")
    transfer_orders: Mapped[list["TransferOrder"]] = relationship(
        "TransferOrder", back_populates="depot"
    )

    def __repr__(self):
        return f"<Depot {self.name}>"


class Store(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stores"
    __table_args__ = (
        Index("ix_stores_tenant_id", "tenant_id"),
        Index("ix_stores_tenant_name", "tenant_id", "name", unique=True),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="stores")
    transfer_orders: Mapped[list["TransferOrder"]] = relationship(
        "TransferOrder", back_populates="store"
    )
    inward_sessions: Mapped[list["InwardSession"]] = relationship(
        "InwardSession", back_populates="store"
    )

    def __repr__(self):
        return f"<Store {self.name}>"
