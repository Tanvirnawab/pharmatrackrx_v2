import uuid
from sqlalchemy import String, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin


class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subdomain: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    depots: Mapped[list["Depot"]] = relationship("Depot", back_populates="tenant")
    stores: Mapped[list["Store"]] = relationship("Store", back_populates="tenant")
    transfer_orders: Mapped[list["TransferOrder"]] = relationship(
        "TransferOrder", back_populates="tenant"
    )

    def __repr__(self):
        return f"<Tenant {self.name}>"
