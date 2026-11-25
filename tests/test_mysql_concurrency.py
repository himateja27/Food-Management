import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import MenuItem, Order, OrderLine, User
from app.schemas.orders import OrderCreate, OrderLineCreate
from app.services.orders import BusinessRuleError, OrderService

MYSQL_TEST_DATABASE_URL = os.getenv("MYSQL_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not MYSQL_TEST_DATABASE_URL, reason="Set MYSQL_TEST_DATABASE_URL to a dedicated MySQL test database")


def test_two_customers_cannot_buy_the_final_portion_concurrently() -> None:
    engine = create_engine(MYSQL_TEST_DATABASE_URL, pool_size=5, max_overflow=0)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    email = f"race-{suffix}@example.test"
    with factory() as session:
        user = User(email=email, full_name="Concurrency Test", password_hash="not-used", role="USER")
        item = MenuItem(
            title=f"Race Dish {suffix}",
            category="Test",
            description="Temporary concurrency fixture",
            price=Decimal("10.00"),
            capacity=1,
            is_vegetarian=True,
            declared_allergens=[],
        )
        session.add_all([user, item])
        session.commit()
        user_id, item_id = user.id, item.id

    barrier = Barrier(2)

    def place_order(index: int) -> bool:
        with factory() as session:
            barrier.wait(timeout=10)
            try:
                OrderService(session).create_order(
                    user_id,
                    OrderCreate(items=[OrderLineCreate(menu_item_id=item_id, quantity=1)]),
                    f"race-{suffix}-{index}",
                )
                return True
            except BusinessRuleError as error:
                if error.code == "INSUFFICIENT_CAPACITY":
                    return False
                raise

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(place_order, (1, 2)))
        assert sorted(outcomes) == [False, True]
        with factory() as session:
            item = session.get(MenuItem, item_id)
            orders = list(session.scalars(select(Order).where(Order.user_id == user_id)))
            assert item is not None and item.capacity == 0
            assert len(orders) == 1
    finally:
        with factory() as session:
            order_ids = list(session.scalars(select(Order.id).where(Order.user_id == user_id)))
            for order_id in order_ids:
                order = session.get(Order, order_id)
                if order is not None:
                    session.delete(order)
            session.delete(session.get(MenuItem, item_id))
            session.delete(session.get(User, user_id))
            session.commit()
        engine.dispose()
