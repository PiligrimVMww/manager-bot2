from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from questions import CATEGORIES


def categories_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, cat in CATEGORIES.items():
        builder.button(text=cat["title"], callback_data=f"cat:{key}")
    builder.adjust(1)
    return builder.as_markup()


def skip_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Пропустити", callback_data="skip_field")
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Все вірно, надіслати", callback_data="confirm_order")
    builder.button(text="🔁 Почати заново", callback_data="restart_order")
    builder.adjust(1)
    return builder.as_markup()


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Нове", callback_data=f"admin_status:{order_id}:new")
    builder.button(text="🔧 В роботі", callback_data=f"admin_status:{order_id}:in_progress")
    builder.button(text="✅ Виконано", callback_data=f"admin_status:{order_id}:done")
    builder.button(text="❌ Скасувати", callback_data=f"admin_status:{order_id}:cancelled")
    builder.adjust(2)
    return builder.as_markup()
