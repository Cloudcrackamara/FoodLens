import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Text
from sqlmodel import Field

from app.models.base import CreatedAtMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import FulfilmentMethod, OrderStatus


class WholesaleOrder(TimestampMixin, table=True):
    """Order request only. No payment fields, by design."""

    __tablename__ = "wholesale_order"
    __table_args__ = (
        CheckConstraint("buyer_company_id <> seller_company_id", name="buyer_not_seller"),
    )

    order_id: uuid.UUID = uuid_pk()
    buyer_company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    seller_company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    created_by_user_id: uuid.UUID = Field(foreign_key="app_user.user_id")
    pickup_location_id: uuid.UUID | None = Field(
        default=None, foreign_key="supplier_location.location_id"
    )
    fulfilment_method: FulfilmentMethod = Field(
        sa_type=enum_column(FulfilmentMethod, "fulfilment_method")
    )
    delivery_details: str | None = Field(default=None, sa_type=Text)
    status: OrderStatus = Field(
        default=OrderStatus.SUBMITTED, sa_type=enum_column(OrderStatus, "order_status")
    )
    buyer_note: str | None = Field(default=None, sa_type=Text)
    seller_note: str | None = Field(default=None, sa_type=Text)


class OrderLine(CreatedAtMixin, table=True):
    __tablename__ = "order_line"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    line_id: uuid.UUID = uuid_pk()
    order_id: uuid.UUID = Field(foreign_key="wholesale_order.order_id", index=True)
    product_id: uuid.UUID = Field(foreign_key="product.product_id", index=True)
    quantity: Decimal = Field(max_digits=12, decimal_places=3)
    unit: str


class OrderBatchAllocation(CreatedAtMixin, table=True):
    """Batch used to fulfil a line. The service checks the batch belongs to the line's product."""

    __tablename__ = "order_batch_allocation"
    __table_args__ = (
        CheckConstraint("allocated_quantity > 0", name="allocated_quantity_positive"),
    )

    allocation_id: uuid.UUID = uuid_pk()
    line_id: uuid.UUID = Field(foreign_key="order_line.line_id", index=True)
    batch_id: uuid.UUID = Field(foreign_key="product_batch.batch_id", index=True)
    allocated_quantity: Decimal = Field(max_digits=12, decimal_places=3)
