from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import Base, MenuItem, User

TEST_PASSWORD = "TestPass123!"


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    hasher = PasswordHash.recommended()
    with factory() as session:
        session.add_all(
            [
                User(email="asha@example.test", full_name="Asha", password_hash=hasher.hash(TEST_PASSWORD), role="USER"),
                User(email="rohan@example.test", full_name="Rohan", password_hash=hasher.hash(TEST_PASSWORD), role="USER"),
                User(email="admin@example.test", full_name="Admin", password_hash=hasher.hash(TEST_PASSWORD), role="ADMIN"),
            ]
        )
        session.add_all(
            [
                MenuItem(title="Masala Dosa", category="South Indian", description="Crisp rice crepe", price=Decimal("90.00"), capacity=1, is_vegetarian=True, declared_allergens=["Milk"]),
                MenuItem(title="Chicken Curry", category="Main Course", description="Pepper chicken curry", price=Decimal("220.00"), capacity=5, is_vegetarian=False, declared_allergens=[]),
            ]
        )
        session.commit()

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()
