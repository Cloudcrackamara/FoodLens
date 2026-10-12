"""Wholesale order request routes. Thin: rules live in app/services/orders.py (D95-D99).

The path company must be the signed-in user's company (require_company_member); an order is
only visible to its buyer and seller companies (404 for anyone else).
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import require_company_member
from app.core.db import DbSession
from app.models import CompanyMember, WholesaleOrder
from app.schemas.order import (
    DeclineRequest,
    FulfilRequest,
    OrderCreateRequest,
    OrderRead,
    OrderRole,
    ReplyRequest,
)
from app.services import orders as order_service
from app.services.companies import InvalidTransitionError, NotFoundError

router = APIRouter(prefix="/api/companies/{company_id}/orders", tags=["orders"])

Member = Annotated[CompanyMember, Depends(require_company_member())]


def _run(db: DbSession, action: Callable[[], WholesaleOrder]) -> OrderRead:
    try:
        order = action()
    except NotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from None
    except order_service.NotAllowedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.message) from None
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from None
    except order_service.OrderRuleError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message) from None
    return order_service.order_read(db, order)


@router.post("", status_code=status.HTTP_201_CREATED)
def place_order(
    company_id: uuid.UUID, body: OrderCreateRequest, member: Member, db: DbSession
) -> OrderRead:
    return _run(db, lambda: order_service.place_order(db, member, body))


@router.get("")
def list_orders(
    company_id: uuid.UUID,
    member: Member,
    db: DbSession,
    role: Annotated[OrderRole | None, Query()] = None,
) -> list[OrderRead]:
    orders = order_service.orders_for_company(db, member.company_id, role)
    return order_service.order_reads(db, orders)


@router.get("/{order_id}")
def get_order(
    company_id: uuid.UUID, order_id: uuid.UUID, member: Member, db: DbSession
) -> OrderRead:
    return _run(db, lambda: order_service.get_order(db, member.company_id, order_id))


@router.post("/{order_id}/accept")
def accept(company_id: uuid.UUID, order_id: uuid.UUID, member: Member, db: DbSession) -> OrderRead:
    return _run(db, lambda: order_service.accept(db, member, order_id))


@router.post("/{order_id}/decline")
def decline(
    company_id: uuid.UUID,
    order_id: uuid.UUID,
    body: DeclineRequest,
    member: Member,
    db: DbSession,
) -> OrderRead:
    return _run(db, lambda: order_service.decline(db, member, order_id, body))


@router.post("/{order_id}/reply")
def reply(
    company_id: uuid.UUID,
    order_id: uuid.UUID,
    body: ReplyRequest,
    member: Member,
    db: DbSession,
) -> OrderRead:
    return _run(db, lambda: order_service.reply(db, member, order_id, body))


@router.post("/{order_id}/fulfil")
def fulfil(
    company_id: uuid.UUID,
    order_id: uuid.UUID,
    body: FulfilRequest,
    member: Member,
    db: DbSession,
) -> OrderRead:
    return _run(db, lambda: order_service.fulfil(db, member, order_id, body))


@router.post("/{order_id}/cancel")
def cancel(company_id: uuid.UUID, order_id: uuid.UUID, member: Member, db: DbSession) -> OrderRead:
    return _run(db, lambda: order_service.cancel(db, member, order_id))
