"""CLI to create officer accounts.

Usage: python -m web.api.create_user <email> <password>
"""
import asyncio
import sys

from sqlalchemy import select

from web.api.database import engine, async_session
from web.api.models import Base, User
from web.api.auth import hash_password


async def main():
    if len(sys.argv) != 3:
        print("Usage: python -m web.api.create_user <email> <password>")
        sys.exit(1)

    email, password = sys.argv[1], sys.argv[2]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"User '{email}' already exists.")
            sys.exit(1)

        user = User(email=email, password_hash=hash_password(password), role="officer")
        session.add(user)
        await session.commit()
        print(f"Officer account '{email}' created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
