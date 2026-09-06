"""Unit tests for core/security.py"""

import time

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_returns_string(self) -> None:
        result = hash_password("mypassword")
        assert isinstance(result, str)

    def test_hash_contains_dollar_separator(self) -> None:
        result = hash_password("mypassword")
        assert "$" in result

    def test_salt_is_random(self) -> None:
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        # Different salts → different hashes
        assert h1 != h2

    def test_verify_correct_password(self) -> None:
        stored = hash_password("correct_password")
        assert verify_password("correct_password", stored) is True

    def test_verify_wrong_password(self) -> None:
        stored = hash_password("correct_password")
        assert verify_password("wrong_password", stored) is False

    def test_verify_empty_password(self) -> None:
        stored = hash_password("")
        assert verify_password("", stored) is True
        assert verify_password("not_empty", stored) is False

    def test_verify_tampered_hash(self) -> None:
        stored = hash_password("password")
        # Tamper with the digest portion
        salt, _, digest = stored.partition("$")
        tampered = f"{salt}$0000{digest[4:]}"
        assert verify_password("password", tampered) is False


class TestJWT:
    def test_create_access_token_returns_string(self) -> None:
        token = create_access_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_refresh_token_returns_string(self) -> None:
        token = create_refresh_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_valid_token(self) -> None:
        token = create_access_token("user-456")
        result = decode_token(token)
        assert result == "user-456"

    def test_decode_refresh_token(self) -> None:
        token = create_refresh_token("user-789")
        result = decode_token(token)
        assert result == "user-789"

    def test_decode_invalid_token(self) -> None:
        result = decode_token("garbage.token.value")
        assert result is None

    def test_decode_tampered_token(self) -> None:
        token = create_access_token("user-123")
        # Flip a character in the middle
        mid = len(token) // 2
        tampered = token[:mid] + ("A" if token[mid] != "A" else "B") + token[mid + 1 :]
        result = decode_token(tampered)
        assert result is None

    def test_access_and_refresh_are_different(self) -> None:
        access = create_access_token("user-1")
        refresh = create_refresh_token("user-1")
        assert access != refresh
        # Both decode to the same user
        assert decode_token(access) == decode_token(refresh) == "user-1"
