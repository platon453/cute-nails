from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import settings

# Асинхронный движок для подключения к PostgreSQL
engine = create_async_engine(
    url=settings.db_url,
    echo=False,
)

# Фабрика асинхронных сессий
async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)
