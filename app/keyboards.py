from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Agregatsiya")],
            [KeyboardButton(text="Excel/CSV -> DataMatrix PDF")],
            [KeyboardButton(text="API kalitni almashtirish")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Kerakli amalni tanlang",
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Bekor qilish")]],
        resize_keyboard=True,
    )


def datamatrix_product_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Suv mahsuloti")],
            [KeyboardButton(text="Maishiy texnika")],
            [KeyboardButton(text="Bekor qilish")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Mahsulot turini tanlang",
    )
