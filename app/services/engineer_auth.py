"""
Engineer authentication service.

Issues and verifies short-lived JWT tokens for engineer dashboard sessions.
Multiple engineers can be active simultaneously; each gets their own token.
"""
import jwt
import time
from app.core.config import settings

_ALGORITHM = "HS256"
_EXPIRY_SECONDS = 86400  # 24 hours


def create_engineer_token(name: str) -> str:
    """Issue a signed JWT for an engineer session."""
    payload = {
        "sub": name,
        "type": "engineer",
        "iat": int(time.time()),
        "exp": int(time.time()) + _EXPIRY_SECONDS,
    }
    return jwt.encode(payload, settings.ENGINEER_JWT_SECRET, algorithm=_ALGORITHM)


def verify_engineer_token(token: str) -> dict:
    """
    Decode and validate an engineer JWT.
    Returns the decoded payload dict on success.
    Raises jwt.PyJWTError on failure (expired, invalid sig, wrong type).
    """
    payload = jwt.decode(token, settings.ENGINEER_JWT_SECRET, algorithms=[_ALGORITHM])
    if payload.get("type") != "engineer":
        raise jwt.InvalidTokenError("Token is not an engineer token")
    return payload
