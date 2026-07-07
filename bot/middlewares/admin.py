from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import settings


class AdminMiddleware(BaseMiddleware):
    """
    Middleware для проверки прав админа.

    Добавляет в data["is_admin"] булевый флаг, который хендлеры могут
    использовать для разграничения доступа. Список ID админов берётся
    из .env через конфигурацию (ADMIN_IDS).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Aiogram 3 автоматически добавляет event_from_user в словарь data
        user = data.get("event_from_user")
        user_id = user.id if user else None

        data["is_admin"] = user_id in settings.admin_id_list if user_id else False

        return await handler(event, data)
