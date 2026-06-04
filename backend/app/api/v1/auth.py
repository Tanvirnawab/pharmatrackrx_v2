from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.session import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.dependencies import get_current_user
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.schemas import LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse, UserOut
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_token_response(user: User) -> dict:
    access = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
        store_id=str(user.store_id) if user.store_id else None,
        depot_id=str(user.depot_id) if user.depot_id else None,
    )
    refresh = create_refresh_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password")

    # Update last login
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login_at=datetime.now(timezone.utc))
    )

    return _build_token_response(user)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type")
    except JWTError:
        raise UnauthorizedError("Invalid or expired refresh token")

    import uuid as _uuid
    result = await db.execute(
        select(User).where(User.id == _uuid.UUID(payload["sub"]), User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User not found")

    access = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
        store_id=str(user.store_id) if user.store_id else None,
        depot_id=str(user.depot_id) if user.depot_id else None,
    )
    return {"access_token": access, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
