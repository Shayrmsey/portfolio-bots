from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from catalog import CATEGORIES, Product, products_in

BTN_CATALOG = "🛍 Каталог"
BTN_CART = "🛒 Кошик"
BTN_CONTACTS = "📞 Контакти"
MENU_BUTTONS = {BTN_CATALOG, BTN_CART, BTN_CONTACTS}

main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_CART)], [KeyboardButton(text=BTN_CONTACTS)]],
    resize_keyboard=True,
)

share_phone = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Надіслати номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, title in CATEGORIES.items():
        kb.button(text=title, callback_data=f"cat:{code}")
    kb.adjust(1)
    return kb.as_markup()


def products_kb(category: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in products_in(category):
        kb.button(text=f"{p.name} — {p.price} грн", callback_data=f"prod:{p.id}")
    kb.button(text="⬅️ Категорії", callback_data="catalog")
    kb.adjust(1)
    return kb.as_markup()


def product_kb(product: Product, qty: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➖", callback_data=f"qty:-1:{product.id}")
    kb.button(text=f"У кошику: {qty}", callback_data="cart")
    kb.button(text="➕", callback_data=f"qty:1:{product.id}")
    kb.button(text="⬅️ Назад", callback_data=f"cat:{product.category}")
    kb.button(text="🛒 Кошик", callback_data="cart")
    kb.adjust(3, 2)
    return kb.as_markup()


def cart_kb(items: list[tuple[Product, int]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p, qty in items:
        kb.row(
            InlineKeyboardButton(text="➖", callback_data=f"cqty:-1:{p.id}"),
            InlineKeyboardButton(text=f"{p.name} ×{qty}", callback_data=f"prod:{p.id}"),
            InlineKeyboardButton(text="➕", callback_data=f"cqty:1:{p.id}"),
        )
    if items:
        kb.row(
            InlineKeyboardButton(text="🗑 Очистити", callback_data="cart_clear"),
            InlineKeyboardButton(text="✅ Оформити", callback_data="checkout"),
        )
    kb.row(InlineKeyboardButton(text="🛍 До каталогу", callback_data="catalog"))
    return kb.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити замовлення", callback_data="order_confirm")
    kb.button(text="❌ Скасувати", callback_data="order_cancel")
    kb.adjust(1)
    return kb.as_markup()


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити", callback_data=f"status:confirmed:{order_id}")
    kb.button(text="🚚 Відправлено", callback_data=f"status:shipped:{order_id}")
    kb.button(text="❌ Відхилити", callback_data=f"status:rejected:{order_id}")
    kb.adjust(2, 1)
    return kb.as_markup()
