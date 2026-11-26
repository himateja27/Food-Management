from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"content": "Does the menu declare milk as an allergen in Masala Dosa?"}})

    content: str = Field(min_length=1, max_length=4000)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seq_no: int
    role: str
    content: str
    mode: str | None
    citations: list[dict[str, Any]]
    outcome_code: str | None
    created_at: datetime


class PendingActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_type: str
    payload: dict[str, Any]
    impact: dict[str, Any]
    status: str
    expires_at: datetime
    confirmation_key: str


class ChatTurnRead(BaseModel):
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    pending_action: PendingActionRead | None = None
