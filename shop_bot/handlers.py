import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import keyboards as kb
from catalog import CATEGORIES, PRODUCTS_BY_ID, Product
from config import FREE_DELIVERY_FROM, SHOP_NAME, Config
from db import STATUSES, Database

router = Router()

PHONE_RE = re.compile(r"^\+?\d{10,13}$")
STATUS_MARK = "\n\n<b>Статус:</b> "


class Checkout(StatesGroup):
    name = State()
    phone = State()
    address = State()
    confirm = State()


def normalize_phone(raw: str) -> str | None:
    phone = re.sub(r"[\s\-()]", "", raw)
    return phone if PHONE_RE.match(phone) else None


def cart_text(items: list[tuple[Product, int]]) -> str:
    if not items:
        return "🛒 Кошик порожній"
    lines = [f"• {p.name} × {q} = {p.price * q} грн" for p, q in items]
    total = sum(p.price * q for p, q in items)
    delivery = (
        "🚚 Доставка безкоштовна"
        if total >= FREE_DELIVERY_FROM
        else f"🚚 До безкоштовної доставки ще {FREE_DELIVERY_FROM - total} грн"
    )
    return "<b>Ваш кошик:</b>\n" + "\n".join(lines) + f"\n\n💰 <b>Разом: {total} грн</b>\n{delivery}"


async def safe_edit(call: CallbackQuery, text: str, markup=None):
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await call.answer()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Вітаємо в <b>{SHOP_NAME}</b>! ☕\nСвіжообсмажена кава та чай з доставкою Новою Поштою.",
        reply_markup=kb.main_menu,
    )


@router.message(F.text == kb.BTN_CONTACTS)
async def contacts(message: Message):
    await message.answer(f"<b>{SHOP_NAME}</b>\n📞 +380 00 000 00 00\n🕙 Пн–Сб 9:00–20:00\nОплата при отриманні.")


@router.message(F.text == kb.BTN_CATALOG)
async def catalog(message: Message):
    await message.answer("Оберіть категорію:", reply_markup=kb.categories_kb())


@router.callback_query(F.data == "catalog")
async def catalog_cb(call: CallbackQuery):
    await safe_edit(call, "Оберіть категорію:", kb.categories_kb())


@router.callback_query(F.data.startswith("cat:"))
async def category(call: CallbackQuery):
    code = call.data.split(":", 1)[1]
    if code not in CATEGORIES:
        await call.answer("Категорію не знайдено", show_alert=True)
        return
    await safe_edit(call, CATEGORIES[code], kb.products_kb(code))


def product_card(product: Product) -> str:
    return f"<b>{product.name}</b>\n\n{product.description}\n\n💰 {product.price} грн"


def cart_qty(db: Database, user_id: int, product_id: int) -> int:
    return next((q for p, q in db.cart(user_id) if p.id == product_id), 0)


@router.callback_query(F.data.startswith("prod:"))
async def product(call: CallbackQuery, db: Database):
    product = PRODUCTS_BY_ID.get(int(call.data.split(":", 1)[1]))
    if not product:
        await call.answer("Товар не знайдено", show_alert=True)
        return
    qty = cart_qty(db, call.from_user.id, product.id)
    await safe_edit(call, product_card(product), kb.product_kb(product, qty))


@router.callback_query(F.data.startswith("qty:"))
async def change_qty_on_card(call: CallbackQuery, db: Database):
    _, delta, product_id = call.data.split(":")
    product = PRODUCTS_BY_ID.get(int(product_id))
    if not product:
        await call.answer("Товар не знайдено", show_alert=True)
        return
    qty = db.change_qty(call.from_user.id, product.id, int(delta))
    await safe_edit(call, product_card(product), kb.product_kb(product, qty))


async def show_cart(call: CallbackQuery, db: Database):
    items = db.cart(call.from_user.id)
    await safe_edit(call, cart_text(items), kb.cart_kb(items))


@router.message(F.text == kb.BTN_CART)
async def cart(message: Message, db: Database):
    items = db.cart(message.from_user.id)
    await message.answer(cart_text(items), reply_markup=kb.cart_kb(items))


@router.callback_query(F.data == "cart")
async def cart_cb(call: CallbackQuery, db: Database):
    await show_cart(call, db)


@router.callback_query(F.data.startswith("cqty:"))
async def change_qty_in_cart(call: CallbackQuery, db: Database):
    _, delta, product_id = call.data.split(":")
    if int(product_id) in PRODUCTS_BY_ID:
        db.change_qty(call.from_user.id, int(product_id), int(delta))
    await show_cart(call, db)


@router.callback_query(F.data == "cart_clear")
async def cart_clear(call: CallbackQuery, db: Database):
    db.clear_cart(call.from_user.id)
    await show_cart(call, db)


