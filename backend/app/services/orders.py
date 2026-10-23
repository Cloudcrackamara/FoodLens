"""Wholesale order requests (CLAUDE.md rule 6, docs/DECISIONS.md D95-D99).

Rules:
- Buyer: the path company, approved, flagged as a distributor (D127). Seller: the company that
  owns the ordered products, listed in the partner directory. One seller per order; never the
  buyer.
- Lines: published products of that seller, quantity > 0, a unit. No prices or payments.
- Pickup from one of the seller's reviewed locations, or delivery with an address/notes.
- Status: REQUESTED -> ACCEPTED | DECLINED (seller) | CANCELLED (buyer); ACCEPTED -> FULFILLED
  (seller). Everything else is refused. The seller must still be approved to respond.
- Only the buyer and seller companies can see an order. Every action writes an audit entry.
"""

import uuid
from collections import defaultdict

from sqlmodel import Session, or_, select

from app.models import (
    Company,
    CompanyMember,
    OrderBatchAllocation,
    OrderLine,
    Product,
    ProductBatch,
    SupplierLocation,
    WholesaleOrder,
)
from app.models.enums import (
    CompanyReviewStatus,
    FulfilmentMethod,
    OrderStatus,
    ProductStatus,
    ReviewStatus,
)
from app.schemas.order import (
    AllocatedBatchRead,
    DeclineRequest,
    FulfilRequest,
    OrderCreateRequest,
    OrderLineRead,
    OrderPartyRead,
    OrderPickupRead,
    OrderRead,
    OrderRole,
    ReplyRequest,
)
from app.services import audit, suppliers
from app.services.companies import InvalidTransitionError, NotFoundError

TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.REQUESTED: {OrderStatus.ACCEPTED, OrderStatus.DECLINED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.FULFILLED},
}
REPLY_STATUSES = {OrderStatus.REQUESTED, OrderStatus.ACCEPTED}


class OrderRuleError(Exception):
    """The request breaks an order rule (shown to the user as a 422)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotAllowedError(Exception):
    """The company is a party to the order but may not take this action (403)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --- Placing ----------------------------------------------------------------------------------


def place_order(db: Session, member: CompanyMember, data: OrderCreateRequest) -> WholesaleOrder:
    buyer = db.get(Company, member.company_id)
    if buyer is None or buyer.review_status != CompanyReviewStatus.APPROVED:
        raise NotAllowedError("Your company can order after FoodLens approves its profile")
    if not buyer.is_distributor:
        raise NotAllowedError("Only distributor companies can send order requests")

    product_ids = [line.product_id for line in data.lines]
    if len(set(product_ids)) != len(product_ids):
        raise OrderRuleError("Each product can appear only once in an order")
    products = {
        p.product_id: p for p in db.exec(select(Product).where(Product.product_id.in_(product_ids)))
    }
    if len(products) != len(product_ids) or any(
        p.status != ProductStatus.PUBLISHED for p in products.values()
    ):
        raise OrderRuleError("Only published products can be ordered")
    sellers = {p.company_id for p in products.values()}
    if len(sellers) != 1:
        raise OrderRuleError("An order can only include products from one supplier")
    seller_id = sellers.pop()
    if seller_id == buyer.company_id:
        raise OrderRuleError("A company cannot order from itself")
    if not suppliers.is_listed(db, seller_id):
        raise OrderRuleError("This supplier is not taking order requests on FoodLens")

    pickup_location_id = None
    delivery_details = None
    if data.fulfilment_method == FulfilmentMethod.PICKUP:
        location = (
            db.get(SupplierLocation, data.pickup_location_id) if data.pickup_location_id else None
        )
        if (
            location is None
            or location.company_id != seller_id
            or location.review_status != ReviewStatus.APPROVED
        ):
            raise OrderRuleError("Choose one of the supplier's reviewed locations for pickup")
        pickup_location_id = location.location_id
    else:
        if not data.delivery_details or len(data.delivery_details) < 5:
            raise OrderRuleError("Enter a delivery address or delivery notes")
        delivery_details = data.delivery_details

    order = WholesaleOrder(
        buyer_company_id=buyer.company_id,
        seller_company_id=seller_id,
        created_by_user_id=member.user_id,
        fulfilment_method=data.fulfilment_method,
        pickup_location_id=pickup_location_id,
        delivery_details=delivery_details,
        buyer_note=data.buyer_note or None,
    )
    db.add(order)
    db.flush()
    for line in data.lines:
        db.add(
            OrderLine(
                order_id=order.order_id,
                product_id=line.product_id,
                quantity=line.quantity,
                unit=line.unit,
            )
        )
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="wholesale_order",
        entity_id=order.order_id,
        action="order_requested",
        new_values={"status": order.status.value, "lines": len(data.lines)},
    )
    db.commit()
    db.refresh(order)
    return order


