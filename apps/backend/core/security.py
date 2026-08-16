import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(plain_password: str, stored: str) -> bool:
    salt, _, digest_hex = stored.partition("$")
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode(), salt.encode(), 100_000
    )
    return secrets.compare_digest(digest.hex(), digest_hex)


def _create_token(subject: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    return _create_token(
        user_id, timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None