@router.callback_query(F.data == "checkout")
async def checkout(call: CallbackQuery, state: FSMContext, db: Database):
    if not db.cart(call.from_user.id):
        await call.answer("Кошик порожній", show_alert=True)
        return
    await state.set_state(Checkout.name)
    await call.message.answer("Оформлення замовлення.\nВаше ім'я та прізвище:")
    await call.answer()


@router.message(Checkout.name, F.text, ~F.text.in_(kb.MENU_BUTTONS))
async def checkout_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 60:
        await message.answer("Введіть ім'я від 2 до 60 символів:")
        return
    await state.update_data(name=name)
    await state.set_state(Checkout.phone)
    await message.answer("Номер телефону:", reply_markup=kb.share_phone)


@router.message(Checkout.phone, F.contact | (F.text & ~F.text.in_(kb.MENU_BUTTONS)))
async def checkout_phone(message: Message, state: FSMContext):
    phone = normalize_phone(message.contact.phone_number if message.contact else message.text)
    if not phone:
        await message.answer("Некоректний номер. Приклад: +380991234567")
        return
    await state.update_data(phone=phone)
    await state.set_state(Checkout.address)
    await message.answer(
        "Місто та відділення Нової Пошти (наприклад: <i>Київ, відділення 25</i>):",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Checkout.address, F.text, ~F.text.in_(kb.MENU_BUTTONS))
async def checkout_address(message: Message, state: FSMContext, db: Database):
    address = message.text.strip()
    if not 5 <= len(address) <= 200:
        await message.answer("Вкажіть місто та номер відділення:")
        return
    await state.update_data(address=address)
    await state.set_state(Checkout.confirm)
    data = await state.get_data()
    items = db.cart(message.from_user.id)
    await message.answer(
        f"{cart_text(items)}\n\n👤 {escape(data['name'])}\n📱 {data['phone']}\n📦 {escape(address)}\n"
        "💳 Оплата при отриманні",
        reply_markup=kb.confirm_kb(),
    )


@router.callback_query(Checkout.confirm, F.data == "order_cancel")
async def order_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Оформлення скасовано. Товари залишились у кошику.")
    await call.message.answer("Головне меню:", reply_markup=kb.main_menu)
    await call.answer()


@router.callback_query(Checkout.confirm, F.data == "order_confirm")
async def order_confirm(call: CallbackQuery, state: FSMContext, db: Database, bot: Bot, config: Config):
    items = db.cart(call.from_user.id)
    if not items:
        await state.clear()
        await call.answer("Кошик порожній", show_alert=True)
        return
    data = await state.get_data()
    order_id = db.create_order(call.from_user.id, items, data["name"], data["phone"], data["address"])
    await state.clear()

    await call.message.edit_text(f"🎉 Замовлення <b>#{order_id}</b> прийнято! Менеджер зв'яжеться з вами найближчим часом.")
    await call.message.answer("Головне меню:", reply_markup=kb.main_menu)
    await call.answer()

    await bot.send_message(
        config.admin_id,
        f"🆕 <b>Замовлення #{order_id}</b>\n\n{cart_text(items)}\n\n"
        f"👤 {escape(data['name'])}\n📱 {data['phone']}\n📦 {escape(data['address'])}",
        reply_markup=kb.admin_order_kb(order_id),
    )


@router.callback_query(F.data.startswith("status:"))
async def change_status(call: CallbackQuery, db: Database, bot: Bot, config: Config):
    if call.from_user.id != config.admin_id:
        await call.answer("Недостатньо прав", show_alert=True)
        return
    _, status, order_id = call.data.split(":")
    if status not in STATUSES:
        await call.answer("Невідомий статус", show_alert=True)
        return
    order = db.set_status(int(order_id), status)
    if not order:
        await call.answer("Замовлення не знайдено", show_alert=True)
        return
    base_text = call.message.html_text.split(STATUS_MARK)[0]
    await safe_edit(call, f"{base_text}{STATUS_MARK}{STATUSES[status]}", call.message.reply_markup)
    await bot.send_message(order["user_id"], f"Ваше замовлення #{order['id']}: {STATUSES[status]}")


@router.message(Command("orders"))
async def orders(message: Message, db: Database, config: Config):
    if message.from_user.id != config.admin_id:
        return
    rows = db.recent_orders()
    if not rows:
        await message.answer("Замовлень ще немає.")
        return
    lines = [f"#{o['id']} — {o['total']} грн, {escape(o['name'])}, {STATUSES[o['status']]}" for o in rows]
    await message.answer("<b>Останні замовлення:</b>\n" + "\n".join(lines))


@router.callback_query()
async def stale_button(call: CallbackQuery):
    await call.answer("Кнопка застаріла. Почніть знову з меню.")
