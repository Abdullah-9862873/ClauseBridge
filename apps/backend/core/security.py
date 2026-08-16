import hashlib
import secrets


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
