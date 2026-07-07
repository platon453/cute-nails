from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import Slot


# ── Callback Data ────────────────────────────────────────────────────────

class AdminMenuCB(CallbackData, prefix="adm_menu"):
    """Колбэк-данные для главного меню админа."""
    action: str  # "add_slot" | "view_slots"


class SlotDeleteCB(CallbackData, prefix="adm_del"):
    """Колбэк-данные для удаления конкретного слота."""
    slot_id: int


class SlotPageCB(CallbackData, prefix="adm_page"):
    """Колбэк-данные для пагинации списка слотов."""
    page: int


# ── Клавиатуры ───────────────────────────────────────────────────────────

def admin_main_menu() -> InlineKeyboardMarkup:
    """Главное меню админа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📅 Добавить слот",
                callback_data=AdminMenuCB(action="add_slot").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 Мои слоты",
                callback_data=AdminMenuCB(action="view_slots").pack(),
            ),
        ],
    ])


def slots_list_kb(
    slots: list[Slot],
    page: int = 0,
    per_page: int = 5,
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком слотов и кнопками удаления.
    Поддерживает пагинацию по 5 слотов на страницу.
    """
    total_pages = max(1, (len(slots) + per_page - 1) // per_page)
    page = min(page, total_pages - 1)

    start = page * per_page
    end = start + per_page
    page_slots = slots[start:end]

    rows: list[list[InlineKeyboardButton]] = []

    for slot in page_slots:
        date_str = slot.date.strftime("%d.%m.%Y")
        time_str = slot.time.strftime("%H:%M")
        status = "🟢" if slot.is_available else "🔴"

        rows.append([
            InlineKeyboardButton(
                text=f"{status} {date_str} в {time_str}",
                callback_data="noop",
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=SlotDeleteCB(slot_id=slot.id).pack(),
            ),
        ])

    # Кнопки пагинации
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=SlotPageCB(page=page - 1).pack(),
            )
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=SlotPageCB(page=page + 1).pack(),
            )
        )
    if nav_buttons:
        rows.append(nav_buttons)

    # Кнопка «Назад в меню»
    rows.append([
        InlineKeyboardButton(
            text="🔙 Назад в меню",
            callback_data=AdminMenuCB(action="back").pack(),
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены для FSM-операций."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=AdminMenuCB(action="cancel").pack(),
            ),
        ],
    ])
