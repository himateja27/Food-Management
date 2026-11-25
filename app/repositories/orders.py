from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import MenuItem, Order


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, order_id: int, user_id: int, *, lock: bool = False) -> Order | None:
        query = select(Order).options(selectinload(Order.lines)).where(Order.id == order_id, Order.user_id == user_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def get_by_id(self, order_id: int, *, lock: bool = False) -> Order | None:
        query = select(Order).options(selectinload(Order.lines)).where(Order.id == order_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_for_user(self, user_id: int) -> list[Order]:
        query = select(Order).options(selectinload(Order.lines)).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        return list(self.session.scalars(query))

    def list_all(self) -> list[Order]:
        query = select(Order).options(selectinload(Order.lines)).order_by(Order.created_at.desc())
        return list(self.session.scalars(query))

    def by_idempotency_key(self, user_id: int, key: str, *, lock: bool = False) -> Order | None:
        query = select(Order).options(selectinload(Order.lines)).where(Order.user_id == user_id, Order.idempotency_key == key)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def lock_menu_item(self, item_id: int) -> MenuItem | None:
        return self.session.scalar(select(MenuItem).where(MenuItem.id == item_id).with_for_update())
