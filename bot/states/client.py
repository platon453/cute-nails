from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """FSM-стейты для процесса записи клиента."""

    choosing_date = State()   # Выбор даты из доступных
    choosing_time = State()   # Выбор времени на выбранную дату
    entering_name = State()   # Ввод имени
    entering_phone = State()  # Отправка номера телефона
