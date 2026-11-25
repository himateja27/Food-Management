from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.orders import OrderLineCreate


class AgentOrderProposal(BaseModel):
    items: list[OrderLineCreate] = Field(min_length=1, max_length=20)
    session_id: int = Field(gt=0)


class AgentCancelProposal(BaseModel):
    order_id: int = Field(gt=0)
    session_id: int = Field(gt=0)


class AgentPolicyQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class ActionResultRead(BaseModel):
    status: str
    outcome: dict[str, Any] | None = None


class AgentToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]
