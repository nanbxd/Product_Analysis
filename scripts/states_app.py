from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

class SearchState(StatesGroup):
    waiting_for_photo = State()  # Состояние "ожидание фото"
