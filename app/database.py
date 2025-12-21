from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Support both PostgreSQL and SQLite
database_url = settings.database_url

# Convert SQLite URL for async driver if needed
if database_url.startswith("sqlite:"):
    database_url = database_url.replace("sqlite:", "sqlite+aiosqlite:")
elif database_url.startswith("postgresql:") and "asyncpg" not in database_url:
    database_url = database_url.replace("postgresql:", "postgresql+asyncpg:")

engine = create_async_engine(
    database_url,
    echo=settings.debug,
    pool_pre_ping=True if "postgresql" in database_url else False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # Check for SQLite "not a database" error
        is_sqlite_error = "sqlite" in str(e).lower() or "file is not a database" in str(e).lower()
        if is_sqlite_error and "sqlite" in settings.database_url:
            import os
            import logging
            
            # Extract path from URL (e.g., sqlite+aiosqlite:////data/boxscore.db)
            db_path = settings.database_url.split(":///")[-1]
            if os.path.exists(db_path):
                logging.error(f"Database corruption detected ({str(e)}). Deleting {db_path} and retrying...")
                try:
                    os.remove(db_path)
                    # Retry init
                    async with engine.begin() as conn:
                        await conn.run_sync(Base.metadata.create_all)
                    logging.info("Database recreated successfully.")
                    return
                except Exception as delete_error:
                    logging.error(f"Failed to delete corrupted database: {delete_error}")
        
        # Re-raise if not handled
        raise e
