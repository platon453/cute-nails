import datetime
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.formatting import as_list, as_key_value, as_marked_section, Text, Bold, CustomEmoji, TextLink, Italic, BlockQuote
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.db.models import Booking, BookingStatus, Slot, User
from bot.keyboards.client import (
    BookDateCB,
    BookTimeCB,
    BookingActionCB,
    active_booking_kb,
    available_dates_kb,
    available_times_kb,
    phone_request_kb,
    remove_kb,
)
from bot.states.client import BookingStates

logger = logging.getLogger(__name__)
router = Router(name="client")


# ── /start — Приветствие и вывод дат ────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Приветствие клиента и показ доступных дат (или текущей записи)."""
    await state.clear()

    # Сначала проверяем, есть ли у пользователя активная бронь
    tg_id = message.from_user.id
    
    # Ищем пользователя и его активные записи на будущие слоты
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.slot))
        .join(Booking.user)
        .join(Booking.slot)
        .where(
            User.telegram_id == tg_id,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
            Slot.date >= datetime.date.today()
        )
        .order_by(Slot.date, Slot.time)
    )
    active_booking = result.scalars().first()
    
    if active_booking:
        slot = active_booking.slot
        date_str = slot.date.strftime("%d.%m.%Y")
        time_str = slot.time.strftime("%H:%M")
        status_ru = "Ожидает подтверждения ⏳" if active_booking.status == BookingStatus.PENDING else "Подтверждена ✅"
        
        text = as_list(
            Text("💅", Bold(" Привет!"), " У вас уже есть активная запись:"),
            "",
            as_key_value("📅" + " Дата", Bold(date_str)),
            as_key_value("⏰" + " Время", Bold(time_str)),
            as_key_value("ℹ️" + " Статус", status_ru),
            "",
            "Пока эта запись активна, вы не можете записаться на новое время."
        )
        await message.answer(**text.as_kwargs(), reply_markup=active_booking_kb(settings.admin_username))
        return

    # Если активных записей нет, показываем доступные слоты
    result = await session.execute(
        select(Slot)
        .where(Slot.is_available == True, Slot.date >= datetime.date.today())
        .order_by(Slot.date, Slot.time)
    )
    slots = list(result.scalars().all())

    if not slots:
        text = as_list(
            Text("💅", Bold(" Привет!"), " Добро пожаловать!"),
            "",
            "К сожалению, сейчас нет свободных окон для записи.",
            "Попробуйте зайти позже 🙏"
        )
        await message.answer(**text.as_kwargs())
        return

    await state.set_state(BookingStates.choosing_date)
    text = as_list(
        Text("Привет", " 💅"),
        "",
        BlockQuote(Italic("Нажмите кнопку ниже и выберите удобную дату, чтобы записаться ко мне на ноготочки: "))
    )
    await message.answer(**text.as_kwargs(), reply_markup=available_dates_kb(slots))


# ── Выбор даты ─────────────────────────────────────────────────────────

@router.callback_query(BookDateCB.filter(), BookingStates.choosing_date)
async def cb_choose_date(
    callback: CallbackQuery,
    callback_data: BookDateCB,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Клиент выбрал дату — показываем свободное время."""
    date = datetime.datetime.strptime(callback_data.date, "%d.%m.%Y").date()

    result = await session.execute(
        select(Slot)
        .where(Slot.date == date, Slot.is_available == True)
        .order_by(Slot.time)
    )
    slots = list(result.scalars().all())

    if not slots:
        await callback.answer("На эту дату уже нет свободных окон 😔", show_alert=True)
        return

    await state.update_data(chosen_date=callback_data.date)
    await state.set_state(BookingStates.choosing_time)

    text = as_list(
        as_key_value("📅" + " Дата", Bold(callback_data.date)),
        "",
        "Выберите удобное время:"
    )
    await callback.message.edit_text(**text.as_kwargs(), reply_markup=available_times_kb(slots, callback_data.date))
    await callback.answer()


# ── Кнопка «Назад к датам» ─────────────────────────────────────────────

@router.callback_query(F.data == "back_to_dates", BookingStates.choosing_time)
async def cb_back_to_dates(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Возврат к выбору даты."""
    result = await session.execute(
        select(Slot)
        .where(Slot.is_available == True, Slot.date >= datetime.date.today())
        .order_by(Slot.date, Slot.time)
    )
    slots = list(result.scalars().all())

    if not slots:
        await callback.message.edit_text(
            "😔 К сожалению, свободных окон больше нет.\n"
            "Попробуйте зайти позже 🙏",
        )
        await state.clear()
        await callback.answer()
        return

    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        "💅 Выберите удобную дату:",
        reply_markup=available_dates_kb(slots),
    )
    await callback.answer()


# ── Выбор времени ──────────────────────────────────────────────────────

