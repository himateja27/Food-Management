from pwdlib import PasswordHash

from app.models import User


def test_registration_creates_hashed_customer_account_and_signs_in(api_client) -> None:
    client, factory = api_client
    payload = {
        "full_name": "Mira Patel",
        "email": "Mira@Example.test",
        "password": "DinnerTable123!",
        "role": "ADMIN",
    }

    registered = client.post("/api/auth/register", json=payload)
    authenticated = client.get("/api/auth/me", auth=("mira@example.test", payload["password"]))

    assert registered.status_code == 201
    assert registered.json()["email"] == "mira@example.test"
    assert registered.json()["role"] == "USER"
    assert "password" not in registered.json()
    assert authenticated.status_code == 200
    assert authenticated.json()["role"] == "USER"
    with factory() as session:
        user = session.get(User, registered.json()["id"])
        assert user.role == "USER"
        assert user.password_hash != payload["password"]
        assert PasswordHash.recommended().verify(payload["password"], user.password_hash)


def test_registration_duplicate_and_invalid_values_are_safe(api_client) -> None:
    client, _ = api_client
    payload = {"full_name": "New Customer", "email": "asha@example.test", "password": "DinnerTable123!"}

    duplicate = client.post("/api/auth/register", json=payload)
    invalid_email = client.post("/api/auth/register", json={**payload, "email": "not-an-email"})
    short_password = client.post("/api/auth/register", json={**payload, "email": "new@example.test", "password": "short"})

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "EMAIL_ALREADY_REGISTERED"
    assert "request_id" in duplicate.json()
    assert invalid_email.status_code == 422
    assert short_password.status_code == 422


def test_registration_page_is_served_and_has_customer_form(api_client) -> None:
    client, _ = api_client

    response = client.get("/register")

    assert response.status_code == 200
    assert 'id="register-form"' in response.text
    assert 'name="full_name"' in response.text
    assert 'name="role"' not in response.text.lower()
