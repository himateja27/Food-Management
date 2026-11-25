from typing import Any

from sqlalchemy.orm import Session

from app.ai.gemini import AssistantResult
from app.ai.orchestrator import ChatOrchestrator
from app.core.redaction import redact_sensitive_content
from app.models import ChatMessage, ChatSession, PendingAction
from app.repositories.chat import ChatRepository
from app.schemas.chat import ChatMessageCreate, ChatSessionCreate


class ChatService:
    def __init__(self, session: Session, engine: ChatOrchestrator | None = None) -> None:
        self.session = session
        self.repository = ChatRepository(session)
        self.engine = engine or ChatOrchestrator(session)

    def create_session(self, user_id: int, data: ChatSessionCreate) -> ChatSession:
        return self.repository.create_session(user_id, data.title)

    def list_sessions(self, user_id: int) -> list[ChatSession]:
        return self.repository.list_sessions(user_id)

    def list_messages(self, session_id: int, user_id: int) -> list[ChatMessage]:
        if self.repository.get_session(session_id, user_id) is None:
            raise LookupError("Chat session not found")
        return self.repository.list_messages(session_id)

    def post_message(self, session_id: int, user_id: int, data: ChatMessageCreate) -> tuple[ChatMessage, ChatMessage, PendingAction | None]:
        if self.repository.get_session(session_id, user_id) is None:
            raise LookupError("Chat session not found")
        recent = self.repository.recent_messages(session_id)
        safe_content = redact_sensitive_content(data.content)
        user_message = self.repository.append_message(session_id, "USER", safe_content)
        try:
            result = self.engine.generate(
                safe_content,
                recent + [user_message],
                user_id=user_id,
                session_id=session_id,
                message_id=user_message.id,
            )
        except Exception:
            result = AssistantResult(
                text="I couldn't process that request just now. Your message is saved; please try again.",
                outcome_code="PROCESSING_ERROR",
            )
        assistant_message = self.repository.append_message(
            session_id,
            "ASSISTANT",
            result.text,
            mode=result.mode,
            citations=result.citations or [],
            outcome_code=result.outcome_code,
        )
        pending_action = self.session.get(PendingAction, result.pending_action_id) if result.pending_action_id is not None else None
        return user_message, assistant_message, pending_action
