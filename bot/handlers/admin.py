import datetime
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db.models import Booking, BookingStatus, Slot, User
from bot.keyboards.client import BookingActionCB
from bot.keyboards.admin import (
    AdminMenuCB,
    AdminDatesPageCB,
    AdminDateSelectCB,
    AdminSlotDetailCB,
    AdminCancelBookingCB,
    SlotDeleteCB,
    AdminActiveBookingsPageCB,
    AdminArchivePageCB,
    admin_main_menu,
    admin_dates_kb,
    admin_slots_on_date_kb,
    admin_slot_detail_kb,
    admin_active_bookings_kb,
    admin_archive_kb,
    cancel_kb,
)
from bot.states.admin import AddSlotStates

logger = logging.getLogger(__name__)
router = Router(name="admin")


# ── Вспомогательная функция: проверка админа ────────────────────────────

def _check_admin(is_admin: bool) -> bool:
    """Возвращает True если пользователь — админ."""
    return is_admin


# ── /admin — Главное меню ───────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, is_admin: bool) -> None:
    """Команда /admin — открывает админ-панель."""
    if not _check_admin(is_admin):
        return

    await message.answer(
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_main_menu(),
    )


# ── Навигация по меню ──────────────────────────────────────────────────

@router.callback_query(AdminMenuCB.filter(F.action == "back"))
async def cb_back_to_menu(
    callback: CallbackQuery,
    is_admin: bool,
) -> None:
    """Возврат в главное меню админа."""
    if not _check_admin(is_admin):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_main_menu(),
    )
    await callback.answer()


@router.callback_query(AdminMenuCB.filter(F.action == "cancel"))
async def cb_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool,
) -> None:
    """Отмена текущей FSM-операции и возврат в меню."""
    if not _check_admin(is_admin):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_main_menu(),
    )
    await callback.answer("Отменено")


# ── Добавление слота: начало ────────────────────────────────────────────

