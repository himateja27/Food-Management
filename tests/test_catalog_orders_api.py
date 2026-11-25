from decimal import Decimal

from sqlalchemy import select

from app.models import MenuItem
from tests.conftest import TEST_PASSWORD


USER_ONE = ("asha@example.test", TEST_PASSWORD)
USER_TWO = ("rohan@example.test", TEST_PASSWORD)
ADMIN = ("admin@example.test", TEST_PASSWORD)


def test_catalog_filters_are_public(api_client) -> None:
    client, _ = api_client

    response = client.get("/api/menu_items", params={"vegetarian": "true", "max_price": "100", "keyword": "dosa"})

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Masala Dosa"]


def test_order_uses_db_price_and_idempotency_then_restores_stock_once(api_client) -> None:
    client, factory = api_client
    payload = {"items": [{"menu_item_id": 1, "quantity": 1}]}
    headers = {"Idempotency-Key": "order-key-0001"}

    first = client.post("/api/orders", json=payload, headers=headers, auth=USER_ONE)
    duplicate = client.post("/api/orders", json=payload, headers=headers, auth=USER_ONE)

    assert first.status_code == 201
    assert duplicate.json()["id"] == first.json()["id"]
    assert first.json()["total_amount"] == "90.00"
    assert first.json()["lines"][0]["unit_price_snapshot"] == "90.00"
    with factory() as session:
        assert session.get(MenuItem, 1).capacity == 0

    cancelled = client.post(f"/api/orders/{first.json()['id']}/cancel", headers={**headers, "Idempotency-Key": "cancel-key-0001"}, auth=USER_ONE)
    repeated = client.post(f"/api/orders/{first.json()['id']}/cancel", headers={**headers, "Idempotency-Key": "cancel-key-0001"}, auth=USER_ONE)

    assert cancelled.status_code == 200
    assert repeated.json()["status"] == "CANCELLED"
    with factory() as session:
        assert session.get(MenuItem, 1).capacity == 1


def test_order_owner_role_validation_and_transition_rules(api_client) -> None:
    client, _ = api_client
    created = client.post(
        "/api/orders",
        json={"items": [{"menu_item_id": 1, "quantity": 1}]},
        headers={"Idempotency-Key": "owner-key-0001"},
        auth=USER_ONE,
    )
    order_id = created.json()["id"]

    forbidden_admin_action = client.post("/api/menu_items", json={}, auth=USER_ONE)
    hidden_from_other_owner = client.get(f"/api/orders/{order_id}", auth=USER_TWO)
    invalid_status = client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "PREPARING"}, auth=ADMIN)
    invalid_quantity = client.post(
        "/api/orders",
        json={"items": [{"menu_item_id": 2, "quantity": 11}]},
        headers={"Idempotency-Key": "invalid-key-0001"},
        auth=USER_ONE,
    )

    assert forbidden_admin_action.status_code == 403
    assert hidden_from_other_owner.status_code == 404
    assert invalid_status.status_code == 409
    assert invalid_quantity.status_code == 422
    assert all("request_id" in response.json() and "code" in response.json() for response in (forbidden_admin_action, hidden_from_other_owner, invalid_status, invalid_quantity))


def test_admin_can_make_permitted_status_transition(api_client) -> None:
    client, _ = api_client
    order = client.post(
        "/api/orders",
        json={"items": [{"menu_item_id": 1, "quantity": 1}]},
        headers={"Idempotency-Key": "status-key-0001"},
        auth=USER_ONE,
    ).json()

    response = client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "ACCEPTED"}, auth=ADMIN)

    assert response.status_code == 200
    assert response.json()["status"] == "ACCEPTED"