# --- Reading ----------------------------------------------------------------------------------


def get_order(db: Session, company_id: uuid.UUID, order_id: uuid.UUID) -> WholesaleOrder:
    """The order, only if this company is its buyer or seller; otherwise NotFound (no leak)."""
    order = db.get(WholesaleOrder, order_id)
    if order is None or company_id not in (order.buyer_company_id, order.seller_company_id):
        raise NotFoundError
    return order


def orders_for_company(
    db: Session, company_id: uuid.UUID, role: OrderRole | None = None
) -> list[WholesaleOrder]:
    statement = select(WholesaleOrder).order_by(WholesaleOrder.created_at.desc())
    if role == OrderRole.BUYING:
        statement = statement.where(WholesaleOrder.buyer_company_id == company_id)
    elif role == OrderRole.SELLING:
        statement = statement.where(WholesaleOrder.seller_company_id == company_id)
    else:
        statement = statement.where(
            or_(
                WholesaleOrder.buyer_company_id == company_id,
                WholesaleOrder.seller_company_id == company_id,
            )
        )
    return list(db.exec(statement).all())


def order_reads(db: Session, orders: list[WholesaleOrder]) -> list[OrderRead]:
    if not orders:
        return []
    order_ids = [o.order_id for o in orders]
    company_ids = {o.buyer_company_id for o in orders} | {o.seller_company_id for o in orders}
    companies = {
        c.company_id: c for c in db.exec(select(Company).where(Company.company_id.in_(company_ids)))
    }
    location_ids = {o.pickup_location_id for o in orders if o.pickup_location_id}
    locations = (
        {
            loc.location_id: loc
            for loc in db.exec(
                select(SupplierLocation).where(SupplierLocation.location_id.in_(location_ids))
            )
        }
        if location_ids
        else {}
    )

    lines_by_order: dict = defaultdict(list)
    line_rows = db.exec(
        select(OrderLine, Product)
        .join(Product, Product.product_id == OrderLine.product_id)
        .where(OrderLine.order_id.in_(order_ids))
        .order_by(OrderLine.created_at, Product.name)
    ).all()
    line_ids = [line.line_id for line, _ in line_rows]
    batches_by_line: dict = defaultdict(list)
    if line_ids:
        for allocation, batch in db.exec(
            select(OrderBatchAllocation, ProductBatch)
            .join(ProductBatch, ProductBatch.batch_id == OrderBatchAllocation.batch_id)
            .where(OrderBatchAllocation.line_id.in_(line_ids))
            .order_by(ProductBatch.batch_number)
        ).all():
            batches_by_line[allocation.line_id].append(
                AllocatedBatchRead(
                    batch_id=batch.batch_id,
                    batch_number=batch.batch_number,
                    expiry_date=batch.expiry_date,
                )
            )
    for line, product in line_rows:
        lines_by_order[line.order_id].append(
            OrderLineRead(
                line_id=line.line_id,
                product_id=product.product_id,
                product_name=product.name,
                product_code=product.product_code,
                quantity=line.quantity,
                unit=line.unit,
                batches=batches_by_line[line.line_id],
            )
        )

    def party(company_id: uuid.UUID) -> OrderPartyRead:
        return OrderPartyRead(
            company_id=company_id, display_name=companies[company_id].display_name
        )

    reads = []
    for order in orders:
        location = locations.get(order.pickup_location_id) if order.pickup_location_id else None
        reads.append(
            OrderRead(
                order_id=order.order_id,
                status=order.status,
                buyer=party(order.buyer_company_id),
                seller=party(order.seller_company_id),
                fulfilment_method=order.fulfilment_method,
                pickup_location=OrderPickupRead(
                    location_id=location.location_id,
                    name=location.name,
                    address=location.address,
                    area=location.area,
                )
                if location
                else None,
                delivery_details=order.delivery_details,
                buyer_note=order.buyer_note,
                seller_note=order.seller_note,
                lines=lines_by_order[order.order_id],
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        )
    return reads


def order_read(db: Session, order: WholesaleOrder) -> OrderRead:
    return order_reads(db, [order])[0]


# --- Status changes ---------------------------------------------------------------------------


def _as_seller(db: Session, member: CompanyMember, order_id: uuid.UUID) -> WholesaleOrder:
    order = get_order(db, member.company_id, order_id)
    if order.seller_company_id != member.company_id:
        raise NotAllowedError("Only the supplier can respond to this order")
    seller = db.get(Company, member.company_id)
    if seller is None or seller.review_status != CompanyReviewStatus.APPROVED:
        raise NotAllowedError("Your company can respond to orders while its profile is approved")
    return order


def _move(
    db: Session,
    member: CompanyMember,
    order: WholesaleOrder,
    new_status: OrderStatus,
    action: str,
    extra: dict | None = None,
) -> WholesaleOrder:
    old_status = order.status
    if new_status not in TRANSITIONS.get(old_status, set()):
        raise InvalidTransitionError(
            f"An order that is {old_status.value.lower()} cannot become {new_status.value.lower()}"
        )
    order.status = new_status
    db.add(order)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="wholesale_order",
        entity_id=order.order_id,
        action=action,
        old_values={"status": old_status.value},
        new_values={"status": new_status.value} | (extra or {}),
    )
    db.commit()
    db.refresh(order)
    return order


