from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import get_settings
from app.core.security import CurrentUser
from app.models import User


def enforce_chat_limit(request: Request, user: CurrentUser) -> None:
    limiter = request.app.state.rate_limiter
    if not limiter.allow(f"chat:{user.id}", get_settings().chat_requests_per_minute, 60):
        raise HTTPException(status_code=429, detail="Chat request limit reached; try again shortly")


def enforce_upload_limit(request: Request, user: CurrentUser) -> None:
    limiter = request.app.state.rate_limiter
    if not limiter.allow(f"upload:{user.id}", get_settings().upload_requests_per_minute, 60):
        raise HTTPException(status_code=429, detail="Upload limit reached; try again shortly")


ChatRateLimit = Annotated[None, Depends(enforce_chat_limit)]
UploadRateLimit = Annotated[None, Depends(enforce_upload_limit)]
