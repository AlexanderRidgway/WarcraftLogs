import logging
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    import warnings
    warnings.warn(
        "JWT_SECRET environment variable is not set. Using an insecure default for local development only.",
        stacklevel=1,
    )
    JWT_SECRET = "local-dev-only-not-for-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# Email config: SMTP preferred, SES as fallback
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER

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
    subject = "CRANK \u2014 Password Reset"
    html_body = (
        f"<p>You requested a password reset for your CRANK officer account.</p>"
        f'<p><a href="{reset_url}">Click here to reset your password</a></p>'
        f"<p>This link expires in {RESET_TOKEN_EXPIRE_HOURS} hour(s).</p>"
        f"<p>If you did not request this, ignore this email.</p>"
    )
    text_body = (
        f"You requested a password reset for your CRANK officer account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in {RESET_TOKEN_EXPIRE_HOURS} hour(s).\n\n"
        f"If you did not request this, ignore this email."
    )

    if SMTP_HOST and SMTP_USER:
        _send_via_smtp(to_email, subject, html_body, text_body)
    elif SES_SENDER_EMAIL:
        _send_via_ses(to_email, subject, html_body, text_body)
    else:
        raise RuntimeError("No email provider configured (set SMTP_HOST/SMTP_USER or SES_SENDER_EMAIL)")


def _send_via_smtp(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, to_email, msg.as_string())
    logger.info("Password reset email sent via SMTP to %s", to_email)


def _send_via_ses(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    import boto3
    ses = boto3.client("ses", region_name=SES_REGION)
    ses.send_email(
        Source=SES_SENDER_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {
                "Html": {"Data": html_body},
                "Text": {"Data": text_body},
            },
        },
    )
    logger.info("Password reset email sent via SES to %s", to_email)


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
    if user.role != "officer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Officer role required")
    return user
