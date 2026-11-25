from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.gemini import AssistantResult
from app.ai.orchestrator import ChatOrchestrator
from app.models import Base, ChatMessage


def test_general_and_policy_requests_use_separate_paths(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    monkeypatch.setattr("app.ai.orchestrator.RagService.answer", lambda self, prompt: ("Verified policy answer", [{"filename": "policy.txt", "section": "line 1"}], None))
    monkeypatch.setattr("app.ai.orchestrator.GeminiChatEngine.generate", lambda self, prompt, history: AssistantResult("General answer"))
    orchestrator = ChatOrchestrator(session)
    history = [ChatMessage(seq_no=1, role="USER", content="Hi", citations=[])]

    general = orchestrator.generate("Say hello", history, user_id=1, session_id=1, message_id=1)
    policy = orchestrator.generate("What is the allergen policy?", history, user_id=1, session_id=1, message_id=1)

    assert general.mode == "GENERAL"
    assert general.text == "General answer"
    assert policy.mode == "RAG"
    assert policy.citations == [{"filename": "policy.txt", "section": "line 1"}]
    session.close()
    engine.dispose()


def test_mixed_live_policy_request_uses_agent_with_server_context(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    called = {}

    def fake_respond(self, prompt, messages, *, user_id, session_id, message_id, mode):
        called.update(user_id=user_id, session_id=session_id, message_id=message_id, mode=mode)
        return AssistantResult("Pending proposal", mode=mode, pending_action_id=8)

    monkeypatch.setattr("app.ai.orchestrator.GeminiAgent.respond", fake_respond)
    result = ChatOrchestrator(session).generate(
        "Can you order a dosa and check whether it contains dairy?",
        [],
        user_id=4,
        session_id=5,
        message_id=6,
    )

    assert result.mode == "MIXED"
    assert result.pending_action_id == 8
    assert called == {"user_id": 4, "session_id": 5, "message_id": 6, "mode": "MIXED"}
    session.close()
    engine.dispose()
