from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import MenuItem


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_active(
        self,
        *,
        category: str | None = None,
        vegetarian: bool | None = None,
        max_price: object | None = None,
        keyword: str | None = None,
    ) -> list[MenuItem]:
        query: Select[tuple[MenuItem]] = select(MenuItem).where(MenuItem.is_active.is_(True))
        if category:
            query = query.where(MenuItem.category == category)
        if vegetarian is not None:
            query = query.where(MenuItem.is_vegetarian.is_(vegetarian))
        if max_price is not None:
            query = query.where(MenuItem.price <= max_price)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            query = query.where(MenuItem.title.ilike(pattern) | MenuItem.description.ilike(pattern))
        return list(self.session.scalars(query.order_by(MenuItem.category, MenuItem.title)))

    def get_active(self, item_id: int) -> MenuItem | None:
        return self.session.scalar(select(MenuItem).where(MenuItem.id == item_id, MenuItem.is_active.is_(True)))

    def get_any(self, item_id: int) -> MenuItem | None:
        return self.session.get(MenuItem, item_id)

    def add(self, item: MenuItem) -> MenuItem:
        self.session.add(item)
        self.session.flush()
        return item
