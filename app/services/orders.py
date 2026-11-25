from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Order, OrderLine
from app.repositories.orders import OrderRepository
from app.schemas.orders import OrderCreate

CANCELLABLE_STATUSES = {"PLACED", "ACCEPTED"}
STATUS_TRANSITIONS = {
    "PLACED": {"ACCEPTED", "CANCELLED"},
    "ACCEPTED": {"PREPARING", "CANCELLED"},
    "PREPARING": {"READY"},
    "READY": {"COMPLETED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class BusinessRuleError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class OrderService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = OrderRepository(session)

    def create_order(
        self,
        user_id: int,
        data: OrderCreate,
        idempotency_key: str,
        expected_prices: dict[int, Decimal] | None = None,
    ) -> Order:
        prior = self.repository.by_idempotency_key(user_id, idempotency_key)
        if prior is not None:
            return prior
        quantities: dict[int, int] = {}
        for line in data.items:
            quantities[line.menu_item_id] = quantities.get(line.menu_item_id, 0) + line.quantity
        if any(quantity > 10 for quantity in quantities.values()):
            raise BusinessRuleError("INVALID_QUANTITY", "Combined quantity for an item cannot exceed 10", 422)
        try:
            locked_items = {item_id: self.repository.lock_menu_item(item_id) for item_id in sorted(quantities)}
            prior = self.repository.by_idempotency_key(user_id, idempotency_key, lock=True)
            if prior is not None:
                self.session.rollback()
                return prior
            for item_id, quantity in quantities.items():
                item = locked_items[item_id]
                if item is None or not item.is_active:
                    raise BusinessRuleError("MENU_ITEM_UNAVAILABLE", "One or more menu items are unavailable", 404)
                if item.capacity < quantity:
                    raise BusinessRuleError("INSUFFICIENT_CAPACITY", f"Not enough portions available for {item.title}")
                if expected_prices is not None and item.price != expected_prices.get(item_id):
                    raise BusinessRuleError("TERMS_CHANGED", "Menu prices changed; review and confirm the updated terms")
            total = sum((locked_items[item_id].price * quantity for item_id, quantity in quantities.items()), Decimal("0.00"))
            order = Order(user_id=user_id, idempotency_key=idempotency_key, status="PLACED", total_amount=total)
            order.lines = [
                OrderLine(
                    menu_item_id=item_id,
                    item_title_snapshot=locked_items[item_id].title,
                    quantity=quantity,
                    unit_price_snapshot=locked_items[item_id].price,
                )
                for item_id, quantity in sorted(quantities.items())
            ]
            for item_id, quantity in quantities.items():
                locked_items[item_id].capacity -= quantity
            self.session.add(order)
            self.session.commit()
            self.session.refresh(order)
            return order
        except IntegrityError:
            self.session.rollback()
            prior = self.repository.by_idempotency_key(user_id, idempotency_key)
            if prior is not None:
                return prior
            raise BusinessRuleError("ORDER_CONFLICT", "Order could not be created; retry with the same idempotency key")
        except Exception:
            self.session.rollback()
            raise

    def list_orders(self, user_id: int) -> list[Order]:
        return self.repository.list_for_user(user_id)

    def list_all_orders(self) -> list[Order]:
        return self.repository.list_all()

    def get_order(self, order_id: int, user_id: int) -> Order:
        order = self.repository.get_for_user(order_id, user_id)
        if order is None:
            raise LookupError("Order not found")
        return order

    def cancel_order(self, order_id: int, user_id: int, idempotency_key: str | None = None) -> Order:
        order = self.repository.get_for_user(order_id, user_id, lock=True)
        if order is None:
            raise LookupError("Order not found")
        if order.status == "CANCELLED":
            if idempotency_key is not None and order.cancel_idempotency_key not in {None, idempotency_key}:
                raise BusinessRuleError("CANCELLATION_ALREADY_COMPLETED", "This order has already been cancelled", 409)
            return order
        if order.status not in CANCELLABLE_STATUSES:
            raise BusinessRuleError("CANCELLATION_NOT_ALLOWED", "Orders cannot be cancelled after preparation begins")
        try:
            for line in order.lines:
                item = self.repository.lock_menu_item(line.menu_item_id)
                if item is not None:
                    item.capacity += line.quantity
            order.status = "CANCELLED"
            order.cancel_idempotency_key = idempotency_key
            self.session.commit()
            return order
        except Exception:
            self.session.rollback()
            raise

    def change_status(self, order_id: int, status: str) -> Order:
        order = self.repository.get_by_id(order_id, lock=True)
        if order is None:
            raise LookupError("Order not found")
        if status not in STATUS_TRANSITIONS.get(order.status, set()):
            raise BusinessRuleError("INVALID_STATUS_TRANSITION", f"Cannot transition an order from {order.status} to {status}")
        try:
            if status == "CANCELLED":
                for line in order.lines:
                    item = self.repository.lock_menu_item(line.menu_item_id)
                    if item is not None:
                        item.capacity += line.quantity
            order.status = status
            self.session.commit()
            return order
        except Exception:
            self.session.rollback()
            raise
