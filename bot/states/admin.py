from aiogram.fsm.state import State, StatesGroup


class AddSlotStates(StatesGroup):
    """FSM-стейты для добавления нового слота админом."""

    waiting_for_date = State()  # Ожидание ввода даты (ДД.ММ.ГГГГ)
    waiting_for_time = State()  # Ожидание ввода времени (ЧЧ:ММ)

