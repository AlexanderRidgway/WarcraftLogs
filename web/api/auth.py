import os
import secrets
from datetime import datetime, timedelta, timezone

import boto3
import jwt
from botocore.exceptions import ClientError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "")
SES_REGION = os.getenv("AWS_REGION", "us-east-1")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
RESET_TOKEN_EXPIRE_HOURS = 1


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": email, "exp": expire},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def send_reset_email(to_email: str, reset_token: str) -> None:
    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
    ses = boto3.client("ses", region_name=SES_REGION)
    ses.send_email(
        Source=SES_SENDER_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": "CRANK — Password Reset"},
            "Body": {
                "Html": {
                    "Data": (
                        f"<p>You requested a password reset for your CRANK officer account.</p>"
                        f'<p><a href="{reset_url}">Click here to reset your password</a></p>'
                        f"<p>This link expires in {RESET_TOKEN_EXPIRE_HOURS} hour(s).</p>"
                        f"<p>If you did not request this, ignore this email.</p>"
                    )
                },
                "Text": {
                    "Data": (
                        f"You requested a password reset for your CRANK officer account.\n\n"
                        f"Reset your password: {reset_url}\n\n"
                        f"This link expires in {RESET_TOKEN_EXPIRE_HOURS} hour(s).\n\n"
                        f"If you did not request this, ignore this email."
                    )
                },
            },
        },
    )


async def get_current_officer(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    from web.api.models import User
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
