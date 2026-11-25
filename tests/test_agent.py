from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx
from google.genai import types
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.agent import AgentToolClient, GeminiAgent, TOOL_SPECS
from app.core.security import create_internal_identity_headers
from app.models import Base, ChatMessage, ChatSession, ToolRun, User


SECRET = "test-internal-signing-secret-0123456789abcdef"


def test_tool_schemas_are_closed_and_reject_unlisted_arguments(monkeypatch) -> None:
    for spec in TOOL_SPECS.values():
        assert spec.schema["type"] == "object"
        assert spec.schema["additionalProperties"] is False

    monkeypatch.setattr("app.ai.agent.get_settings", lambda: SimpleNamespace(internal_api_base_url="http://127.0.0.1", internal_api_secret=SECRET))
    monkeypatch.setattr("app.core.security.get_settings", lambda: SimpleNamespace(internal_api_secret=SECRET))
    requests = []
    client = httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(lambda request: requests.append(request)))
    tools = AgentToolClient(client)

    result, safe_input, action_id, _ = tools.dispatch(
        "search_menu_items",
        {"keyword": "dosa", "url": "http://attacker.invalid"},
        user_id=1,
        session_id=3,
        message_id=4,
    )

    assert result == {"error": "Tool arguments did not match the allowed schema"}
    assert safe_input == {}
    assert action_id is None
    nested_price, _, _, _ = tools.dispatch(
        "create_order",
        {"items": [{"menu_item_id": 1, "quantity": 1, "price": 0.01}]},
        user_id=1,
        session_id=3,
        message_id=4,
    )
    assert nested_price == {"error": "Tool arguments did not match the allowed schema"}
    assert requests == []
    client.close()


def test_internal_identity_is_signed_and_tamper_resistant(api_client, monkeypatch) -> None:
    client, factory = api_client
    monkeypatch.setattr("app.core.security.get_settings", lambda: SimpleNamespace(internal_api_secret=SECRET))
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "asha@example.test"))
        signed = create_internal_identity_headers(user.id)

    allowed = client.get("/api/orders", headers=signed)
    altered = {**signed, "X-Internal-Actor": "2"}
    rejected = client.get("/api/orders", headers=altered)

    assert allowed.status_code == 200
    assert rejected.status_code == 401
    assert rejected.json()["code"] == "UNAUTHENTICATED"


def test_gemini_function_call_uses_allowlist_and_persists_safe_tool_run(monkeypatch) -> None:
    from app.ai import agent as agent_module

    engine = __import__("sqlalchemy").create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    user = User(email="agent@example.test", full_name="Agent User", password_hash="x")
    chat_session = ChatSession(user=user, title="Menu lookup")
    session.add(chat_session)
    session.flush()
    user_message = ChatMessage(session_id=chat_session.id, seq_no=1, role="USER", content="Search the menu for dosa", citations=[])
    session.add(user_message)
    session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/menu_items"
        assert request.url.params["keyword"] == "dosa"
        assert request.headers["X-Internal-Actor"] == str(user.id)
        assert "Authorization" not in request.headers
        return httpx.Response(200, json=[{
            "id": 1,
            "title": "Masala Dosa",
            "category": "South Indian",
            "description": "Crisp rice crepe",
            "price": "90.00",
            "capacity": 4,
            "is_vegetarian": True,
            "declared_allergens": ["Milk"],
            "is_active": True,
        }], request=request)

    http_client = httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(handler))
    tool_client = AgentToolClient(http_client)

    class FakeModels:
        calls = 0

        def generate_content(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                declarations = kwargs["config"].tools[0].function_declarations
                assert {declaration.name for declaration in declarations} == set(TOOL_SPECS)
                function_call = types.FunctionCall(name="search_menu_items", args={"keyword": "dosa"})
                content = types.Content(role="model", parts=[types.Part(function_call=function_call)])
                return SimpleNamespace(candidates=[types.Candidate(content=content)], text=None)
            assert any(part.function_response for part in kwargs["contents"][-1].parts)
            content = types.Content(role="model", parts=[types.Part(text="Masala Dosa is available at ₹90.00.")])
            return SimpleNamespace(candidates=[types.Candidate(content=content)], text="Masala Dosa is available at ₹90.00.")

    fake_models = FakeModels()
    monkeypatch.setattr(agent_module, "get_settings", lambda: SimpleNamespace(gemini_api_key="fake-key", gemini_model="test-model", internal_api_base_url="http://127.0.0.1", internal_api_secret=SECRET))
    monkeypatch.setattr("app.core.security.get_settings", lambda: SimpleNamespace(internal_api_secret=SECRET))
    monkeypatch.setattr(agent_module.genai, "Client", lambda **kwargs: SimpleNamespace(models=fake_models))

    result = GeminiAgent(session, tool_client).respond(
        "Search the menu for dosa",
        [user_message],
        user_id=user.id,
        session_id=chat_session.id,
        message_id=user_message.id,
    )

    tool_run = session.scalar(select(ToolRun).where(ToolRun.session_id == chat_session.id))
    assert result.mode == "AGENT"
    assert "Masala Dosa" in result.text
    assert tool_run is not None
    assert tool_run.safe_input == {"keyword": "dosa"}
    assert "Authorization" not in str(tool_run.safe_result)
    http_client.close()
    session.close()
    engine.dispose()
