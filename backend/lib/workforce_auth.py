import os

from fastapi import HTTPException, Request

from lib.auth import current_user


async def require_workforce_admin(request: Request) -> dict:
    """Require a real authenticated admin; workforce records are never public."""
    if os.environ.get("AUTH_DISABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=503, detail="workforce_authentication_required")

    user = await current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin_only")
    return user
