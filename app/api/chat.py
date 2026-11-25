from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from fastapi import Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser
from app.api.limits import ChatRateLimit
from app.models import User
from app.schemas.chat import ChatMessageCreate, ChatMessageRead, ChatSessionCreate, ChatSessionRead, ChatTurnRead, PendingActionRead
from app.schemas.agent import ActionResultRead
from app.services.actions import PendingActionService
from app.services.chat import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED, summary="Create a chat session")
def create_session(data: ChatSessionCreate, session: DbSession, user: CurrentUser) -> ChatSessionRead:
    return ChatService(session).create_session(user.id, data)


@router.get("/sessions", response_model=list[ChatSessionRead], summary="List the user's chat sessions")
def list_sessions(session: DbSession, user: CurrentUser) -> list[ChatSessionRead]:
    return ChatService(session).list_sessions(user.id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageRead], summary="Load ordered chat history")
def list_messages(session_id: Annotated[int, Path(gt=0)], session: DbSession, user: CurrentUser) -> list[ChatMessageRead]:
    return ChatService(session).list_messages(session_id, user.id)


@router.get("/sessions/{session_id}/actions", response_model=list[PendingActionRead], summary="Load open actions for an owned chat session")
def list_session_actions(session_id: Annotated[int, Path(gt=0)], session: DbSession, user: CurrentUser) -> list[PendingActionRead]:
    return PendingActionService(session).list_for_session(session_id, user.id)


@router.post("/sessions/{session_id}/messages", response_model=ChatTurnRead, summary="Send a message to the assistant")
def post_message(
    session_id: Annotated[int, Path(gt=0)],
    data: ChatMessageCreate,
    session: DbSession,
    user: CurrentUser,
    _rate_limit: ChatRateLimit,
) -> ChatTurnRead:
    user_message, assistant_message, pending_action = ChatService(session).post_message(session_id, user.id, data)
    return ChatTurnRead(user_message=user_message, assistant_message=assistant_message, pending_action=pending_action)

@router.post("/actions/{action_id}/confirm", response_model=ActionResultRead, summary="Confirm a pending business action")
def confirm_action(
    action_id: Annotated[int, Path(gt=0)],
    session: DbSession,
    user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
) -> ActionResultRead:
    action = PendingActionService(session).confirm(action_id, user.id, idempotency_key)
    return ActionResultRead(status=action.status, outcome=action.outcome)

@router.post("/actions/{action_id}/reject", response_model=ActionResultRead, summary="Reject a pending business action")
def reject_action(
    action_id: Annotated[int, Path(gt=0)],
    session: DbSession,
    user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
) -> ActionResultRead:
    action = PendingActionService(session).reject(action_id, user.id, idempotency_key)
    return ActionResultRead(status=action.status, outcome=action.outcome)
