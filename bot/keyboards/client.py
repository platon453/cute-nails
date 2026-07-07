import datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot.db.models import Slot


# ── Callback Data ────────────────────────────────────────────────────────

class BookDateCB(CallbackData, prefix="book_date"):
    """Колбэк для выбора даты клиентом."""
    date: str  # Формат "ДД.ММ.ГГГГ"


class BookTimeCB(CallbackData, prefix="book_time"):
    """Колбэк для выбора конкретного слота клиентом."""
    slot_id: int


class BookingActionCB(CallbackData, prefix="book_act"):
    """Колбэк для подтверждения/отклонения брони админом (Этап 5)."""
    booking_id: int
    action: str  # "confirm" | "reject"


# ── Клавиатуры ───────────────────────────────────────────────────────────

WEEKDAYS_RU = {
    0: "Пн", 1: "Вт", 2: "Ср",
    3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс",
}


def available_dates_kb(slots: list[Slot]) -> InlineKeyboardMarkup:
    """
    Клавиатура с уникальными датами, на которые есть свободные слоты.
    Показывает день недели рядом с датой для удобства.
    """
    # Собираем уникальные даты
    seen: set[datetime.date] = set()
    unique_dates: list[datetime.date] = []
    for slot in slots:
        if slot.date not in seen:
            seen.add(slot.date)
            unique_dates.append(slot.date)

    rows: list[list[InlineKeyboardButton]] = []

    for date in unique_dates:
        weekday = WEEKDAYS_RU[date.weekday()]
        date_str = date.strftime("%d.%m.%Y")
        rows.append([
            InlineKeyboardButton(
                text=f"📅 {date_str} ({weekday})",
                callback_data=BookDateCB(date=date_str).pack(),
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def available_times_kb(slots: list[Slot], date_str: str) -> InlineKeyboardMarkup:
    """
    Клавиатура с доступным временем на выбранную дату.
    Слоты выводятся по 2 в ряд для компактности.
    """
    buttons: list[InlineKeyboardButton] = []

    for slot in slots:
        time_str = slot.time.strftime("%H:%M")
        buttons.append(
            InlineKeyboardButton(
                text=f"⏰ {time_str}",
                callback_data=BookTimeCB(slot_id=slot.id).pack(),
            )
        )

    # Разбиваем кнопки по 2 в ряд
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i + 2])

    # Кнопка «Назад к датам»
    rows.append([
        InlineKeyboardButton(
            text="🔙 Назад к датам",
            callback_data="back_to_dates",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def phone_request_kb() -> ReplyKeyboardMarkup:
    """
    Reply-клавиатура с кнопкой 'Поделиться контактом'.
    Используется для получения номера телефона клиента.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# Для удаления reply-клавиатуры после получения контакта
remove_kb = ReplyKeyboardRemove()


def active_booking_kb(admin_username: str | None) -> InlineKeyboardMarkup | None:
    """Клавиатура с кнопкой связи с админом для отмены записи."""
    if not admin_username:
        return None
    
    # Убираем @ если он есть, чтобы сформировать ссылку t.me
    clean_username = admin_username.lstrip('@')
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить запись (связь с админом)", url=f"https://t.me/{clean_username}")]
        ]
    )