@router.callback_query(AdminMenuCB.filter(F.action == "add_slot"))
async def cb_add_slot_start(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool,
) -> None:
    """Начало FSM добавления слота — запрос даты."""
    if not _check_admin(is_admin):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(AddSlotStates.waiting_for_date)
    await callback.message.edit_text(
        "📅 <b>Добавление слота</b>\n\n"
        "Введите дату в формате <code>ДД.ММ.ГГГГ</code>\n"
        "Например: <code>15.07.2026</code>",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


# ── Добавление слота: ввод даты ─────────────────────────────────────────

@router.message(AddSlotStates.waiting_for_date)
async def fsm_slot_date(
    message: Message,
    state: FSMContext,
    is_admin: bool,
) -> None:
    """Обработка введённой даты и переход к вводу времени."""
    if not _check_admin(is_admin):
        return

    text = message.text.strip()

    try:
        date = datetime.datetime.strptime(text, "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Неверный формат даты.\n"
            "Введите дату в формате <code>ДД.ММ.ГГГГ</code>",
            reply_markup=cancel_kb(),
        )
        return

    if date < datetime.date.today():
        await message.answer(
            "❌ Нельзя добавить слот в прошлое.\n"
            "Введите актуальную дату:",
            reply_markup=cancel_kb(),
        )
        return

    await state.update_data(date=text)
    await state.set_state(AddSlotStates.waiting_for_time)
    await message.answer(
        f"✅ Дата: <b>{text}</b>\n\n"
        "⏰ Теперь введите время в формате <code>ЧЧ:ММ</code>\n"
        "Например: <code>14:30</code>",
        reply_markup=cancel_kb(),
    )


# ── Добавление слота: ввод времени ──────────────────────────────────────

@router.message(AddSlotStates.waiting_for_time)
async def fsm_slot_time(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Обработка введённого времени и сохранение слота в БД."""
    if not _check_admin(is_admin):
        return

    text = message.text.strip()

    try:
        time = datetime.datetime.strptime(text, "%H:%M").time()
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Введите время в формате <code>ЧЧ:ММ</code>",
            reply_markup=cancel_kb(),
        )
        return

    data = await state.get_data()
    date = datetime.datetime.strptime(data["date"], "%d.%m.%Y").date()

    # Проверяем, нет ли уже такого слота
    existing = await session.execute(
        select(Slot).where(Slot.date == date, Slot.time == time)
    )
    if existing.scalar_one_or_none():
        await message.answer(
            "❌ Слот на эту дату и время уже существует!\n"
            "Введите другое время:",
            reply_markup=cancel_kb(),
        )
        return

    # Сохраняем слот
    slot = Slot(date=date, time=time, is_available=True)
    session.add(slot)
    await session.commit()

    await state.clear()

    date_str = date.strftime("%d.%m.%Y")
    time_str = time.strftime("%H:%M")

    logger.info("Админ %s добавил слот: %s %s", message.from_user.id, date_str, time_str)

    await message.answer(
        f"✅ <b>Слот добавлен!</b>\n\n"
        f"📅 Дата: {date_str}\n"
        f"⏰ Время: {time_str}",
        reply_markup=admin_main_menu(),
    )


# ── Просмотр слотов (группировка по датам) ──────────────────────────────

async def _show_dates_page(callback: CallbackQuery, session: AsyncSession, page: int = 0):
    """Вспомогательная функция для отображения списка дат."""
    # Получаем уникальные даты, начиная с сегодня
    result = await session.execute(
        select(Slot.date)
        .where(Slot.date >= datetime.date.today())
        .distinct()
        .order_by(Slot.date)
    )
    dates = list(result.scalars().all())

    if not dates:
        text = (
            "📋 <b>Мои слоты</b>\n\n"
            "Пока нет доступных дат со слотами.\n"
            "Добавьте их через меню 📅"
        )
        markup = admin_main_menu()
    else:
        text = "📋 <b>Выберите дату для просмотра слотов:</b>"
        markup = admin_dates_kb(dates, page=page)

    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass


@router.callback_query(AdminMenuCB.filter(F.action == "view_slots"))
async def cb_view_slots(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Показать список дат со слотами (первая страница)."""
    if not _check_admin(is_admin):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await _show_dates_page(callback, session, page=0)
    await callback.answer()


@router.callback_query(AdminDatesPageCB.filter())
async def cb_admin_dates_page(
    callback: CallbackQuery,
    callback_data: AdminDatesPageCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Пагинация списка дат."""
    if not _check_admin(is_admin):
        return
    await _show_dates_page(callback, session, page=callback_data.page)
    await callback.answer()


# ── Просмотр слотов на конкретную дату ─────────────────────────────────

@router.callback_query(AdminDateSelectCB.filter())
async def cb_admin_date_select(
    callback: CallbackQuery,
    callback_data: AdminDateSelectCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Показать слоты на выбранную дату."""
    if not _check_admin(is_admin):
        return

    try:
        selected_date = datetime.date.fromisoformat(callback_data.date_str)
    except ValueError:
        await callback.answer("Ошибка формата даты", show_alert=True)
        return

    result = await session.execute(
        select(Slot)
        .where(Slot.date == selected_date)
        .order_by(Slot.time)
    )
    slots = list(result.scalars().all())

    if not slots:
        await callback.answer("Слоты на эту дату не найдены", show_alert=True)
        await _show_dates_page(callback, session, page=0)
        return

    date_str_ru = selected_date.strftime("%d.%m.%Y")
    
    try:
        await callback.message.edit_text(
            f"📅 <b>Слоты на {date_str_ru}</b>\n\n"
            f"Выберите слот для управления:",
            reply_markup=admin_slots_on_date_kb(slots),
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


# ── Карточка конкретного слота ──────────────────────────────────────────

@router.callback_query(AdminSlotDetailCB.filter())
async def cb_admin_slot_detail(
    callback: CallbackQuery,
    callback_data: AdminSlotDetailCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Показать карточку конкретного слота."""
    if not _check_admin(is_admin):
        return

    result = await session.execute(
        select(Slot)
        .options(selectinload(Slot.bookings).selectinload(Booking.user))
        .where(Slot.id == callback_data.slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        await callback.answer("Слот не найден", show_alert=True)
        return

    date_str = slot.date.strftime("%d.%m.%Y")
    time_str = slot.time.strftime("%H:%M")

    text_lines = [
        f"💅 <b>Слот:</b> {date_str} в {time_str}",
        ""
    ]

    if slot.is_available:
        text_lines.append("🟢 <b>Статус:</b> Свободен")
        text_lines.append("<i>Вы можете удалить этот слот, если он больше не нужен.</i>")
    else:
        text_lines.append("🔴 <b>Статус:</b> Занят")
        
        # Берем привязанную бронь (только активную)
        active_booking = next(
            (b for b in slot.bookings if b.status in (BookingStatus.CONFIRMED, BookingStatus.PENDING)),
            None
        )
        if active_booking:
            client = active_booking.user
            status_ru = "Ожидает подтверждения" if active_booking.status == BookingStatus.PENDING else "Подтверждена"
            text_lines.extend([
                "",
                f"👤 <b>Клиент:</b> {client.first_name}",
                f"📱 <b>Телефон:</b> {client.phone or 'Не указан'}",
                f"ℹ️ <b>Статус брони:</b> {status_ru}"
            ])
        else:
            text_lines.append("\n⚠️ Бронь не найдена (возможно, ошибка данных).")

    try:
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=admin_slot_detail_kb(slot)
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


# ── Удаление слота ─────────────────────────────────────────────────────

@router.callback_query(SlotDeleteCB.filter())
async def cb_delete_slot(
    callback: CallbackQuery,
    callback_data: SlotDeleteCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Удаление конкретного свободного слота."""
    if not _check_admin(is_admin):
        return

    result = await session.execute(
        select(Slot)
        .options(selectinload(Slot.bookings))
        .where(Slot.id == callback_data.slot_id)
    )
    slot = result.scalar_one_or_none()
    if not slot:
        await callback.answer("Слот не найден", show_alert=True)
        return

    if not slot.is_available:
        await callback.answer("❌ Слот занят! Сначала отмените бронь.", show_alert=True)
        return

    slot_date = slot.date
    date_str = slot_date.strftime("%d.%m.%Y")
    time_str = slot.time.strftime("%H:%M")

    await session.delete(slot)
    await session.commit()

    logger.info("Админ %s удалил слот: %s %s", callback.from_user.id, date_str, time_str)
    await callback.answer(f"🗑 Слот {time_str} удалён")

    # Возвращаемся к списку слотов на эту дату
    result = await session.execute(
        select(Slot).where(Slot.date == slot_date).order_by(Slot.time)
    )
    slots = list(result.scalars().all())

    if slots:
        try:
            await callback.message.edit_text(
                f"📅 <b>Слоты на {date_str}</b>\n\n"
                f"Выберите слот для управления:",
                reply_markup=admin_slots_on_date_kb(slots),
            )
        except TelegramBadRequest:
            pass
    else:
        # Если слотов на день не осталось, возвращаем к списку дат
        await _show_dates_page(callback, session, page=0)


# ── Отмена брони админом ───────────────────────────────────────────────

@router.callback_query(AdminCancelBookingCB.filter())
async def cb_admin_cancel_booking(
    callback: CallbackQuery,
    callback_data: AdminCancelBookingCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Админ отменяет бронь и освобождает слот."""
    if not _check_admin(is_admin):
        return

    result = await session.execute(
        select(Slot)
        .options(selectinload(Slot.bookings).selectinload(Booking.user))
        .where(Slot.id == callback_data.slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot or slot.is_available:
        await callback.answer("Слот уже свободен или не найден", show_alert=True)
        return

    active_booking = next(
        (b for b in slot.bookings if b.status in (BookingStatus.CONFIRMED, BookingStatus.PENDING)),
        None
    )
    if not active_booking:
        await callback.answer("Активная бронь не найдена", show_alert=True)
        return

    # Отменяем бронь и освобождаем слот
    active_booking.status = BookingStatus.REJECTED
    slot.is_available = True
    await session.commit()

    date_str = slot.date.strftime("%d.%m.%Y")
    time_str = slot.time.strftime("%H:%M")
    
    await callback.answer("✅ Бронь отменена, слот свободен!")

    # Уведомляем клиента
    client = active_booking.user
    try:
        await callback.bot.send_message(
            chat_id=client.telegram_id,
            text=(
                f"😔 <b>К сожалению, ваша запись отменена</b>\n\n"
                f"📅 Дата: {date_str}\n"
                f"⏰ Время: {time_str}\n\n"
                f"Администратор был вынужден отменить запись. Вы можете выбрать другое время — нажмите /start"
            )
        )
    except Exception as e:
        logger.error("Не удалось уведомить клиента %s об отмене: %s", client.telegram_id, e)

    # Обновляем карточку слота (она теперь должна показывать, что слот свободен)
    text_lines = [
        f"💅 <b>Слот:</b> {date_str} в {time_str}",
        "",
        "🟢 <b>Статус:</b> Свободен",
        "<i>Вы можете удалить этот слот, если он больше не нужен.</i>"
    ]
    try:
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=admin_slot_detail_kb(slot)
        )
    except TelegramBadRequest:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Этап 5: Финализация бронирования
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ── Подтверждение записи ────────────────────────────────────────────────

@router.callback_query(BookingActionCB.filter(F.action == "confirm"))
async def cb_confirm_booking(
    callback: CallbackQuery,
    callback_data: BookingActionCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Админ подтверждает запись клиента."""
    if not _check_admin(is_admin):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    # Загружаем бронь вместе со связанными объектами
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.user), selectinload(Booking.slot))
        .where(Booking.id == callback_data.booking_id)
    )
    booking = result.scalar_one_or_none()

    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    if booking.status != BookingStatus.PENDING:
        status_text = "подтверждена" if booking.status == BookingStatus.CONFIRMED else "отклонена"
        await callback.answer(f"Эта запись уже {status_text}", show_alert=True)
        return

    # Подтверждаем
    booking.status = BookingStatus.CONFIRMED
    await session.commit()

    date_str = booking.slot.date.strftime("%d.%m.%Y")
    time_str = booking.slot.time.strftime("%H:%M")

    logger.info(
        "Админ %s подтвердил бронь #%s (user=%s, %s %s)",
        callback.from_user.id, booking.id, booking.user.telegram_id, date_str, time_str,
    )

    # Обновляем сообщение админа
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from bot.keyboards.admin import AdminMenuCB
    
    await callback.message.edit_text(
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"👤 {booking.user.first_name}\n"
        f"📱 {booking.user.phone}\n"
        f"📅 {date_str} в {time_str}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К активным записям", callback_data=AdminMenuCB(action="active_bookings").pack())
        ]])
    )
    await callback.answer("✅ Подтверждено!")

    # Уведомляем клиента
    bot = callback.bot
    try:
        await bot.send_message(
            chat_id=booking.user.telegram_id,
            text=(
                "🎉 <b>Ваша запись подтверждена!</b>\n\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}\n\n"
                "Ждём вас! ✨"
            ),
        )
    except Exception as e:
        logger.error("Не удалось уведомить клиента %s: %s", booking.user.telegram_id, e)


