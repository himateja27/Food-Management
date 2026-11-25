from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ChatSession, MenuItem, Order, PendingAction
from app.repositories.orders import OrderRepository
from app.schemas.orders import OrderCreate, OrderLineCreate
from app.services.orders import BusinessRuleError, CANCELLABLE_STATUSES, OrderService

ACTION_TTL = timedelta(minutes=10)


class PendingActionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def propose_order(self, user_id: int, session_id: int, data: OrderCreate, idempotency_key: str | None = None) -> PendingAction:
        self._require_owned_session(session_id, user_id)
        existing = self._find_by_idempotency_key(user_id, idempotency_key)
        if existing is not None:
            return existing
        quantities: dict[int, int] = {}
        for line in data.items:
            quantities[line.menu_item_id] = quantities.get(line.menu_item_id, 0) + line.quantity
        if any(quantity > 10 for quantity in quantities.values()):
            raise BusinessRuleError("INVALID_QUANTITY", "Combined quantity for an item cannot exceed 10", 422)
        try:
            items: dict[int, MenuItem] = {}
            for item_id in sorted(quantities):
                item = self.session.scalar(select(MenuItem).where(MenuItem.id == item_id).with_for_update())
                if item is None or not item.is_active:
                    raise BusinessRuleError("MENU_ITEM_UNAVAILABLE", "One or more menu items are unavailable", 404)
                if item.capacity < quantities[item_id]:
                    raise BusinessRuleError("INSUFFICIENT_CAPACITY", f"Not enough portions available for {item.title}")
                items[item_id] = item
            lines = [
                {
                    "menu_item_id": item_id,
                    "title": items[item_id].title,
                    "quantity": quantity,
                    "unit_price": str(items[item_id].price),
                    "line_total": str(items[item_id].price * quantity),
                }
                for item_id, quantity in sorted(quantities.items())
            ]
            total = sum((items[item_id].price * quantity for item_id, quantity in quantities.items()), Decimal("0.00"))
            action = PendingAction(
                user_id=user_id,
                session_id=session_id,
                action_type="CREATE_ORDER",
                payload={"items": [{"menu_item_id": item_id, "quantity": quantity, "expected_price": str(items[item_id].price)} for item_id, quantity in sorted(quantities.items())]},
                impact={"items": lines, "total_amount": str(total)},
                idempotency_key=idempotency_key or uuid4().hex,
                status="PENDING",
                expires_at=datetime.now(timezone.utc) + ACTION_TTL,
            )
            self.session.add(action)
            self.session.commit()
            self.session.refresh(action)
            return action
        except Exception:
            self.session.rollback()
            raise

    def propose_cancellation(self, user_id: int, session_id: int, order_id: int, idempotency_key: str | None = None) -> PendingAction:
        self._require_owned_session(session_id, user_id)
        existing = self._find_by_idempotency_key(user_id, idempotency_key)
        if existing is not None:
            return existing
        order = OrderRepository(self.session).get_for_user(order_id, user_id, lock=True)
        if order is None:
            raise LookupError("Order not found")
        if order.status not in CANCELLABLE_STATUSES:
            raise BusinessRuleError("CANCELLATION_NOT_ALLOWED", "Orders cannot be cancelled after preparation begins")
        impact = {
            "order_id": order.id,
            "current_status": order.status,
            "portions_returned": [
                {"title": line.item_title_snapshot, "quantity": line.quantity}
                for line in order.lines
            ],
            "total_amount": str(order.total_amount),
        }
        action = PendingAction(
            user_id=user_id,
            session_id=session_id,
            action_type="CANCEL_ORDER",
            payload={"order_id": order.id, "expected_status": order.status},
            impact=impact,
            idempotency_key=idempotency_key or uuid4().hex,
            status="PENDING",
            expires_at=datetime.now(timezone.utc) + ACTION_TTL,
        )
        self.session.add(action)
        self.session.commit()
        self.session.refresh(action)
        return action

    def confirm(self, action_id: int, user_id: int, idempotency_key: str) -> PendingAction:
        action = self._get_owned_action(action_id, user_id, lock=True)
        if action.idempotency_key != idempotency_key:
            raise BusinessRuleError("IDEMPOTENCY_KEY_MISMATCH", "Confirmation key does not match this action", 409)
        if action.status == "CONFIRMED":
            return action
        if action.status in {"REJECTED", "EXPIRED"}:
            raise BusinessRuleError("ACTION_NOT_PENDING", "This action is no longer available", 409)
        expires_at = action.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            action.status = "EXPIRED"
            self.session.commit()
            raise BusinessRuleError("ACTION_EXPIRED", "This confirmation has expired; request a new proposal", 409)

        action.status = "PROCESSING"
        self.session.commit()
        try:
            if action.action_type == "CREATE_ORDER":
                outcome = self._confirm_order(action, user_id)
            elif action.action_type == "CANCEL_ORDER":
                outcome = self._confirm_cancellation(action, user_id)
            else:
                raise BusinessRuleError("ACTION_NOT_SUPPORTED", "This action type is not supported", 409)
            action = self._get_owned_action(action_id, user_id, lock=True)
            action.status = "CONFIRMED"
            action.outcome = outcome
            self.session.commit()
            return action
        except BusinessRuleError as exc:
            self.session.rollback()
            current = self._get_owned_action(action_id, user_id, lock=True)
            if current.status == "PROCESSING":
                current.status = "EXPIRED"
                current.outcome = {"code": exc.code, "message": "The confirmed terms are no longer available"}
                self.session.commit()
            raise
        except Exception:
            self.session.rollback()
            raise

    def reject(self, action_id: int, user_id: int, idempotency_key: str) -> PendingAction:
        action = self._get_owned_action(action_id, user_id, lock=True)
        if action.idempotency_key != idempotency_key:
            raise BusinessRuleError("IDEMPOTENCY_KEY_MISMATCH", "Confirmation key does not match this action", 409)
        if action.status == "REJECTED":
            return action
        if action.status != "PENDING":
            raise BusinessRuleError("ACTION_NOT_PENDING", "This action can no longer be rejected", 409)
        action.status = "REJECTED"
        self.session.commit()
        return action

    def list_for_session(self, session_id: int, user_id: int) -> list[PendingAction]:
        self._require_owned_session(session_id, user_id)
        actions = list(self.session.scalars(
            select(PendingAction)
            .where(
                PendingAction.session_id == session_id,
                PendingAction.user_id == user_id,
                PendingAction.status.in_(["PENDING", "PROCESSING"]),
            )
            .order_by(PendingAction.created_at)
        ))
        now = datetime.now(timezone.utc)
        changed = False
        for action in actions:
            expires_at = action.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                action.status = "EXPIRED"
                changed = True
        if changed:
            self.session.commit()
        return [action for action in actions if action.status in {"PENDING", "PROCESSING"}]

    def _confirm_order(self, action: PendingAction, user_id: int) -> dict[str, object]:
        prior = OrderRepository(self.session).by_idempotency_key(user_id, f"agent-action-{action.id}")
        if prior is not None:
            return {"order_id": prior.id, "status": prior.status, "total_amount": str(prior.total_amount)}
        payload_items = action.payload["items"]
        expected_prices = {int(line["menu_item_id"]): Decimal(str(line["expected_price"])) for line in payload_items}
        quantities = {int(line["menu_item_id"]): int(line["quantity"]) for line in payload_items}
        items = {
            item_id: self.session.scalar(select(MenuItem).where(MenuItem.id == item_id).with_for_update())
            for item_id in sorted(quantities)
        }
        for item_id, quantity in quantities.items():
            item = items[item_id]
            if item is None or not item.is_active:
                self._expire(action, "One or more menu items are no longer available")
                raise BusinessRuleError("TERMS_CHANGED", "Menu availability changed; request a new proposal", 409)
            if item.capacity < quantity:
                action.impact = {"message": "Insufficient current portions", "available": item.capacity, "requested": quantity}
                action.status = "EXPIRED"
                action.outcome = {"code": "INSUFFICIENT_CAPACITY"}
                self.session.commit()
                raise BusinessRuleError("INSUFFICIENT_CAPACITY", "There are no longer enough portions available", 409)
        if any(items[item_id].price != expected_prices[item_id] for item_id in quantities):
            action.payload = {
                "items": [
                    {"menu_item_id": item_id, "quantity": quantities[item_id], "expected_price": str(items[item_id].price)}
                    for item_id in sorted(quantities)
                ]
            }
            action.impact = self._order_impact(items, quantities)
            action.status = "PENDING"
            self.session.commit()
            raise BusinessRuleError("TERMS_CHANGED", "Menu prices changed; review and confirm the updated terms", 409)
        try:
            order = OrderService(self.session).create_order(
                user_id,
                OrderCreate(items=[OrderLineCreate(menu_item_id=item_id, quantity=quantity) for item_id, quantity in sorted(quantities.items())]),
                f"agent-action-{action.id}",
                expected_prices=expected_prices,
            )
        except BusinessRuleError as exc:
            if exc.code == "TERMS_CHANGED":
                self.session.rollback()
                action = self._get_owned_action(action.id, user_id, lock=True)
                current_items = {item_id: self.session.get(MenuItem, item_id) for item_id in quantities}
                if all(current_items[item_id] is not None and current_items[item_id].is_active for item_id in quantities):
                    action.payload = {"items": [{"menu_item_id": item_id, "quantity": quantities[item_id], "expected_price": str(current_items[item_id].price)} for item_id in sorted(quantities)]}
                    action.impact = self._order_impact(current_items, quantities)
                    action.status = "PENDING"
                    self.session.commit()
                    raise BusinessRuleError("TERMS_CHANGED", "Menu prices changed; review and confirm the updated terms", 409) from exc
            raise
        return {"order_id": order.id, "status": order.status, "total_amount": str(order.total_amount)}

    def _confirm_cancellation(self, action: PendingAction, user_id: int) -> dict[str, object]:
        order_id = int(action.payload["order_id"])
        order = OrderRepository(self.session).get_for_user(order_id, user_id, lock=True)
        if order is None:
            self._expire(action, "Order not found")
            raise LookupError("Order not found")
        if order.status == "CANCELLED":
            return {"order_id": order.id, "status": order.status, "portions_restored": sum(line.quantity for line in order.lines)}
        if order.status != action.payload["expected_status"] or order.status not in CANCELLABLE_STATUSES:
            self._expire(action, "Order state changed")
            raise BusinessRuleError("TERMS_CHANGED", "Order status changed; request a new cancellation proposal", 409)
        cancelled = OrderService(self.session).cancel_order(order_id, user_id, action.idempotency_key)
        return {"order_id": cancelled.id, "status": cancelled.status, "portions_restored": sum(line.quantity for line in cancelled.lines)}

    def _order_impact(self, items: dict[int, MenuItem | None], quantities: dict[int, int]) -> dict[str, object]:
        lines = [
            {
                "title": items[item_id].title,
                "quantity": quantities[item_id],
                "unit_price": str(items[item_id].price),
                "line_total": str(items[item_id].price * quantities[item_id]),
            }
            for item_id in sorted(quantities)
            if items[item_id] is not None
        ]
        total = sum((items[item_id].price * quantities[item_id] for item_id in quantities if items[item_id] is not None), Decimal("0.00"))
        return {"items": lines, "total_amount": str(total)}

    def _expire(self, action: PendingAction, reason: str) -> None:
        action.status = "EXPIRED"
        action.outcome = {"message": reason}
        self.session.commit()

    def _get_owned_action(self, action_id: int, user_id: int, *, lock: bool = False) -> PendingAction:
        query = select(PendingAction).where(PendingAction.id == action_id, PendingAction.user_id == user_id)
        if lock:
            query = query.with_for_update()
        action = self.session.scalar(query)
        if action is None:
            raise LookupError("Pending action not found")
        return action

    def _find_by_idempotency_key(self, user_id: int, key: str | None) -> PendingAction | None:
        if key is None:
            return None
        return self.session.scalar(select(PendingAction).where(PendingAction.user_id == user_id, PendingAction.idempotency_key == key))

    def _require_owned_session(self, session_id: int, user_id: int) -> None:
        chat_session = self.session.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
        if chat_session is None:
            raise LookupError("Chat session not found")
