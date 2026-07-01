from aiogram.fsm.state import State, StatesGroup


class ApiKeyFlow(StatesGroup):
    waiting_for_key = State()


class AggregationFlow(StatesGroup):
    waiting_for_business_place_address = State()
    waiting_for_business_place = State()
    waiting_for_parent = State()
    waiting_for_units_per_group = State()
    waiting_for_children = State()


class DataMatrixFlow(StatesGroup):
    waiting_for_product_type = State()
    waiting_for_file = State()
