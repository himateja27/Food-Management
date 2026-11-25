from datetime import datetime, timezone
from types import SimpleNamespace

from tests.conftest import TEST_PASSWORD

ADMIN = ("admin@example.test", TEST_PASSWORD)
USER_ONE = ("asha@example.test", TEST_PASSWORD)


def test_document_upload_enforces_admin_and_type(api_client) -> None:
    client, _ = api_client
    forbidden = client.post("/api/documents", files={"upload": ("policy.txt", b"Terms", "text/plain")}, auth=USER_ONE)
    invalid_type = client.post("/api/documents", files={"upload": ("policy.exe", b"Terms", "text/plain")}, auth=ADMIN)
    mismatched_type = client.post("/api/documents", files={"upload": ("policy.txt", b"Terms", "application/pdf")}, auth=ADMIN)

    assert forbidden.status_code == 403
    assert invalid_type.status_code == 415
    assert mismatched_type.status_code == 415
    assert all("request_id" in response.json() for response in (forbidden, invalid_type, mismatched_type))


def test_document_upload_is_bounded_and_indexes_safe_filename(api_client, monkeypatch) -> None:
    client, _ = api_client
    monkeypatch.setattr("app.api.documents.get_settings", lambda: SimpleNamespace(upload_max_bytes=5))
    too_large = client.post("/api/documents", files={"upload": ("policy.txt", b"123456", "text/plain")}, auth=ADMIN)
    assert too_large.status_code == 413

    class FakeRagService:
        def __init__(self, session):
            pass

        def upload(self, user_id, filename, content, media_type):
            assert filename == "../policy.txt"
            assert content == b"Terms"
            return SimpleNamespace(
                id=3,
                filename="policy.txt",
                media_type=media_type,
                version=1,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )

    monkeypatch.setattr("app.api.documents.RagService", FakeRagService)
    response = client.post("/api/documents", files={"upload": ("../policy.txt", b"Terms", "text/plain")}, auth=ADMIN)

    assert response.status_code == 201
    assert response.json()["filename"] == "policy.txt"
