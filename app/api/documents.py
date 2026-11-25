from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import AdminUser
from app.api.limits import UploadRateLimit
from app.schemas.documents import DocumentRead
from app.ai.rag import RagService

router = APIRouter(prefix="/api/documents", tags=["documents"])
DbSession = Annotated[Session, Depends(get_db)]

ALLOWED_MEDIA_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain"},
}


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED, summary="Upload and index a policy document (admin)")
def upload_document(
    session: DbSession,
    user: AdminUser,
    _rate_limit: UploadRateLimit,
    upload: Annotated[UploadFile, File(description="PDF, DOCX, or UTF-8 TXT policy document")],
) -> DocumentRead:
    extension = Path(upload.filename or "").suffix.lower()
    accepted_types = ALLOWED_MEDIA_TYPES.get(extension)
    if accepted_types is None or upload.content_type not in accepted_types:
        raise HTTPException(status_code=415, detail="Upload must be a PDF, DOCX, or TXT file with a matching media type")
    content = upload.file.read(get_settings().upload_max_bytes + 1)
    if len(content) > get_settings().upload_max_bytes:
        raise HTTPException(status_code=413, detail="Document exceeds the configured upload limit")
    try:
        return RagService(session).upload(user.id, upload.filename or "policy.txt", content, upload.content_type or "text/plain")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Document indexing is temporarily unavailable") from exc
    finally:
        upload.file.close()