# ── Отклонение записи ──────────────────────────────────────────────────

@router.callback_query(BookingActionCB.filter(F.action == "reject"))
async def cb_reject_booking(
    callback: CallbackQuery,
    callback_data: BookingActionCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    """Админ отклоняет запись клиента."""
    if not _check_admin(is_admin):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    # Загружаем бронь вместе со связанными объектами
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.user), selectinload(Booking.slot))
        .where(Booking.id == callback_data.booking_id)
    )
    booking = result.scalar_one_or_none()

    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    if booking.status != BookingStatus.PENDING:
        status_text = "подтверждена" if booking.status == BookingStatus.CONFIRMED else "отклонена"
        await callback.answer(f"Эта запись уже {status_text}", show_alert=True)
        return

    # Отклоняем и освобождаем слот
    booking.status = BookingStatus.REJECTED
    booking.slot.is_available = True
    await session.commit()

    date_str = booking.slot.date.strftime("%d.%m.%Y")
    time_str = booking.slot.time.strftime("%H:%M")

    logger.info(
        "Админ %s отклонил бронь #%s (user=%s, %s %s)",
        callback.from_user.id, booking.id, booking.user.telegram_id, date_str, time_str,
    )

    # Обновляем сообщение админа
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from bot.keyboards.admin import AdminMenuCB
    
    await callback.message.edit_text(
        f"❌ <b>Запись отклонена!</b>\n\n"
        f"👤 {booking.user.first_name}\n"
        f"📱 {booking.user.phone}\n"
        f"📅 {date_str} в {time_str}\n\n"
        "Слот снова свободен.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К активным записям", callback_data=AdminMenuCB(action="active_bookings").pack())
        ]])
    )
    await callback.answer("❌ Отклонено")

    # Уведомляем клиента
    bot = callback.bot
    try:
        await bot.send_message(
            chat_id=booking.user.telegram_id,
            text=(
                "😔 <b>К сожалению, ваша запись отклонена</b>\n\n"
                f"📅 Дата: {date_str}\n"
                f"⏰ Время: {time_str}\n\n"
                "Вы можете выбрать другое время — нажмите /start 💅"
            ),
        )
    except Exception as e:
        logger.error("Не удалось уведомить клиента %s: %s", booking.user.telegram_id, e)

