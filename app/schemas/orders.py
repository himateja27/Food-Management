from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderLineCreate(BaseModel):
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=10)


class OrderCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"items": [{"menu_item_id": 1, "quantity": 2}]}
    })

    items: list[OrderLineCreate] = Field(min_length=1, max_length=20)


class OrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_id: int
    item_title_snapshot: str
    quantity: int
    unit_price_snapshot: Decimal


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    lines: list[OrderLineRead]


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(ACCEPTED|PREPARING|READY|COMPLETED|CANCELLED)$")
