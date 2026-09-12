"""
Основна логіка діалогу з клієнтом: вибір категорії -> послідовні питання
з questions.py -> підтвердження -> відправка замовлення адміну (вам).

Логіка навмисно "рушійна" (generic): вона не прив'язана до конкретних
питань, а просто йде по списку fields з questions.py. Завдяки цьому
нові питання можна додавати без зміни цього файлу.
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import database as db
from config import ADMIN_IDS
from questions import CATEGORIES
from keyboards import categories_kb, skip_kb, confirm_kb, admin_order_kb

router = Router()


class OrderForm(StatesGroup):
    choosing_category = State()
    filling_field = State()
    collecting_files = State()
    confirming = State()


WELCOME_TEXT = (
    "Вітаю! 👋\n\n"
    "Я бот-помічник. Допоможу оформити замовлення: виконання практичних, "
    "лабораторних, написання рефератів чи створення презентацій.\n\n"
    "Оберіть, будь ласка, тип роботи:"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=categories_kb())


@router.message(Command("neworder"))
async def cmd_neworder(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Оберіть тип роботи:", reply_markup=categories_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Наразі немає активного оформлення замовлення.")
        return
    await state.clear()
    await message.answer("Оформлення замовлення скасовано. Щоб почати знову — /neworder")


@router.message(Command("myorders"))
async def cmd_myorders(message: Message):
    orders = db.list_orders_by_user(message.from_user.id)
    if not orders:
        await message.answer("У вас поки немає замовлень. Створити нове — /neworder")
        return
    status_labels = {
        db.STATUS_NEW: "🆕 нове",
        db.STATUS_IN_PROGRESS: "🔧 в роботі",
        db.STATUS_DONE: "✅ виконано",
        db.STATUS_CANCELLED: "❌ скасовано",
    }
    lines = ["Ваші замовлення:\n"]
    for o in orders:
        cat_title = CATEGORIES.get(o["category_key"], {}).get("title", o["category_key"])
        lines.append(f"№{o['id']} — {cat_title} — {status_labels.get(o['status'], o['status'])}")
    await message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("cat:"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    category_key = callback.data.split(":", 1)[1]
    if category_key not in CATEGORIES:
        await callback.answer("Невідома категорія", show_alert=True)
        return

    order_id = db.create_order(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        user_full_name=callback.from_user.full_name,
        category_key=category_key,
    )

    await state.update_data(order_id=order_id, category_key=category_key, field_index=0)
    await callback.message.edit_text(f"Обрано: {CATEGORIES[category_key]['title']}\n\nПочнемо оформлення 📝")
    await ask_current_field(callback.message, state)
    await callback.answer()


async def ask_current_field(message: Message, state: FSMContext):
    data = await state.get_data()
    category_key = data["category_key"]
    field_index = data["field_index"]
    fields = CATEGORIES[category_key]["fields"]

    if field_index >= len(fields):
        await show_summary_and_confirm(message, state)
        return

    field = fields[field_index]

    if field.get("type") == "files":
        await state.set_state(OrderForm.collecting_files)
        kb = skip_kb() if field.get("optional") else None
        await message.answer(field["question"], reply_markup=kb)
    else:
        await state.set_state(OrderForm.filling_field)
        kb = skip_kb() if field.get("optional") else None
        await message.answer(field["question"], reply_markup=kb)


@router.callback_query(F.data == "skip_field")
async def skip_field(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(field_index=data["field_index"] + 1)
    await ask_current_field(callback.message, state)
    await callback.answer()


@router.message(OrderForm.filling_field)
async def receive_text_field(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Будь ласка, дайте відповідь текстом.")
        return

    data = await state.get_data()
    category_key = data["category_key"]
    field_index = data["field_index"]
    field = CATEGORIES[category_key]["fields"][field_index]

    db.save_answer(data["order_id"], field["key"], message.text)
    await state.update_data(field_index=field_index + 1)
    await ask_current_field(message, state)


@router.message(OrderForm.collecting_files, Command("done"))
async def finish_files(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(field_index=data["field_index"] + 1)
    await ask_current_field(message, state)


@router.message(OrderForm.collecting_files, F.photo | F.document)
async def receive_file(message: Message, state: FSMContext):
    data = await state.get_data()
    category_key = data["category_key"]
    field_index = data["field_index"]
    field = CATEGORIES[category_key]["fields"][field_index]

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    else:
        file_id = message.document.file_id
        file_type = "document"

    db.add_file(data["order_id"], field["key"], file_id, file_type)
    await message.answer("Файл отримано ✅ Можете надіслати ще, або напишіть /done, щоб продовжити.")


@router.message(OrderForm.collecting_files)
async def files_wrong_input(message: Message):
    await message.answer(
        "Надішліть файл (фото або документ), або напишіть /done, щоб продовжити далі."
    )


def build_summary_text(order_row, files_count: int) -> str:
    import json
    from questions import CATEGORIES as CATS

    category_key = order_row["category_key"]
    answers = json.loads(order_row["answers_json"])
    fields = CATS[category_key]["fields"]

    lines = [f"📋 Замовлення №{order_row['id']}", f"Тип: {CATS[category_key]['title']}", ""]
    for field in fields:
        if field.get("type") == "files":
            continue
        value = answers.get(field["key"])
        if not value:
            continue

        # Питання, на які клієнт відповідає кількома рядками (наприклад,
        # об'єднані дані для титульної сторінки), показуємо списком підрядків,
        # а не однією суцільною лінією.
        value_lines = [v.strip() for v in value.split("\n") if v.strip()]
        short_label = field.get("label", field["question"].split("\n")[0]).rstrip(":")
        if len(value_lines) > 1:
            lines.append(f"• {short_label}:")
            for v in value_lines:
                lines.append(f"   {v}")
        else:
            lines.append(f"• {short_label}: {value}")
    if files_count:
        lines.append(f"\n📎 Прикріплених файлів: {files_count}")
    return "\n".join(lines)


async def show_summary_and_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    order_row = db.get_order(data["order_id"])
    files = db.get_order_files(data["order_id"])
    summary = build_summary_text(order_row, len(files))

    await state.set_state(OrderForm.confirming)
    await message.answer(
        summary + "\n\nПеревірте дані. Якщо все правильно — підтвердіть відправку.",
        reply_markup=confirm_kb(),
    )


@router.callback_query(F.data == "restart_order", OrderForm.confirming)
async def restart_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Добре, почнемо заново. Оберіть тип роботи:", reply_markup=categories_kb())
    await callback.answer()


@router.callback_query(F.data == "confirm_order", OrderForm.confirming)
async def confirm_order(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_row = db.get_order(data["order_id"])
    files = db.get_order_files(data["order_id"])
    summary = build_summary_text(order_row, len(files))

    contact = f"@{callback.from_user.username}" if callback.from_user.username else "(немає username)"
    admin_text = (
        f"🆕 НОВЕ ЗАМОВЛЕННЯ\n\n{summary}\n\n"
        f"👤 Клієнт: {callback.from_user.full_name} {contact}\n"
        f"🔗 tg://user?id={callback.from_user.id}"
    )

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, admin_text, reply_markup=admin_order_kb(order_row["id"]))
        for f in files:
            caption = f"Замовлення №{order_row['id']} — файл до поля «{f['field_key']}»"
            if f["file_type"] == "photo":
                await bot.send_photo(admin_id, f["file_id"], caption=caption)
            else:
                await bot.send_document(admin_id, f["file_id"], caption=caption)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"Дякую! Замовлення №{order_row['id']} прийнято ✅\n"
        "Я передав всі дані менеджеру, з вами скоро зв'яжуться щодо деталей та вартості.\n\n"
        "Переглянути свої замовлення можна командою /myorders"
    )
    await state.clear()
    await callback.answer()
