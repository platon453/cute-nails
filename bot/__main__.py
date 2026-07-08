import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from bot.config import settings
from bot.db.engine import engine
from bot.handlers.admin import router as admin_router
from bot.handlers.client import router as client_router
from bot.middlewares.admin import AdminMiddleware
from bot.middlewares.db import DbSessionMiddleware


async def main() -> None:
    """Точка входа: настройка и запуск бота."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ],
    )

    # Прокси через v2rayA (SOCKS5-прокси на порту 20170 в Docker-сети)
    session = AiohttpSession(proxy="socks5://v2raya:20170")

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

    # ── Хуки жизненного цикла ───────────────────────────────────────────
    async def on_startup(bot: Bot) -> None:
        logging.info("Бот запущен и готов к работе")

    async def on_shutdown(bot: Bot) -> None:
        logging.info("Бот останавливается — закрываем соединения с БД...")
        await engine.dispose()
        logging.info("Бот остановлен")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logging.info("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
