from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AdminUser
from app.models import User
from app.schemas.menu import MenuItemRead, MenuItemWrite
from app.services.catalog import CatalogService

router = APIRouter(prefix="/api/menu_items", tags=["catalog"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[MenuItemRead], summary="Search active menu items")
def list_menu_items(
    session: DbSession,
    category: Annotated[str | None, Query(max_length=60, description="Match an exact menu category")] = None,
    vegetarian: Annotated[bool | None, Query(description="Filter to vegetarian items when true")] = None,
    max_price: Annotated[Decimal | None, Query(gt=0, max_digits=10, decimal_places=2, description="Maximum price in INR")] = None,
    keyword: Annotated[str | None, Query(min_length=1, max_length=120, description="Case-insensitive title or description search")] = None,
) -> list[MenuItemRead]:
    return CatalogService(session).list_items(category=category, vegetarian=vegetarian, max_price=max_price, keyword=keyword)


@router.get("/{item_id}", response_model=MenuItemRead, summary="Get an active menu item")
def get_menu_item(item_id: Annotated[int, Path(gt=0)], session: DbSession) -> MenuItemRead:
    return CatalogService(session).get_item(item_id)


@router.post("", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED, summary="Create a catalog item (admin)")
def create_menu_item(data: MenuItemWrite, session: DbSession, _: AdminUser) -> MenuItemRead:
    return CatalogService(session).create_item(data)


@router.put("/{item_id}", response_model=MenuItemRead, summary="Update a catalog item (admin)")
def update_menu_item(item_id: Annotated[int, Path(gt=0)], data: MenuItemWrite, session: DbSession, _: AdminUser) -> MenuItemRead:
    return CatalogService(session).update_item(item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-disable a catalog item (admin)")
def disable_menu_item(item_id: Annotated[int, Path(gt=0)], session: DbSession, _: AdminUser) -> Response:
    CatalogService(session).disable_item(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