@router.callback_query(BookTimeCB.filter(), BookingStates.choosing_time)
async def cb_choose_time(
    callback: CallbackQuery,
    callback_data: BookTimeCB,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Клиент выбрал время — запрашиваем имя."""
    slot = await session.get(Slot, callback_data.slot_id)

    if not slot or not slot.is_available:
        await callback.answer("Это время уже занято 😔", show_alert=True)
        return

    date_str = slot.date.strftime("%d.%m.%Y")
    time_str = slot.time.strftime("%H:%M")

    await state.update_data(slot_id=slot.id)
    await state.set_state(BookingStates.entering_name)

    text = as_list(
        Text("✅", " Вы выбрали: ", Bold(date_str), " в ", Bold(time_str)),
        "",
        Text("✏️", " Введите ваше имя:")
    )
    await callback.message.edit_text(**text.as_kwargs())
    await callback.answer()


# ── Ввод имени ─────────────────────────────────────────────────────────

@router.message(BookingStates.entering_name, F.text)
async def fsm_enter_name(
    message: Message,
    state: FSMContext,
) -> None:
    """Получение имени и запрос телефона."""
    name = message.text.strip()

    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите ваше имя:")
        return

    if len(name) > 150:
        await message.answer("❌ Имя слишком длинное. Введите ваше имя:")
        return

    await state.update_data(name=name)
    await state.set_state(BookingStates.entering_phone)

    text = as_list(
        Text("👋", " Приятно познакомиться, ", Bold(name), "!"),
        "",
        Text("📱", " Теперь поделитесь своим номером телефона."),
        "Нажмите кнопку ниже или введите номер вручную:"
    )
    await message.answer(**text.as_kwargs(), reply_markup=phone_request_kb())


# ── Получение телефона (через контакт) ──────────────────────────────────

@router.message(BookingStates.entering_phone, F.contact)
async def fsm_phone_contact(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Получение телефона через кнопку 'Поделиться контактом'."""
    phone = message.contact.phone_number
    await _finalize_booking(message, state, session, phone)


# ── Получение телефона (текстом) ────────────────────────────────────────

@router.message(BookingStates.entering_phone, F.text)
async def fsm_phone_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Получение телефона через ручной ввод."""
    phone = message.text.strip()

    # Простая валидация: только цифры, +, -, пробелы, скобки
    cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.lstrip("+").isdigit() or len(cleaned) < 7:
        await message.answer(
            "❌ Неверный номер телефона.\n"
            "Введите номер или нажмите кнопку ниже:",
            reply_markup=phone_request_kb(),
        )
        return

    await _finalize_booking(message, state, session, phone)


# ── Финализация записи и уведомление админа ─────────────────────────────

async def _finalize_booking(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    phone: str,
) -> None:
    """Создание записи в БД и отправка уведомления админам."""
    data = await state.get_data()
    slot_id = data["slot_id"]
    name = data["name"]

    # Получаем слот
    slot = await session.get(Slot, slot_id)
    if not slot or not slot.is_available:
        await message.answer(
            "😔 К сожалению, это время уже забронировали.\n"
            "Нажмите /start чтобы выбрать другое.",
            reply_markup=remove_kb,
        )
        await state.clear()
        return

    # Создаём или обновляем юзера
    tg_id = message.from_user.id
    result = await session.execute(
        select(User).where(User.telegram_id == tg_id)
    )
    user = result.scalar_one_or_none()

    tg_username = message.from_user.username
    if user:
        user.first_name = name
        user.phone = phone
        user.username = tg_username
    else:
        user = User(telegram_id=tg_id, username=tg_username, first_name=name, phone=phone)
        session.add(user)
        await session.flush()  # Получаем user.id

    # Создаём бронь
    booking = Booking(
        user_id=user.id,
        slot_id=slot.id,
        status=BookingStatus.PENDING,
    )
    slot.is_available = False
    session.add(booking)
    await session.commit()

    date_str = slot.date.strftime("%d.%m.%Y")
    time_str = slot.time.strftime("%H:%M")

    await state.clear()

    # Сообщение клиенту
    client_text = as_list(
        Text("🎉", Bold(" Заявка отправлена!")),
        "",
        as_key_value("•" + " Дата", date_str),
        as_key_value("•" + " Время", time_str),
        as_key_value("•" + " Имя", name),
        as_key_value("•" + " Телефон", phone),
        "",
        Text("⏳", " Ожидайте подтверждения от мастера."),
        Text("Вам придёт уведомление! ",)
    )
    await message.answer(**client_text.as_kwargs(), reply_markup=remove_kb)

    logger.info(
        "Новая заявка: user=%s, slot=%s %s, booking_id=%s",
        tg_id, date_str, time_str, booking.id,
    )

    # Уведомление админам
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=BookingActionCB(
                    booking_id=booking.id, action="confirm"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=BookingActionCB(
                    booking_id=booking.id, action="reject"
                ).pack(),
            ),
        ],
    ])

    tg_username = f"@{message.from_user.username}" if message.from_user.username else "нет"

    admin_text = as_list(
        Text("🔔", Bold(" Новая заявка на запись!")),
        "",
        as_key_value("👤" + " Имя", name),
        as_key_value("📱" + " Телефон", phone),
        as_key_value("💬" + " Telegram", tg_username),
        as_key_value("📅" + " Дата", date_str),
        as_key_value("⏰" + " Время", time_str),
        "",
        "Подтвердите или отклоните запись:"
    )

    bot = message.bot
    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(
                chat_id=admin_id,
                **admin_text.as_kwargs(),
                reply_markup=admin_kb,
            )
        except Exception as e:
            logger.error("Не удалось отправить уведомление админу %s: %s", admin_id, e)
