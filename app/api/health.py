from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check application availability")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
