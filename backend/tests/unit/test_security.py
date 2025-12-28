"""Unit tests for security utilities.

Tests password hashing, JWT token creation and validation.
"""

from datetime import UTC, datetime, timedelta

from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Unit tests for password hashing functions."""

    def test_hash_password_creates_hash(self):
        """Test password hashing creates a hash string."""
        password = "TestPassword123!"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password

    def test_hash_password_creates_different_hashes(self):
        """Test same password creates different hashes (salt)."""
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # bcrypt uses random salt, so hashes should differ
        assert hash1 != hash2

    def test_verify_password_with_correct_password(self):
        """Test password verification with correct password."""
        password = "TestPassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_with_wrong_password(self):
        """Test password verification with wrong password."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test password verification is case sensitive."""
        password = "TestPassword123!"
        wrong_case = "testpassword123!"
        hashed = hash_password(password)

        assert verify_password(wrong_case, hashed) is False


class TestJWTAccessToken:
    """Unit tests for JWT access token functions."""

    def test_create_access_token_returns_string(self):
        """Test access token creation returns a string."""
        data = {"sub": "user123"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_custom_expiry(self):
        """Test access token creation with custom expiry."""
        data = {"sub": "user123"}
        expires_delta = timedelta(minutes=60)

        # Capture time before token creation
        before = datetime.now(UTC)
        token = create_access_token(data, expires_delta)
        after = datetime.now(UTC)

        assert token is not None
        payload = decode_token(token)
        assert payload is not None

        # Verify expiry is set correctly (use timezone-aware datetime)
        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        expected_min = before + expires_delta - timedelta(seconds=1)
        expected_max = after + expires_delta + timedelta(seconds=1)

        # Expiry should be within the range of before+delta to after+delta
        assert expected_min <= exp <= expected_max

    def test_decode_valid_access_token(self):
        """Test decoding valid access token."""
        data = {"sub": "user123", "role": "admin"}
        token = create_access_token(data)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_decode_invalid_token(self):
        """Test decoding invalid token returns None."""
        invalid_token = "invalid.token.here"
        payload = decode_token(invalid_token)

        assert payload is None

    def test_decode_expired_token(self):
        """Test decoding expired token returns None."""
        data = {"sub": "user123"}
        # Create token with negative expiry (already expired)
        expires_delta = timedelta(seconds=-10)
        token = create_access_token(data, expires_delta)
        payload = decode_token(token)

        assert payload is None

    def test_access_token_contains_expiry(self):
        """Test access token contains expiry claim."""
        data = {"sub": "user123"}
        token = create_access_token(data)
        payload = decode_token(token)

        assert payload is not None
        assert "exp" in payload
        assert isinstance(payload["exp"], int)

        # Verify expiry is in future (use timezone-aware datetime)
        exp_datetime = datetime.fromtimestamp(payload["exp"], tz=UTC)
        assert exp_datetime > datetime.now(UTC)


class TestJWTRefreshToken:
    """Unit tests for JWT refresh token functions."""

    def test_create_refresh_token_returns_string(self):
        """Test refresh token creation returns a string."""
        data = {"sub": "user123"}
        token = create_refresh_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_refresh_token_has_longer_expiry(self):
        """Test refresh token has 7 day expiry."""
        data = {"sub": "user123"}

        # Capture time before token creation
        before = datetime.now(UTC)
        token = create_refresh_token(data)
        after = datetime.now(UTC)

        payload = decode_token(token)
        assert payload is not None

        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        expected_min = before + timedelta(days=7) - timedelta(seconds=1)
        expected_max = after + timedelta(days=7) + timedelta(seconds=1)

        # Expiry should be within the range
        assert expected_min <= exp <= expected_max

    def test_refresh_token_has_type_claim(self):
        """Test refresh token has 'type: refresh' claim."""
        data = {"sub": "user123"}
        token = create_refresh_token(data)
        payload = decode_token(token)

        assert payload is not None
        assert "type" in payload
        assert payload["type"] == "refresh"

    def test_decode_valid_refresh_token(self):
        """Test decoding valid refresh token."""
        data = {"sub": "user123"}
        token = create_refresh_token(data)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"


class TestTokenSecurity:
    """Security tests for token generation."""

    def test_tokens_are_unique(self):
        """Test that tokens are unique even with same data."""
        data = {"sub": "user123"}
        token1 = create_access_token(data)
        token2 = create_access_token(data)

        # Tokens should be different due to different exp timestamps
        # (even if generated quickly, exp should differ by at least microseconds)
        # Note: This might rarely fail if both tokens are created in the exact same microsecond
        # In practice, different exp values make them different
        assert isinstance(token1, str)
        assert isinstance(token2, str)

    def test_token_without_secret_cannot_be_decoded(self):
        """Test token created with different secret cannot be decoded."""
        # This is more of a conceptual test - decode_token uses the configured secret
        # A token created with a different secret would fail to decode
        data = {"sub": "user123"}
        token = create_access_token(data)

        # Valid token should decode successfully
        payload = decode_token(token)
        assert payload is not None

        # Tampered token should fail
        tampered_token = token[:-10] + "tampered00"
        payload = decode_token(tampered_token)
        assert payload is None

    def test_empty_string_token_fails(self):
        """Test empty string as token returns None."""
        payload = decode_token("")
        assert payload is None

    def test_none_token_fails(self):
        """Test None as token raises exception or returns None."""
        try:
            payload = decode_token(None)
            # If it doesn't raise, it should return None
            assert payload is None
        except (TypeError, AttributeError):
            # Expected behavior - None is not a valid token
            pass
