from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import BROWSER_SESSION_COOKIE, BROWSER_SESSION_TTL, create_browser_session_token, CurrentUser, password_hasher
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=UserRead, summary="Return the authenticated user")
def get_me(user: CurrentUser) -> UserRead:
    return UserRead(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


@router.post("/login", response_model=UserRead, summary="Create a browser login session")
def login(data: LoginRequest, response: Response, session: DbSession) -> UserRead:
    user = session.scalar(select(User).where(User.email == data.email.strip().lower()))
    valid_password = user is not None and password_hasher.verify(data.password.get_secret_value(), user.password_hash)
    if user is None or not valid_password or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password", headers={"WWW-Authenticate": "Basic"})
    response.set_cookie(
        BROWSER_SESSION_COOKIE,
        create_browser_session_token(user.id),
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=BROWSER_SESSION_TTL,
        path="/",
    )
    return UserRead(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


@router.post("/logout", summary="Clear the browser login session")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(BROWSER_SESSION_COOKIE, path="/")
    return {"logged_out": True}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Register a customer account")
def register(data: RegisterRequest, session: DbSession) -> UserRead:
    user = AuthService(session).register(data)
    return UserRead(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