def accept(db: Session, member: CompanyMember, order_id: uuid.UUID) -> WholesaleOrder:
    order = _as_seller(db, member, order_id)
    return _move(db, member, order, OrderStatus.ACCEPTED, "order_accepted")


def decline(
    db: Session, member: CompanyMember, order_id: uuid.UUID, data: DeclineRequest
) -> WholesaleOrder:
    order = _as_seller(db, member, order_id)
    if data.reason:
        order.seller_note = data.reason
    return _move(
        db, member, order, OrderStatus.DECLINED, "order_declined", {"reason": data.reason or None}
    )


def reply(
    db: Session, member: CompanyMember, order_id: uuid.UUID, data: ReplyRequest
) -> WholesaleOrder:
    """Short message from the seller; the latest one is shown (D98)."""
    order = _as_seller(db, member, order_id)
    if order.status not in REPLY_STATUSES:
        raise InvalidTransitionError("You can reply while an order is requested or accepted")
    old_note = order.seller_note
    order.seller_note = data.message
    db.add(order)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="wholesale_order",
        entity_id=order.order_id,
        action="order_replied",
        old_values={"seller_note": old_note},
        new_values={"seller_note": data.message},
    )
    db.commit()
    db.refresh(order)
    return order


def fulfil(
    db: Session, member: CompanyMember, order_id: uuid.UUID, data: FulfilRequest
) -> WholesaleOrder:
    """Mark fulfilled, optionally linking each line to the seller's own batches of that product."""
    order = _as_seller(db, member, order_id)
    if order.status != OrderStatus.ACCEPTED:
        raise InvalidTransitionError(
            f"An order that is {order.status.value.lower()} cannot become fulfilled"
        )
    lines = {
        line.line_id: line
        for line in db.exec(select(OrderLine).where(OrderLine.order_id == order.order_id))
    }
    allocations: list[OrderBatchAllocation] = []
    for item in data.allocations:
        line = lines.get(item.line_id)
        if line is None:
            raise OrderRuleError("A batch was linked to a line that is not in this order")
        for batch_id in dict.fromkeys(item.batch_ids):
            batch = db.get(ProductBatch, batch_id)
            product = db.get(Product, batch.product_id) if batch else None
            if (
                batch is None
                or product is None
                or batch.product_id != line.product_id
                or product.company_id != order.seller_company_id
                or batch.review_status != ReviewStatus.APPROVED
            ):
                raise OrderRuleError("Link only your own batches of the product on that line")
            allocations.append(OrderBatchAllocation(line_id=line.line_id, batch_id=batch_id))
    for allocation in allocations:
        db.add(allocation)
    return _move(
        db,
        member,
        order,
        OrderStatus.FULFILLED,
        "order_fulfilled",
        {"batches_linked": len(allocations)},
    )


def cancel(db: Session, member: CompanyMember, order_id: uuid.UUID) -> WholesaleOrder:
    order = get_order(db, member.company_id, order_id)
    if order.buyer_company_id != member.company_id:
        raise NotAllowedError("Only the company that sent the order can cancel it")
    if order.status != OrderStatus.REQUESTED:
        raise InvalidTransitionError("An order can only be cancelled while it is requested")
    return _move(db, member, order, OrderStatus.CANCELLED, "order_cancelled")
