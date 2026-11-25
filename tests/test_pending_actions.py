from decimal import Decimal

from sqlalchemy import select

from app.models import MenuItem, Order, PendingAction, User
from app.schemas.orders import OrderCreate, OrderLineCreate
from app.services.actions import PendingActionService
from tests.conftest import TEST_PASSWORD


USER_ONE = ("asha@example.test", TEST_PASSWORD)
USER_TWO = ("rohan@example.test", TEST_PASSWORD)


def _chat_session(client):
    return client.post("/api/chat/sessions", json={}, auth=USER_ONE).json()["id"]


def _proposal(factory, session_id, *, key="proposal-key-00001"):
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "asha@example.test"))
        action = PendingActionService(session).propose_order(
            user.id,
            session_id,
            OrderCreate(items=[OrderLineCreate(menu_item_id=1, quantity=1)]),
            idempotency_key=key,
        )
        return action.id, action.confirmation_key


def test_order_proposal_has_no_write_until_owner_confirms_repeat_safely(api_client) -> None:
    client, factory = api_client
    session_id = _chat_session(client)
    action_id, confirmation_key = _proposal(factory, session_id)
    open_actions = client.get(f"/api/chat/sessions/{session_id}/actions", auth=USER_ONE)
    foreign_actions = client.get(f"/api/chat/sessions/{session_id}/actions", auth=USER_TWO)
    with factory() as session:
        assert session.get(MenuItem, 1).capacity == 1
        assert session.query(Order).count() == 0

    foreign = client.post(
        f"/api/chat/actions/{action_id}/confirm",
        headers={"Idempotency-Key": confirmation_key},
        auth=USER_TWO,
    )
    confirmed = client.post(
        f"/api/chat/actions/{action_id}/confirm",
        headers={"Idempotency-Key": confirmation_key},
        auth=USER_ONE,
    )
    repeated = client.post(
        f"/api/chat/actions/{action_id}/confirm",
        headers={"Idempotency-Key": confirmation_key},
        auth=USER_ONE,
    )

    assert foreign.status_code == 404
    assert open_actions.status_code == 200 and open_actions.json()[0]["id"] == action_id
    assert foreign_actions.status_code == 404
    assert confirmed.status_code == repeated.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"
    assert confirmed.json()["outcome"]["order_id"] == repeated.json()["outcome"]["order_id"]
    with factory() as session:
        assert session.get(MenuItem, 1).capacity == 0
        assert session.query(Order).count() == 1


def test_rejection_and_changed_price_do_not_mutate_business_records(api_client) -> None:
    client, factory = api_client
    session_id = _chat_session(client)
    reject_id, reject_key = _proposal(factory, session_id, key="reject-proposal-key")
    rejected = client.post(
        f"/api/chat/actions/{reject_id}/reject",
        headers={"Idempotency-Key": reject_key},
        auth=USER_ONE,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"

    changed_id, changed_key = _proposal(factory, session_id, key="changed-proposal-key")
    with factory() as session:
        item = session.get(MenuItem, 1)
        item.price = Decimal("95.00")
        session.commit()
    needs_new_confirmation = client.post(
        f"/api/chat/actions/{changed_id}/confirm",
        headers={"Idempotency-Key": changed_key},
        auth=USER_ONE,
    )

    assert needs_new_confirmation.status_code == 409
    with factory() as session:
        action = session.get(PendingAction, changed_id)
        assert action.status == "PENDING"
        assert action.impact["total_amount"] == "95.00"
        assert session.get(MenuItem, 1).capacity == 1
        assert session.query(Order).count() == 0


def test_confirmed_cancellation_restores_portions_once(api_client) -> None:
    client, factory = api_client
    session_id = _chat_session(client)
    order = client.post(
        "/api/orders",
        json={"items": [{"menu_item_id": 1, "quantity": 1}]},
        headers={"Idempotency-Key": "manual-order-action-test"},
        auth=USER_ONE,
    ).json()
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "asha@example.test"))
        action = PendingActionService(session).propose_cancellation(user.id, session_id, order["id"], "cancel-proposal-key-1")
        action_id, key = action.id, action.confirmation_key

    first = client.post(f"/api/chat/actions/{action_id}/confirm", headers={"Idempotency-Key": key}, auth=USER_ONE)
    again = client.post(f"/api/chat/actions/{action_id}/confirm", headers={"Idempotency-Key": key}, auth=USER_ONE)

    assert first.status_code == again.status_code == 200
    assert first.json()["outcome"] == again.json()["outcome"]
    with factory() as session:
        assert session.get(MenuItem, 1).capacity == 1


def test_stock_change_expires_confirmation_instead_of_leaving_processing(api_client) -> None:
    client, factory = api_client
    session_id = _chat_session(client)
    action_id, key = _proposal(factory, session_id, key="stock-changed-proposal-key")
    with factory() as session:
        session.get(MenuItem, 1).capacity = 0
        session.commit()

    response = client.post(f"/api/chat/actions/{action_id}/confirm", headers={"Idempotency-Key": key}, auth=USER_ONE)

    assert response.status_code == 409
    with factory() as session:
        action = session.get(PendingAction, action_id)
        assert action.status == "EXPIRED"
        assert session.query(Order).count() == 0
