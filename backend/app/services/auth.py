from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select

from app.core.errors import AppError
from app.repositories.models import AuthSessionModel, UserDeviceModel, UserModel

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 256
ACCESS_ALGORITHM = "HS256"


class AuthService:
    def __init__(self, session, secret: str, access_minutes=15, refresh_days=30):
        self.session = session
        self.secret = secret
        self.access_minutes = access_minutes
        self.refresh_days = refresh_days
        self.passwords = PasswordHasher()

    @staticmethod
    def normalize(identifier: str) -> str:
        return identifier.strip().casefold()

    @staticmethod
    def validate_password(password: str) -> None:
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            raise AppError(
                "VALIDATION_ERROR",
                f"password length must be within [{MIN_PASSWORD_LENGTH},{MAX_PASSWORD_LENGTH}]",
                422,
            )

    async def register(self, identifier: str, password: str):
        normalized = self.normalize(identifier)
        self.validate_password(password)
        if not normalized:
            raise AppError("VALIDATION_ERROR", "login identifier is required", 422)
        if await self.session.scalar(
            select(UserModel.id).where(UserModel.login_identifier == normalized)
        ):
            raise AppError("ACCOUNT_EXISTS", "account already exists", 409)
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            login_identifier=normalized,
            password_hash=self.passwords.hash(password),
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        await self.session.commit()
        return user

    async def login(self, identifier: str, password: str) -> dict:
        user = await self.session.scalar(
            select(UserModel).where(UserModel.login_identifier == self.normalize(identifier))
        )
        if user is None:
            raise AppError("UNAUTHENTICATED", "invalid credentials", 401)
        if user.status != "ACTIVE":
            raise AppError("FORBIDDEN", "account is disabled", 403)
        try:
            self.passwords.verify(user.password_hash, password)
        except VerifyMismatchError as error:
            raise AppError("UNAUTHENTICATED", "invalid credentials", 401) from error
        return await self._issue(user)

    async def _issue(self, user: UserModel) -> dict:
        now = datetime.now(UTC)
        session_id = uuid4()
        refresh = token_urlsafe(48)
        self.session.add(
            AuthSessionModel(
                id=session_id,
                user_id=user.id,
                refresh_token_hash=self._hash(refresh),
                expires_at=now + timedelta(days=self.refresh_days),
                created_at=now,
            )
        )
        await self.session.commit()
        return {
            "access_token": self._access(user.id, session_id, now),
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": self.access_minutes * 60,
        }

    def _access(self, user_id: UUID, session_id: UUID, now: datetime) -> str:
        return jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(session_id),
                "jti": str(uuid4()),
                "iat": now,
                "exp": now + timedelta(minutes=self.access_minutes),
            },
            self.secret,
            algorithm=ACCESS_ALGORITHM,
        )

    async def authenticate(self, token: str) -> UserModel:
        try:
            claims = jwt.decode(token, self.secret, algorithms=[ACCESS_ALGORITHM])
            user_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
        except Exception as error:
            raise AppError("UNAUTHENTICATED", "invalid or expired access token", 401) from error
        auth_session = await self.session.get(AuthSessionModel, session_id)
        user = await self.session.get(UserModel, user_id)
        if auth_session is None or auth_session.revoked_at is not None or user is None:
            raise AppError("UNAUTHENTICATED", "session is revoked", 401)
        if user.status != "ACTIVE":
            raise AppError("FORBIDDEN", "account is disabled", 403)
        return user

    async def refresh(self, refresh_token: str) -> dict:
        now = datetime.now(UTC)
        current = await self.session.scalar(
            select(AuthSessionModel).where(
                AuthSessionModel.refresh_token_hash == self._hash(refresh_token)
            )
        )
        if current is None or current.revoked_at is not None or current.expires_at <= now:
            raise AppError("UNAUTHENTICATED", "refresh token is invalid", 401)
        current.revoked_at = now
        current.rotated_at = now
        user = await self.session.get(UserModel, current.user_id)
        await self.session.flush()
        return await self._issue(user)

    async def logout(self, refresh_token: str) -> None:
        current = await self.session.scalar(
            select(AuthSessionModel).where(
                AuthSessionModel.refresh_token_hash == self._hash(refresh_token)
            )
        )
        if current is not None and current.revoked_at is None:
            current.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def upsert_device(self, user_id: UUID, public_id: str, name, platform, app_version):
        row = await self.session.scalar(
            select(UserDeviceModel).where(
                UserDeviceModel.user_id == user_id,
                UserDeviceModel.device_public_id == public_id,
            )
        )
        now = datetime.now(UTC)
        if row is None:
            row = UserDeviceModel(
                id=uuid4(),
                user_id=user_id,
                device_public_id=public_id,
                name=name,
                platform=platform,
                app_version=app_version,
                created_at=now,
                last_seen_at=now,
            )
            self.session.add(row)
        else:
            row.name, row.platform, row.app_version, row.last_seen_at = (
                name,
                platform,
                app_version,
                now,
            )
            row.revoked_at = None
        await self.session.commit()
        return row

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode()).hexdigest()
