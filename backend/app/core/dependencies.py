from typing import Annotated, Optional
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedError, ForbiddenError

security = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {
    "admin": 4,
    "store_manager": 3,
    "depot_staff": 2,
    "store_staff": 1,
}


async def get_current_user_payload(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
) -> dict:
    """Extract and validate JWT payload. Returns the raw payload dict."""
    if not credentials:
        raise UnauthorizedError()
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        return payload
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")


async def get_current_user(
    payload: Annotated[dict, Depends(get_current_user_payload)],
    db: AsyncSession = Depends(get_db),
):
    """Load full user object from DB, verify still active."""
    import uuid as _uuid
    from app.models.user import User

    try:
        user_id = _uuid.UUID(payload.get("sub"))
        tenant_id = _uuid.UUID(payload.get("tid"))
    except (TypeError, ValueError):
        raise UnauthorizedError("Invalid token claims")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("User not found or deactivated")

    # Attach tenant_id from JWT for convenience
    user._jwt_tenant_id = tenant_id
    return user


class RequireRole:
    """Dependency factory that enforces minimum role level."""

    def __init__(self, *allowed_roles: str):
        self.allowed_roles = set(allowed_roles)

    def __call__(self, user=Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise ForbiddenError(
                f"Role '{user.role}' is not permitted for this action. "
                f"Required: {', '.join(self.allowed_roles)}"
            )
        return user


# Reusable role-gated dependencies
require_admin = RequireRole("admin")
require_manager_or_above = RequireRole("admin", "store_manager")
require_depot_staff = RequireRole("admin", "depot_staff")
require_any_role = RequireRole("admin", "store_manager", "depot_staff", "store_staff")

# Type alias for DB session injection
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[any, Depends(get_current_user)]
