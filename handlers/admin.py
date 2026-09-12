"""
Хендлери для адміністратора (вас): перегляд списку замовлень і зміна статусу.
Працюють тільки для ID з ADMIN_IDS у .env.
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import database as db
from config import ADMIN_IDS
from questions import CATEGORIES
from handlers.order import build_summary_text
from keyboards import admin_order_kb

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


STATUS_LABELS = {
    db.STATUS_NEW: "🆕 нове",
    db.STATUS_IN_PROGRESS: "🔧 в роботі",
    db.STATUS_DONE: "✅ виконано",
    db.STATUS_CANCELLED: "❌ скасовано",
}


@router.message(Command("orders"))
async def cmd_orders(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    status_filter = None
    if len(args) > 1:
        arg = args[1].strip().lower()
        mapping = {"new": db.STATUS_NEW, "in_progress": db.STATUS_IN_PROGRESS,
                   "done": db.STATUS_DONE, "cancelled": db.STATUS_CANCELLED}
        status_filter = mapping.get(arg)

    orders = db.list_orders(status_filter)
    if not orders:
        await message.answer("Замовлень немає.")
        return

    lines = ["Список замовлень (використайте /orders new|in_progress|done|cancelled для фільтру):\n"]
    for o in orders[:30]:
        cat_title = CATEGORIES.get(o["category_key"], {}).get("title", o["category_key"])
        lines.append(f"№{o['id']} — {cat_title} — {STATUS_LABELS.get(o['status'])} — @{o['username'] or '—'}")
    await message.answer("\n".join(lines))


@router.message(Command("order"))
async def cmd_order_detail(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Використання: /order <номер_замовлення>")
        return
    order_id = int(args[1].strip())
    order_row = db.get_order(order_id)
    if not order_row:
        await message.answer("Замовлення не знайдено.")
        return
    files = db.get_order_files(order_id)
    summary = build_summary_text(order_row, len(files))
    await message.answer(
        f"{summary}\n\nСтатус: {STATUS_LABELS.get(order_row['status'])}\n"
        f"Клієнт: {order_row['user_full_name']} (@{order_row['username'] or '—'})\n"
        f"tg://user?id={order_row['user_id']}",
        reply_markup=admin_order_kb(order_id),
    )


@router.callback_query(F.data.startswith("admin_status:"))
async def change_status(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Немає доступу", show_alert=True)
        return

    _, order_id_str, new_status = callback.data.split(":")
    order_id = int(order_id_str)
    order_row = db.get_order(order_id)
    if not order_row:
        await callback.answer("Замовлення не знайдено", show_alert=True)
        return

    db.set_status(order_id, new_status)
    await callback.answer(f"Статус змінено: {STATUS_LABELS.get(new_status)}")

    # Кнопки залишаються під повідомленням — статус можна перемикати
    # скільки завгодно разів, у будь-який момент.
    try:
        await callback.message.answer(f"Статус замовлення №{order_id} → {STATUS_LABELS.get(new_status)}")
    except Exception:
        pass

    # Повідомляємо клієнта про зміну статусу (за бажанням можна прибрати)
    if new_status == db.STATUS_DONE:
        await bot.send_message(
            order_row["user_id"],
            f"✅ Ваше замовлення №{order_id} виконано! Менеджер зв'яжеться з вами щодо передачі роботи.",
        )
    elif new_status == db.STATUS_IN_PROGRESS:
        await bot.send_message(
            order_row["user_id"],
            f"🔧 Ваше замовлення №{order_id} взято в роботу.",
        )
