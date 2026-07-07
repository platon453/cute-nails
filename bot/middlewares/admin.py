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
        # Определяем user_id в зависимости от типа события
        user_id: int | None = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        data["is_admin"] = user_id in settings.admin_id_list if user_id else False

        return await handler(event, data)
