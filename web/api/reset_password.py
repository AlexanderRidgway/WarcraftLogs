"""CLI to reset an officer account password.

Usage: python -m web.api.reset_password <email> <new_password>
"""
import asyncio
import sys

from sqlalchemy import select

from web.api.database import engine, async_session
from web.api.models import Base, User
from web.api.auth import hash_password


async def main():
    if len(sys.argv) != 3:
        print("Usage: python -m web.api.reset_password <email> <new_password>")
        sys.exit(1)

    email, new_password = sys.argv[1], sys.argv[2]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            print(f"No user found with email '{email}'.")
            sys.exit(1)

        user.password_hash = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await session.commit()
        print(f"Password reset for '{email}' successful.")


if __name__ == "__main__":
    asyncio.run(main())
