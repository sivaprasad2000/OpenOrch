
import asyncio
import asyncpg
from app.core.config import settings


async def create_database():

    url_parts = settings.DATABASE_URL.replace("postgresql+asyncpg://", "").split("/")
    dbname = url_parts[-1]
    connection_str = url_parts[0]

    user_pass, host_port = connection_str.split("@")
    user, password = user_pass.split(":")
    host, port = host_port.split(":")

    conn = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database="postgres"
    )

    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", dbname
        )

        if not exists:
            await conn.execute(f'CREATE DATABASE "{dbname}"')
            print(f"✓ Database '{dbname}' created successfully!")
        else:
            print(f"✓ Database '{dbname}' already exists.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_database())
