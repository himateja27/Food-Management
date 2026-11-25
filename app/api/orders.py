from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AdminUser, CurrentUser
from app.models import User
from app.schemas.orders import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.orders import OrderService

router = APIRouter(prefix="/api/orders", tags=["orders"])
DbSession = Annotated[Session, Depends(get_db)]


def require_idempotency_key(
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128, description="Stable key reused for retries of the same write")],
) -> str:
    return key


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED, summary="Create an order")
def create_order(data: OrderCreate, session: DbSession, user: CurrentUser, idempotency_key: Annotated[str, Depends(require_idempotency_key)]) -> OrderRead:
    return OrderService(session).create_order(user.id, data, idempotency_key)


@router.get("", response_model=list[OrderRead], summary="List the authenticated user's orders")
def list_orders(session: DbSession, user: CurrentUser) -> list[OrderRead]:
    return OrderService(session).list_orders(user.id)


@router.get("/{order_id}", response_model=OrderRead, summary="Get an owned order")
def get_order(order_id: Annotated[int, Path(gt=0)], session: DbSession, user: CurrentUser) -> OrderRead:
    return OrderService(session).get_order(order_id, user.id)


@router.post("/{order_id}/cancel", response_model=OrderRead, summary="Cancel an owned order before preparation")
def cancel_order(
    order_id: Annotated[int, Path(gt=0)],
    session: DbSession,
    user: CurrentUser,
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> OrderRead:
    return OrderService(session).cancel_order(order_id, user.id, idempotency_key)


admin_router = APIRouter(prefix="/api/admin/orders", tags=["admin"])


@admin_router.get("", response_model=list[OrderRead], summary="List orders for the admin desk")
def list_all_orders(session: DbSession, _: AdminUser) -> list[OrderRead]:
    return OrderService(session).list_all_orders()


@admin_router.patch("/{order_id}/status", response_model=OrderRead, summary="Change order status (admin)")
def change_order_status(
    order_id: Annotated[int, Path(gt=0)],
    data: OrderStatusUpdate,
    session: DbSession,
    _: AdminUser,
) -> OrderRead:
    return OrderService(session).change_status(order_id, data.status)
