import os
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


# --------------------------------------------------
# JWT CONFIGURATION
# --------------------------------------------------

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-secret-change-this-in-production",
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60


# --------------------------------------------------
# PASSWORD HASHING
# --------------------------------------------------

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2.

    Unlike bcrypt, Argon2 does not have bcrypt's
    72-byte password limitation.
    """

    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:

    try:
        return password_hasher.verify(
            password_hash,
            plain_password,
        )

    except VerifyMismatchError:
        return False

    except Exception:
        return False


# --------------------------------------------------
# JWT
# --------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


def create_access_token(
    user_id: int,
) -> str:

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# --------------------------------------------------
# CURRENT USER
# --------------------------------------------------

def get_current_user(
    token: str = Depends(
        oauth2_scheme
    ),

    db: Session = Depends(
        get_db
    ),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,

        detail=(
            "Invalid or expired "
            "authentication token"
        ),

        headers={
            "WWW-Authenticate": "Bearer"
        },
    )

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        user_id = int(user_id)

    except (
        JWTError,
        ValueError,
        TypeError,
    ):

        raise credentials_exception

    user = db.scalar(
        select(User).where(
            User.id == user_id
        )
    )

    if user is None:
        raise credentials_exception

    return user