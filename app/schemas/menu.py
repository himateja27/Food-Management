from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MenuItemWrite(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "Masala Dosa",
            "category": "South Indian",
            "description": "Crisp rice crepe with spiced potato",
            "price": "90.00",
            "capacity": 20,
            "is_vegetarian": True,
            "declared_allergens": ["Milk"],
        }
    })

    title: str = Field(min_length=3, max_length=120)
    category: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=2000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    capacity: int = Field(ge=0)
    is_vegetarian: bool = True
    declared_allergens: list[str] = Field(default_factory=list, max_length=30)


class MenuItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    title: str
    category: str
    description: str
    price: Decimal
    capacity: int
    is_vegetarian: bool
    declared_allergens: list[str]
    is_active: bool
