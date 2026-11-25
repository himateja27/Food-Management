from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_session(self, user_id: int, title: str) -> ChatSession:
        chat_session = ChatSession(user_id=user_id, title=title)
        self.session.add(chat_session)
        self.session.commit()
        self.session.refresh(chat_session)
        return chat_session

    def list_sessions(self, user_id: int) -> list[ChatSession]:
        query = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
        return list(self.session.scalars(query))

    def get_session(self, session_id: int, user_id: int, *, lock: bool = False) -> ChatSession | None:
        query = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        query = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.seq_no)
        return list(self.session.scalars(query))

    def recent_messages(self, session_id: int, limit: int = 12) -> list[ChatMessage]:
        query = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.seq_no.desc()).limit(limit)
        return list(reversed(self.session.scalars(query).all()))

    def append_message(
        self,
        session_id: int,
        role: str,
        content: str,
        *,
        mode: str | None = None,
        citations: list[dict[str, object]] | None = None,
        outcome_code: str | None = None,
    ) -> ChatMessage:
        self.session.scalar(select(ChatSession.id).where(ChatSession.id == session_id).with_for_update())
        current_seq = self.session.scalar(select(func.max(ChatMessage.seq_no)).where(ChatMessage.session_id == session_id)) or 0
        message = ChatMessage(
            session_id=session_id,
            seq_no=current_seq + 1,
            role=role,
            content=content,
            mode=mode,
            citations=citations or [],
            outcome_code=outcome_code,
        )
        self.session.add(message)
        chat_session = self.session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.updated_at = func.now()
        self.session.commit()
        self.session.refresh(message)
        return message
