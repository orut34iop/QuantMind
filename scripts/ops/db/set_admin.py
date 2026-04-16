import asyncio
import os
from sqlalchemy import update
from backend.services.api.user_app.models.user import User
from backend.shared.database_manager_v2 import get_session, init_database

async def make_admin(username: str):
    await init_database()
    async with get_session(read_only=False) as session:
        stmt = update(User).where(User.username == username).values(is_admin=True)
        await session.execute(stmt)
        await session.commit()
        print(f"User {username} is now an admin.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python set_admin.py <username>")
    else:
        asyncio.run(make_admin(sys.argv[1]))
