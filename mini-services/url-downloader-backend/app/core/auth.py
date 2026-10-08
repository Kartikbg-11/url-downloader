"""Authentication helpers for the three-account local login system."""

import asyncio
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


@dataclass(frozen=True)
class AuthUser:
    """Authenticated user identity attached to protected requests."""

    username: str


@dataclass
class Session:
    """Opaque server-side session."""

    username: str
    expires_at: datetime


class AuthService:
    """Validate configured users and manage short-lived in-memory sessions."""

    def __init__(self) -> None:
        settings = get_settings()
        self._users = settings.parsed_auth_users
        self._session_lifetime = timedelta(hours=settings.auth_session_hours)
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _password_digest(password: str) -> bytes:
        return hashlib.sha256(password.encode("utf-8")).digest()

    def authenticate(self, username: str, password: str) -> Optional[AuthUser]:
        """Return a user when credentials match, without leaking which field failed."""
        configured_password = self._users.get(username)
        candidate = self._password_digest(password)
        expected = self._password_digest(configured_password or "")
        if configured_password is None or not hmac.compare_digest(candidate, expected):
            return None
        return AuthUser(username=username)

    async def create_session(self, username: str) -> str:
        """Create and store a cryptographically random session token."""
        token = secrets.token_urlsafe(32)
        async with self._lock:
            self._remove_expired_sessions()
            self._sessions[token] = Session(
                username=username,
                expires_at=datetime.now(timezone.utc) + self._session_lifetime,
            )
        return token

    async def get_user(self, token: Optional[str]) -> Optional[AuthUser]:
        """Resolve an active session token to its user."""
        if not token:
            return None
        async with self._lock:
            session = self._sessions.get(token)
            if not session:
                return None
            if session.expires_at <= datetime.now(timezone.utc):
                self._sessions.pop(token, None)
                return None
            return AuthUser(username=session.username)

    async def delete_session(self, token: Optional[str]) -> None:
        """Invalidate a session if it exists."""
        if not token:
            return
        async with self._lock:
            self._sessions.pop(token, None)

    def _remove_expired_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [token for token, session in self._sessions.items() if session.expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)


auth_service = AuthService()


def get_auth_service() -> AuthService:
    return auth_service


async def get_current_user(request: Request) -> AuthUser:
    """FastAPI dependency requiring an active login session."""
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    user = await auth_service.get_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Please sign in to continue.",
                }
            },
        )
    return user
