from pydantic import BaseModel
from pydantic import ConfigDict, Field, SecretStr


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: str

class RegisterRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "full_name": "Mira Patel",
            "email": "mira@example.test",
            "password": "DinnerTable123!",
        }
    })

    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=8, max_length=128)
