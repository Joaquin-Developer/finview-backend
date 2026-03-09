import uuid
from datetime import datetime, date

from sqlalchemy import DATE, DECIMAL, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    statement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(DATE, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="UYU")
    category_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_source: Mapped[str | None] = mapped_column(String(10), nullable=True)
    installment_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installment_tot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    statement: Mapped["Statement"] = relationship("Statement", back_populates="transactions")
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")

