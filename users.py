import contextlib
import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
    
)

from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.exceptions import UserAlreadyExists
from sqlalchemy import select
from starlette.config import Config
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.openid import OpenID

from db import get_async_session, get_user_db
from models import CompanyModel, PhoneListModel, SoundFileModel, User
from schemas import UserCreate

config = Config('.env')
SECRET = "SECRET"

GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = config('GOOGLE_REDIRECT_URI')

# GITHUB_CLIENT_ID = config('GITHUB_CLIENT_ID')
# GITHUB_CLIENT_SECRET = config('GITHUB_CLIENT_SECRET')

openid_oauth_client = OpenID(
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    'https://accounts.google.com/.well-known/openid-configuration'
)

google_oauth_client = GoogleOAuth2(
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    scopes=["openid", "email", "profile"]
)

# github_oauth_client = GitHubOAuth2(
#     GITHUB_CLIENT_ID,
#     GITHUB_CLIENT_SECRET
# )

class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
            self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
            self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)

get_async_session_context = contextlib.asynccontextmanager(get_async_session)
get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


async def create_user_pro(email: str, password: str, is_superuser: bool = False):
    try:
        async with get_async_session_context() as session:
            async with get_user_db_context(session) as user_db:
                async with get_user_manager_context(user_db) as user_manager:
                    user = await user_manager.create(
                        UserCreate(
                            email=email, password=password, is_superuser=is_superuser
                        )
                    )
                    print(f"User created {user} {email} {password}")
    except UserAlreadyExists:
        print(f"User {email} already exists")


async def get_all_users():
    async with get_async_session_context() as session:
        async with session.begin():
            result = await session.execute(select(User))
            users = result.scalars().all()
            return users


async def create_company_pro(name: str, com_limit: int, day_limit: int, sound_file_id: int, status: int, start_time,
                         end_time, days, reaction, phones_id: int, user_id: int):
    async with get_async_session_context() as session:
        company = CompanyModel(name=name, com_limit=com_limit, day_limit=day_limit, sound_file_id=sound_file_id,
                               status=status, start_time=start_time, end_time=end_time, days=days, reaction=reaction,
                               phones_id=phones_id, user_id=user_id)
        session.add(company)
        await session.commit()
        print(f"Company created {company}")


async def create_sound_file_pro(name: str, file_path: str, user_id: int):
    async with get_async_session_context() as session:
        sound_file = SoundFileModel(name=name, file_path=file_path, user_id=user_id)
        session.add(sound_file)
        await session.commit()
        print(f"SoundFile created {sound_file}")


async def create_phone_list_pro(name: str, phones, user_id: int):
    async with get_async_session_context() as session:
        phone_list = PhoneListModel(name=name, phones=phones, user_id=user_id)
        session.add(phone_list)
        await session.commit()
        print(f"PhoneList created {phone_list}")
