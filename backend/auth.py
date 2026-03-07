"""Google OAuth2 flow, DB-backed sessions, and JWT helpers."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, Request, Response

from jose import JWTError, jwt

from backend.db import execute, fetchone, fetchone_with_return

_ALGORITHM = "HS256"
_SESSION_EXPIRE_DAYS = 7
_CSRF_COOKIE = "oauth_state"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET environment variable is not set")
    return secret


# ── Session management ────────────────────────────────────────────────────────

def create_session(user_id: int) -> dict[str, Any]:
    """Insert a session row; return {id, expires_at}."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=_SESSION_EXPIRE_DAYS)
    row = fetchone_with_return(
        """
        INSERT INTO sessions (user_id, expires_at)
        VALUES (%s, %s)
        RETURNING id::text, expires_at
        """,
        (user_id, expires_at),
    )
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create session")
    return row


def revoke_session(session_id: str) -> None:
    """Mark a session as revoked (logout)."""
    execute(
        "UPDATE sessions SET revoked = TRUE WHERE id = %s",
        (session_id,),
    )


def _get_active_session(session_id: str) -> dict[str, Any] | None:
    """Return session row if active (not revoked, not expired)."""
    return fetchone(
        """
        SELECT id::text, user_id, expires_at
        FROM sessions
        WHERE id = %s AND revoked = FALSE AND expires_at > now()
        """,
        (session_id,),
    )


# ── JWT (embeds session id as jti) ────────────────────────────────────────────

def create_access_token(user_id: int) -> str:
    """Create a JWT whose jti is a new DB session id."""
    session = create_session(user_id)
    session_id = session["id"]
    expires_at = session["expires_at"]
    payload = {
        "sub": str(user_id),
        "jti": session_id,
        "exp": expires_at,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_ALGORITHM)


def verify_token(token: str) -> tuple[int, str]:
    """Verify JWT signature+expiry AND DB session. Returns (user_id, session_id)."""
    try:
        data = jwt.decode(token, _jwt_secret(), algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = data.get("sub")
    session_id = data.get("jti")
    if not user_id or not session_id:
        raise HTTPException(status_code=401, detail="Malformed token")

    session = _get_active_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or revoked")

    return int(user_id), session_id


def get_current_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency: verify Bearer token + session; return user row."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth[len("Bearer "):]
    user_id, _ = verify_token(token)
    user = fetchone(
        "SELECT id, email, name, picture FROM users WHERE id = %s",
        (user_id,),
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_session_id_from_request(request: Request) -> str | None:
    """Extract the session id from a Bearer token without raising."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        token = auth[len("Bearer "):]
        data = jwt.decode(token, _jwt_secret(), algorithms=[_ALGORITHM])
        return data.get("jti")
    except JWTError:
        return None


def get_current_user_optional(request: Request) -> dict[str, Any] | None:
    """Like get_current_user but returns None if not authenticated."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return get_current_user(request)
    except HTTPException:
        return None


# ── CSRF state ────────────────────────────────────────────────────────────────

def generate_oauth_state(response: Response) -> str:
    """Generate a random CSRF state token and store it in an httpOnly cookie."""
    state = secrets.token_urlsafe(32)
    response.set_cookie(
        key=_CSRF_COOKIE,
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600,  # 10 minutes — long enough to complete OAuth
    )
    return state


def verify_oauth_state(request: Request, state: str) -> None:
    """Verify the OAuth state param matches the cookie. Raises 400 on mismatch."""
    expected = request.cookies.get(_CSRF_COOKIE)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state (CSRF check failed)")


# ── Google OAuth flow ─────────────────────────────────────────────────────────

def google_auth_url(state: str) -> str:
    """Return the Google OAuth2 consent URL with state param."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    redirect_uri = os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
    )
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    })
    return f"{GOOGLE_AUTH_URL}?{params}"


async def exchange_code_for_user(code: str) -> dict[str, Any]:
    """Exchange OAuth code for Google user info."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
    )
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()


# ── User upsert (handles email conflict) ─────────────────────────────────────

def upsert_user(google_info: dict[str, Any]) -> dict[str, Any]:
    """
    Insert or update user by google_id.

    Email conflict handling: if the same email already exists with a different
    google_id, we link the accounts by updating the google_id on the existing
    row (graceful account linking).
    """
    google_id = google_info.get("sub")
    email = google_info.get("email")
    name = google_info.get("name")
    picture = google_info.get("picture")

    row = fetchone_with_return(
        """
        INSERT INTO users (google_id, email, name, picture, last_login)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (google_id) DO UPDATE
          SET email      = EXCLUDED.email,
              name       = EXCLUDED.name,
              picture    = EXCLUDED.picture,
              last_login = now()
        RETURNING id, google_id, email, name, picture, created_at, last_login
        """,
        (google_id, email, name, picture),
    )

    if not row:
        # Email conflict with different google_id → link accounts
        row = fetchone_with_return(
            """
            UPDATE users
            SET google_id  = %s,
                name       = %s,
                picture    = %s,
                last_login = now()
            WHERE email = %s
            RETURNING id, google_id, email, name, picture, created_at, last_login
            """,
            (google_id, name, picture, email),
        )

    if not row:
        raise HTTPException(status_code=500, detail="Failed to upsert user")
    return row
