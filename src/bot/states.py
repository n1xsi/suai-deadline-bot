from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()


class AddDeadline(StatesGroup):
    waiting_for_course_name = State()
    waiting_for_task_name = State()
    waiting_for_due_date = State()
