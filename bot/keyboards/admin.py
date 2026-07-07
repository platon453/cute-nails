import datetime
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import Slot


# ── Callback Data ────────────────────────────────────────────────────────

class AdminMenuCB(CallbackData, prefix="adm_menu"):
    """Колбэк-данные для главного меню админа."""
    action: str  # "add_slot" | "view_slots" | "cancel" | "back"


class AdminDatesPageCB(CallbackData, prefix="adm_dpage"):
    """Пагинация для списка дат."""
    page: int


class AdminDateSelectCB(CallbackData, prefix="adm_dsel"):
    """Выбор конкретной даты."""
    date_str: str  # "YYYY-MM-DD"


class AdminSlotDetailCB(CallbackData, prefix="adm_sdet"):
    """Просмотр конкретного слота."""
    slot_id: int


class SlotDeleteCB(CallbackData, prefix="adm_del"):
    """Удаление свободного слота."""
    slot_id: int


class AdminCancelBookingCB(CallbackData, prefix="adm_cbk"):
    """Отмена занятой брони админом."""
    slot_id: int


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


def admin_dates_kb(
    dates: list[datetime.date],
    page: int = 0,
    per_page: int = 6,
) -> InlineKeyboardMarkup:
    """Список дат (пагинация)."""
    total_pages = max(1, (len(dates) + per_page - 1) // per_page)
    page = min(page, total_pages - 1)

    start = page * per_page
    end = start + per_page
    page_dates = dates[start:end]

    rows: list[list[InlineKeyboardButton]] = []

    # Кнопки с датами (по 2 в ряд для красоты)
    current_row = []
    for d in page_dates:
        current_row.append(
            InlineKeyboardButton(
                text=f"📅 {d.strftime('%d.%m.%Y')}",
                callback_data=AdminDateSelectCB(date_str=d.isoformat()).pack(),
            )
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    # Пагинация
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=AdminDatesPageCB(page=page - 1).pack(),
            )
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=AdminDatesPageCB(page=page + 1).pack(),
            )
        )
    if nav_buttons:
        rows.append(nav_buttons)

    # Кнопка «Назад в меню»
    rows.append([
        InlineKeyboardButton(
            text="🔙 В главное меню",
            callback_data=AdminMenuCB(action="back").pack(),
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_slots_on_date_kb(slots: list[Slot]) -> InlineKeyboardMarkup:
    """Список слотов на выбранную дату."""
    rows: list[list[InlineKeyboardButton]] = []

    for slot in slots:
        time_str = slot.time.strftime("%H:%M")
        if slot.is_available:
            text = f"{time_str} (Свободно)"
        else:
            # Для простоты показываем (Занято) на кнопке, детали - при клике
            text = f"{time_str} (🔴 Занято)"

        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=AdminSlotDetailCB(slot_id=slot.id).pack(),
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="🔙 Назад к датам",
            callback_data=AdminMenuCB(action="view_slots").pack(),
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_slot_detail_kb(slot: Slot) -> InlineKeyboardMarkup:
    """Клавиатура для карточки слота (удалить или отменить бронь)."""
    rows: list[list[InlineKeyboardButton]] = []

    if slot.is_available:
        rows.append([
            InlineKeyboardButton(
                text="🗑 Удалить слот",
                callback_data=SlotDeleteCB(slot_id=slot.id).pack(),
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="❌ Отменить бронь",
                callback_data=AdminCancelBookingCB(slot_id=slot.id).pack(),
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="🔙 Назад к списку",
            callback_data=AdminDateSelectCB(date_str=slot.date.isoformat()).pack(),
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
