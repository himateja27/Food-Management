from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import MenuItem
from app.repositories.catalog import CatalogRepository
from app.schemas.menu import MenuItemWrite


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = CatalogRepository(session)

    def list_items(
        self,
        *,
        category: str | None = None,
        vegetarian: bool | None = None,
        max_price: Decimal | None = None,
        keyword: str | None = None,
    ) -> list[MenuItem]:
        return self.repository.list_active(category=category, vegetarian=vegetarian, max_price=max_price, keyword=keyword)

    def get_item(self, item_id: int) -> MenuItem:
        item = self.repository.get_active(item_id)
        if item is None:
            raise LookupError("Menu item not found")
        return item

    def create_item(self, data: MenuItemWrite) -> MenuItem:
        item = MenuItem(**data.model_dump())
        try:
            self.repository.add(item)
            self.session.commit()
            return item
        except Exception:
            self.session.rollback()
            raise

    def update_item(self, item_id: int, data: MenuItemWrite) -> MenuItem:
        item = self.repository.get_any(item_id)
        if item is None:
            raise LookupError("Menu item not found")
        for field, value in data.model_dump().items():
            setattr(item, field, value)
        try:
            self.session.commit()
            return item
        except Exception:
            self.session.rollback()
            raise

    def disable_item(self, item_id: int) -> None:
        item = self.repository.get_any(item_id)
        if item is None:
            raise LookupError("Menu item not found")
        item.is_active = False
        self.session.commit()
