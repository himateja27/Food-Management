import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi import Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import User

basic_scheme = HTTPBasic(auto_error=False)
password_hasher = PasswordHash.recommended()
_dummy_password_hash = password_hasher.hash("unusable-demo-password")


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    internal_actor = request.headers.get("X-Internal-Actor")
    internal_timestamp = request.headers.get("X-Internal-Timestamp")
    internal_signature = request.headers.get("X-Internal-Signature")
    if internal_actor or internal_timestamp or internal_signature:
        settings = get_settings()
        try:
            actor_id = int(internal_actor or "")
            timestamp = int(internal_timestamp or "")
        except ValueError:
            actor_id = 0
            timestamp = 0
        message = f"{actor_id}:{timestamp}".encode()
        expected = hmac.new(settings.internal_api_secret.encode(), message, hashlib.sha256).hexdigest()
        if (
            not settings.internal_api_secret
            or actor_id <= 0
            or abs(int(time.time()) - timestamp) > 60
            or not hmac.compare_digest(expected, internal_signature or "")
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal identity")
        user = session.get(User, actor_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal identity")
        return user
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Basic"})
    user = session.scalar(select(User).where(User.email == credentials.username.lower()))
    stored_hash = user.password_hash if user is not None else _dummy_password_hash
    valid_password = password_hasher.verify(credentials.password, stored_hash)
    if user is None or not valid_password or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password", headers={"WWW-Authenticate": "Basic"})
    return user


def create_internal_identity_headers(user_id: int) -> dict[str, str]:
    settings = get_settings()
    if len(settings.internal_api_secret) < 32:
        raise RuntimeError("Internal API signing secret is not configured")
    timestamp = str(int(time.time()))
    message = f"{user_id}:{timestamp}".encode()
    signature = hmac.new(settings.internal_api_secret.encode(), message, hashlib.sha256).hexdigest()
    return {
        "X-Internal-Actor": str(user_id),
        "X-Internal-Timestamp": timestamp,
        "X-Internal-Signature": signature,
    }


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
