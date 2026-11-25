import os
from decimal import Decimal

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.models import MenuItem, Order, OrderLine, User

PASSWORD_HASHER = PasswordHash.recommended()
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "FoodDemo123!")

MENU_FIXTURES = [
    ("Masala Dosa", "South Indian", "Crisp rice crepe with spiced potato", "90.00", 20, True, ["Milk"]),
    ("Paneer Biryani", "Rice", "Fragrant basmati rice with paneer", "180.00", 10, True, ["Milk"]),
    ("Idli Sambar", "South Indian", "Steamed rice cakes with lentil stew", "70.00", 24, True, []),
    ("Chole Bhature", "North Indian", "Chickpea curry with fried bread", "130.00", 16, True, ["Wheat"]),
    ("Chicken Chettinad", "Main Course", "Peppery Chettinad chicken curry", "240.00", 12, False, []),
    ("Vegetable Pulao", "Rice", "Basmati rice with seasonal vegetables", "150.00", 18, True, []),
    ("Aloo Paratha", "North Indian", "Whole wheat flatbread stuffed with potato", "95.00", 20, True, ["Wheat", "Milk"]),
    ("Gulab Jamun", "Dessert", "Milk-solid dumplings in rose syrup", "80.00", 30, True, ["Milk"]),
    ("Lemon Rice", "Rice", "Tempered rice with lemon and peanuts", "85.00", 15, True, ["Peanuts"]),
    ("Paneer Tikka", "Starters", "Chargrilled marinated paneer", "190.00", 14, True, ["Milk"]),
]


def seed_database(session: Session) -> None:
    users = [
        ("asha@example.test", "Asha Rao", "USER"),
        ("rohan@example.test", "Rohan Das", "USER"),
        ("admin@example.test", "Restaurant Admin", "ADMIN"),
    ]
    by_email: dict[str, User] = {}
    for email, full_name, role in users:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, full_name=full_name, role=role, password_hash=PASSWORD_HASHER.hash(DEMO_PASSWORD))
            session.add(user)
        by_email[email] = user
    session.flush()

    menu_by_name: dict[str, MenuItem] = {}
    for title, category, description, price, capacity, vegetarian, allergens in MENU_FIXTURES:
        item = session.scalar(select(MenuItem).where(MenuItem.title == title))
        if item is None:
            item = MenuItem(
                title=title,
                category=category,
                description=description,
                price=Decimal(price),
                capacity=capacity,
                is_vegetarian=vegetarian,
                declared_allergens=allergens,
            )
            session.add(item)
        menu_by_name[title] = item
    session.flush()

    orders = [
        ("asha@example.test", "demo-order-asha-1", "PLACED", [("Masala Dosa", 2)]),
        ("asha@example.test", "demo-order-asha-2", "PREPARING", [("Paneer Biryani", 1)]),
        ("rohan@example.test", "demo-order-rohan-1", "COMPLETED", [("Idli Sambar", 2)]),
    ]
    for email, key, status, lines in orders:
        order = session.scalar(select(Order).where(Order.user_id == by_email[email].id, Order.idempotency_key == key))
        if order is not None:
            continue
        total = sum((Decimal(next(row[3] for row in MENU_FIXTURES if row[0] == title)) * quantity for title, quantity in lines), Decimal("0.00"))
        order = Order(user=by_email[email], idempotency_key=key, status=status, total_amount=total)
        order.lines = [
            OrderLine(
                menu_item_id=menu_by_name[title].id,
                item_title_snapshot=title,
                quantity=quantity,
                unit_price_snapshot=menu_by_name[title].price,
            )
            for title, quantity in lines
        ]
        session.add(order)
    session.commit()


def main() -> None:
    with get_session_factory()() as session:
        seed_database(session)


if __name__ == "__main__":
    main()
