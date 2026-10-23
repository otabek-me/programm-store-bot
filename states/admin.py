from aiogram.fsm.state import State, StatesGroup


class AddProgram(StatesGroup):
    file = State()
    name = State()
    description = State()
    category = State()
    keywords = State()
    version = State()
    operating_system = State()
    confirm = State()


class EditProgram(StatesGroup):
    value = State()
    file = State()


class AdminSearch(StatesGroup):
    query = State()


class CategoryForm(StatesGroup):
    name = State()


class Broadcast(StatesGroup):
    message = State()
    confirm = State()
    collecting_album = State()
    sending = State()


class RequestReply(StatesGroup):
    message = State()
