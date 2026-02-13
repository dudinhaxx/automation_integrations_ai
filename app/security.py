from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


async def verify_internal_key(
    request: Request,
    x_internal_agent_api_key: str | None = Header(None, alias="x-internal-agent-api-key"),
    x_internal_key: str | None = Header(None, alias="X-Internal-Key"),
) -> None:
    settings = get_settings()
    if not settings.internal_agent_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal agent key not configured.",
        )
    candidate = x_internal_agent_api_key or x_internal_key or request.headers.get("x-internal-agent-api-key", "")
    if candidate != settings.internal_agent_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal key.",
        )
