import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PaymentStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PaymentCurrency(str, enum.Enum):
    USD = "USD"


def _enum_values(enum_cls):
    # Store the enum *values* ('success', 'USD') rather than the member names
    return [e.value for e in enum_cls]


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="payments_amount_cents_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[PaymentCurrency] = mapped_column(
        ENUM(
            PaymentCurrency,
            name="payment_currency",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
        default=PaymentCurrency.USD,
        server_default=text("'USD'"),
    )
    status: Mapped[PaymentStatus] = mapped_column(
        ENUM(
            PaymentStatus,
            name="payment_status",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_last4: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} booking_id={self.booking_id} "
            f"{self.amount_cents}c {self.currency.value} {self.status.value}>"
        )
