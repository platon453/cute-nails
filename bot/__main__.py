import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from bot.config import settings
from bot.handlers.admin import router as admin_router
from bot.handlers.client import router as client_router
from bot.middlewares.admin import AdminMiddleware
from bot.middlewares.db import DbSessionMiddleware


async def main() -> None:
    """Точка входа: настройка и запуск бота."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    session = None
    if settings.proxy:
        session = AiohttpSession(proxy=settings.proxy)
        logging.info(f"Используем прокси: {settings.proxy}")

    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # ── Подключение Middlewares ──────────────────────────────────────────
    # Порядок важен: сначала DB-сессия, потом проверка админа
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AdminMiddleware())

    # ── Подключение роутеров (хендлеров) ────────────────────────────────
    # Порядок важен: админ первым, чтобы его хендлеры имели приоритет
    dp.include_router(admin_router)
    dp.include_router(client_router)

    logging.info("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