# ── Активные записи ─────────────────────────────────────────────────────

@router.callback_query(AdminMenuCB.filter(F.action == "active_bookings"))
async def cb_active_bookings_start(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    if not _check_admin(is_admin):
        return
    await _render_active_bookings(callback, session, 0)


@router.callback_query(AdminActiveBookingsPageCB.filter())
async def cb_active_bookings_page(
    callback: CallbackQuery,
    callback_data: AdminActiveBookingsPageCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    if not _check_admin(is_admin):
        return
    await _render_active_bookings(callback, session, callback_data.page)


async def _render_active_bookings(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.user), selectinload(Booking.slot))
        .where(Booking.status == BookingStatus.PENDING)
        .order_by(Booking.id.asc())
    )
    bookings = list(result.scalars().all())
    total = len(bookings)
    
    if not bookings:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        await callback.message.edit_text(
            "🔔 <b>Активные записи</b>\n\nНет заявок, ожидающих подтверждения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 В главное меню", callback_data=AdminMenuCB(action="back").pack())
            ]])
        )
        return
    
    page = max(0, min(page, total - 1))
    booking = bookings[page]
    date_str = booking.slot.date.strftime("%d.%m.%Y")
    time_str = booking.slot.time.strftime("%H:%M")
    
    if booking.user.username:
        user_info = f"@{booking.user.username}"
    else:
        user_info = f"<a href='tg://user?id={booking.user.telegram_id}'>{booking.user.first_name}</a>"
        
    phone = booking.user.phone or "Не указан"
    
    text = (
        f"🔔 <b>Заявка #{booking.id}</b> (Стр. {page + 1} из {total})\n\n"
        f"📅 Слот: <b>{date_str} {time_str}</b>\n"
        f"👤 Клиент: {user_info}\n"
        f"📞 Телефон: <code>{phone}</code>\n"
    )
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=admin_active_bookings_kb(booking.id, page, total),
            disable_web_page_preview=True
        )
    except TelegramBadRequest:
        pass


