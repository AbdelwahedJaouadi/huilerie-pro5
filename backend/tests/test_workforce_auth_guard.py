import pytest
from fastapi import HTTPException

from lib import workforce_auth


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["1", "true", "yes", "on", " TRUE "])
async def test_workforce_routes_fail_closed_when_auth_disabled(monkeypatch, value):
    monkeypatch.setenv("AUTH_DISABLED", value)

    async def unexpected_current_user(_request):
        raise AssertionError("current_user must not run in public mode")

    monkeypatch.setattr(workforce_auth, "current_user", unexpected_current_user)

    with pytest.raises(HTTPException) as exc:
        await workforce_auth.require_workforce_admin(None)

    assert exc.value.status_code == 503
    assert exc.value.detail == "workforce_authentication_required"


@pytest.mark.asyncio
async def test_authenticated_admin_can_access_workforce(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "false")

    async def admin_user(_request):
        return {"id": "admin-1", "role": "admin"}

    monkeypatch.setattr(workforce_auth, "current_user", admin_user)

    result = await workforce_auth.require_workforce_admin(None)

    assert result["id"] == "admin-1"


@pytest.mark.asyncio
async def test_authenticated_worker_is_forbidden(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "false")

    async def worker_user(_request):
        return {"id": "worker-1", "role": "worker"}

    monkeypatch.setattr(workforce_auth, "current_user", worker_user)

    with pytest.raises(HTTPException) as exc:
        await workforce_auth.require_workforce_admin(None)

    assert exc.value.status_code == 403
    assert exc.value.detail == "admin_only"


@pytest.mark.asyncio
async def test_missing_session_error_is_preserved(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "false")

    async def unauthenticated(_request):
        raise HTTPException(status_code=401, detail="not_authenticated")

    monkeypatch.setattr(workforce_auth, "current_user", unauthenticated)

    with pytest.raises(HTTPException) as exc:
        await workforce_auth.require_workforce_admin(None)

    assert exc.value.status_code == 401
