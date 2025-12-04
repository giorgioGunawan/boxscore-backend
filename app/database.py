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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
