from typing import Any
from datetime import datetime, timezone

from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile, File

import jwt
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.database.session import get_db
from app.dependencies.auth import get_current_user, oauth2_scheme
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead, UserUpdate, UserChangePassword
from app.services.user_service import UserService
from app.cache.redis import redis_client
from app.cache.keys import get_token_blacklist_key

router = APIRouter()

class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    service = UserService(db)
    return await service.create_user(user_in)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    repository = UserRepository(db)

    user = await repository.get_by_email(form_data.username)

    if not user or not security.verify_password(
        form_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    access_token = security.create_access_token(subject=user.id)
    refresh_token = security.create_refresh_token(subject=user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    try:
        payload = jwt.decode(
            token_data.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id = payload.get("sub")
        token_type = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalars().first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    new_access_token = security.create_access_token(subject=user.id)
    new_refresh_token = security.create_refresh_token(subject=user.id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserRead)
async def read_user_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    return current_user



@router.put("/profile", response_model=UserRead)
async def update_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    service = UserService(db)
    return await service.update_user(
        user=current_user,
        user_in=user_in,
    )


@router.put("/change-password", status_code=status.HTTP_200_OK)
async def change_user_password(
    password_data: UserChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = UserService(db)
    await service.change_password(
        user=current_user,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
    )
    return {
        "message": "Password changed successfully."
    }



@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
) -> dict:

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token.",
            )

        exp = payload.get("exp")

        if exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expiration is missing.",
            )

        current_time = datetime.now(timezone.utc).timestamp()
        ttl = int(exp - current_time)

        if ttl <= 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
            )

        key = get_token_blacklist_key(token)

        await redis_client.setex(
            key,
            ttl,
            "blacklisted",
        )

        return {
            "message": "Successfully logged out."
        }

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        )


@router.post(
    "/profile-picture",
    response_model=UserRead,
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG, GIF and WEBP images are allowed.",
        )

    profile_dir = Path("uploads/profile")
    profile_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    extension = Path(
        file.filename or ""
    ).suffix.lower()

    if not extension:
        extension = ".jpg"

    filename = (
        f"{uuid4().hex}{extension}"
    )

    file_path = profile_dir / filename

    file_size = 0
    max_size = 5 * 1024 * 1024

    try:
        with file_path.open("wb") as buffer:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                file_size += len(chunk)

                if file_size > max_size:

                    file_path.unlink(
                        missing_ok=True
                    )

                    raise HTTPException(
                        status_code=413,
                        detail="Profile picture must not exceed 5 MB.",
                    )

                buffer.write(chunk)

    finally:
        await file.close()

    current_user.profile_picture = (
        f"/uploads/profile/{filename}"
    )

    await db.commit()
    await db.refresh(current_user)

    return current_user