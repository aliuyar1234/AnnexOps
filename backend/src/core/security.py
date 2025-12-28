"""Security utilities for password hashing and JWT token management."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import bcrypt
import jwt
from jwt import exceptions as jwt_exceptions

from src.core.config import get_settings

settings = get_settings()

# Load common passwords list at module initialization
_COMMON_PASSWORDS_FILE = Path(__file__).parent / "common_passwords.txt"
_COMMON_PASSWORDS = set()

if _COMMON_PASSWORDS_FILE.exists():
    with open(_COMMON_PASSWORDS_FILE, encoding="utf-8") as f:
        _COMMON_PASSWORDS = {line.strip().lower() for line in f if line.strip()}


class PasswordValidationError(ValueError):
    """Raised when password validation fails."""

    pass


def validate_password(password: str) -> None:
    """Validate password meets security requirements.

    Requirements (FR-A11, SC-006):
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - Not in common passwords list

    Args:
        password: Plain text password to validate

    Raises:
        PasswordValidationError: If password does not meet requirements
    """
    if len(password) < 8:
        raise PasswordValidationError("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        raise PasswordValidationError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        raise PasswordValidationError("Password must contain at least one lowercase letter")

    if not re.search(r"\d", password):
        raise PasswordValidationError("Password must contain at least one digit")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise PasswordValidationError("Password must contain at least one special character")

    # Check against common passwords list (case-insensitive)
    if password.lower() in _COMMON_PASSWORDS:
        raise PasswordValidationError(
            "Password is too common. Please choose a more unique password"
        )


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    # Generate salt and hash password
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token.

    Args:
        data: Dictionary of claims to encode in the token

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string to decode

    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt_exceptions.PyJWTError:
        return None
