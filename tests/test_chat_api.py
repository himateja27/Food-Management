from sqlalchemy import select

from app.models import ChatMessage
from app.services.chat import ChatService
from tests.conftest import TEST_PASSWORD


USER_ONE = ("asha@example.test", TEST_PASSWORD)
USER_TWO = ("rohan@example.test", TEST_PASSWORD)


def test_chat_persists_user_before_model_and_resumes_ordered_history(api_client, monkeypatch) -> None:
    client, factory = api_client
    observed = []

    def fake_generate(self, prompt, recent_messages, **kwargs):
        with factory() as session:
            saved = session.scalar(select(ChatMessage).where(ChatMessage.content == prompt, ChatMessage.role == "USER"))
            observed.append(saved is not None)
        assert recent_messages[-1].content == prompt
        return type("Result", (), {"text": f"Reply: {prompt}", "mode": "GENERAL", "citations": [], "outcome_code": None, "pending_action_id": None})()

    monkeypatch.setattr("app.ai.orchestrator.ChatOrchestrator.generate", fake_generate)
    created = client.post("/api/chat/sessions", json={"title": "Dinner ideas"}, auth=USER_ONE)
    session_id = created.json()["id"]

    first = client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Hello"}, auth=USER_ONE)
    second = client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "One more question"}, auth=USER_ONE)
    history = client.get(f"/api/chat/sessions/{session_id}/messages", auth=USER_ONE)
    concealed = client.get(f"/api/chat/sessions/{session_id}/messages", auth=USER_TWO)

    assert created.status_code == 201
    assert first.status_code == second.status_code == 200
    assert observed == [True, True]
    assert [message["seq_no"] for message in history.json()] == [1, 2, 3, 4]
    assert [message["role"] for message in history.json()] == ["USER", "ASSISTANT", "USER", "ASSISTANT"]
    assert concealed.status_code == 404


def test_chat_model_failure_is_persisted_as_safe_outcome(api_client, monkeypatch) -> None:
    client, _ = api_client
    monkeypatch.setattr("app.ai.orchestrator.ChatOrchestrator.generate", lambda *args: (_ for _ in ()).throw(RuntimeError("secret detail")))
    session_id = client.post("/api/chat/sessions", json={}, auth=USER_ONE).json()["id"]

    response = client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Hi"}, auth=USER_ONE)

    assert response.status_code == 200
    assistant = response.json()["assistant_message"]
    assert assistant["outcome_code"] == "PROCESSING_ERROR"
    assert "secret detail" not in assistant["content"]


def test_chat_redacts_credentials_before_storage_and_model(api_client, monkeypatch) -> None:
    client, factory = api_client
    observed = []

    def fake_generate(self, prompt, recent_messages, **kwargs):
        observed.append(prompt)
        return type("Result", (), {"text": "Stored safely", "mode": "GENERAL", "citations": [], "outcome_code": None, "pending_action_id": None})()

    monkeypatch.setattr("app.ai.orchestrator.ChatOrchestrator.generate", fake_generate)
    session_id = client.post("/api/chat/sessions", json={}, auth=USER_ONE).json()["id"]
    submitted = "my password is hunter2 Authorization: Basic dXNlcjpwYXNzd29yZA=="

    response = client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": submitted}, auth=USER_ONE)

    assert response.status_code == 200
    assert "hunter2" not in response.json()["user_message"]["content"]
    assert "dXNlcjpwYXNzd29yZA==" not in response.json()["user_message"]["content"]
    assert "hunter2" not in observed[0]
    assert "dXNlcjpwYXNzd29yZA==" not in observed[0]
    with factory() as session:
        stored = session.scalar(select(ChatMessage).where(ChatMessage.role == "USER", ChatMessage.session_id == session_id))
        assert "hunter2" not in stored.content
