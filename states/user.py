from aiogram.fsm.state import State, StatesGroup


class Search(StatesGroup):
    query = State()


class SoftwareRequest(StatesGroup):
    name = State()
    details = State()
    confirm = State()