# ── Архив записей ───────────────────────────────────────────────────────

@router.callback_query(AdminMenuCB.filter(F.action == "archive"))
async def cb_archive_start(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    if not _check_admin(is_admin):
        return
    await _render_archive(callback, session, 0)


@router.callback_query(AdminArchivePageCB.filter())
async def cb_archive_page(
    callback: CallbackQuery,
    callback_data: AdminArchivePageCB,
    session: AsyncSession,
    is_admin: bool,
) -> None:
    if not _check_admin(is_admin):
        return
    await _render_archive(callback, session, callback_data.page)


async def _render_archive(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.user), selectinload(Booking.slot))
        .where(Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.REJECTED]))
        .order_by(Booking.id.desc())
    )
    bookings = list(result.scalars().all())
    
    per_page = 5
    total_pages = max(1, (len(bookings) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    
    if not bookings:
        await callback.message.edit_text(
            "🗄 <b>Архив заявок</b>\n\nАрхив пуст.",
            reply_markup=admin_archive_kb(page, total_pages)
        )
        return
        
    start = page * per_page
    end = start + per_page
    page_bookings = bookings[start:end]
    
    lines = [f"🗄 <b>Архив заявок (Стр. {page + 1} из {total_pages})</b>\n"]
    
    for b in page_bookings:
        date_str = f"{b.slot.date.strftime('%d.%m.%Y')} {b.slot.time.strftime('%H:%M')}"
        status_icon = "✅ Одобрено" if b.status == BookingStatus.CONFIRMED else "❌ Отклонено"
        
        if b.user.username:
             user_name = f"@{b.user.username}"
        else:
             user_name = f"<a href='tg://user?id={b.user.telegram_id}'>{b.user.first_name}</a>"
             
        phone = b.user.phone or "Не указан"
        
        lines.append(f"#{b.id} | {status_icon} ({date_str})")
        lines.append(f"👤 {user_name} | {b.user.telegram_id} | 📞 {phone}")
        lines.append("➖➖➖➖➖➖➖➖➖")
        
    try:
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=admin_archive_kb(page, total_pages),
            disable_web_page_preview=True
        )
    except TelegramBadRequest:
        pass



