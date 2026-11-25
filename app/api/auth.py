from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser
from app.models import User
from app.schemas.auth import RegisterRequest, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=UserRead, summary="Return the authenticated user")
def get_me(user: CurrentUser) -> UserRead:
    return UserRead(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Register a customer account")
def register(data: RegisterRequest, session: DbSession) -> UserRead:
    user = AuthService(session).register(data)
    return UserRead(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
