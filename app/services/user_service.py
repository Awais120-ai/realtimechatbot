from typing import Union, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import get_password_hash, verify_password
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.models.user import User


class UserService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = UserRepository(db)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.repository.get_by_id(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        return await self.repository.get_by_email(email)

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.repository.get_by_username(username)

    async def create_user(
        self,
        user_in: Optional[UserCreate] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> User:
        if user_in is not None:
            user_email = user_in.email
            user_name = user_in.username
            user_password = user_in.password
        else:
            if not email or not username or not password:
                raise ValueError("email, username, and password are required")
            user_email = email
            user_name = username
            user_password = password

        existing_email = await self.repository.get_by_email(user_email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The user with this email already exists in the system.",
            )

        existing_username = await self.repository.get_by_username(user_name)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The username is already taken.",
            )

        hashed_password = get_password_hash(user_password)
        return await self.repository.create(
            email=user_email,
            username=user_name,
            hashed_password=hashed_password,
        )

    async def update_user(
        self,
        user: User,
        user_in: UserUpdate,
    ) -> User:
        if user_in.email is not None:
            result = await self.db.execute(
                select(User).where(
                    User.email == user_in.email,
                    User.id != user.id,
                )
            )
            existing_user = result.scalars().first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists.",
                )
            user.email = user_in.email

        if user_in.username is not None:
            result = await self.db.execute(
                select(User).where(
                    User.username == user_in.username,
                    User.id != user.id,
                )
            )

            existing_user = result.scalars().first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists.",
                )
            user.username = user_in.username

        if user_in.avatar_url is not None:
            user.avatar_url = user_in.avatar_url

        if user_in.profile_picture is not None:
            user.profile_picture = user_in.profile_picture  

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> User:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        if current_password == new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password.",
            )

        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        await self.db.refresh(user)
        return user