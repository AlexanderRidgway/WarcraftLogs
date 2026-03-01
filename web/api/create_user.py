"""CLI to create officer accounts.

Usage: python -m web.api.create_user <username> <password>
"""
import asyncio
import sys

from sqlalchemy import select

from web.api.database import engine, async_session
from web.api.models import Base, User
from web.api.auth import hash_password


async def main():
    if len(sys.argv) != 3:
        print("Usage: python -m web.api.create_user <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            sys.exit(1)

        user = User(username=username, password_hash=hash_password(password), role="officer")
        session.add(user)
        await session.commit()
        print(f"Officer account '{username}' created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
