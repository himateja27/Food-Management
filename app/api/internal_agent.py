from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.ai.rag import RagService
from app.core.database import get_db
from app.core.security import CurrentUser
from app.schemas.agent import AgentCancelProposal, AgentOrderProposal, AgentPolicyQuestion
from app.schemas.chat import PendingActionRead
from app.schemas.orders import OrderCreate
from app.services.actions import PendingActionService

router = APIRouter(prefix="/api/internal/agent", tags=["internal agent"], include_in_schema=False)
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/order-proposals", response_model=PendingActionRead)
def propose_order(
    data: AgentOrderProposal,
    session: DbSession,
    user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
) -> PendingActionRead:
    action = PendingActionService(session).propose_order(
        user.id,
        data.session_id,
        OrderCreate(items=data.items),
        idempotency_key,
    )
    return action


@router.post("/cancellation-proposals", response_model=PendingActionRead)
def propose_cancellation(
    data: AgentCancelProposal,
    session: DbSession,
    user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
) -> PendingActionRead:
    action = PendingActionService(session).propose_cancellation(user.id, data.session_id, data.order_id, idempotency_key)
    return action


@router.post("/policy")
def retrieve_policy(data: AgentPolicyQuestion, session: DbSession, _: CurrentUser) -> dict[str, object]:
    answer, citations, outcome_code = RagService(session).answer(data.question)
    return {"answer": answer, "citations": citations, "outcome_code": outcome_code}
