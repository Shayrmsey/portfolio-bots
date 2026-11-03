from datetime import date, datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import DAYS_AHEAD, SERVICES, WORK_HOURS

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

BTN_BOOK = "📅 Записатися"
BTN_MY = "📋 Мої записи"
BTN_ABOUT = "ℹ️ Про нас"
MENU_BUTTONS = {BTN_BOOK, BTN_MY, BTN_ABOUT}

main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_BOOK)], [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_ABOUT)]],
    resize_keyboard=True,
)

share_phone = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Надіслати номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def format_day(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{WEEKDAYS[d.weekday()]} {d:%d.%m}"


def services_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, (title, price, minutes) in SERVICES.items():
        kb.button(text=f"{title} — {price} грн ({minutes} хв)", callback_data=f"svc:{code}")
    kb.adjust(1)
    return kb.as_markup()


def days_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    today = date.today()
    for offset in range(DAYS_AHEAD):
        day = (today + timedelta(days=offset)).isoformat()
        kb.button(text=format_day(day), callback_data=f"day:{day}")
    kb.button(text="⬅️ Назад", callback_data="back:services")
    kb.adjust(4, 3, 1)
    return kb.as_markup()


def free_slots(day: str, busy: set[str]) -> list[str]:
    now = datetime.now()
    is_today = day == now.date().isoformat()
    return [
        f"{hour:02d}:00"
        for hour in WORK_HOURS
        if f"{hour:02d}:00" not in busy and not (is_today and hour <= now.hour)
    ]


def times_kb(slots: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for slot in slots:
        kb.button(text=slot, callback_data=f"time:{slot}")
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ Інший день", callback_data="back:days"))
    return kb.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити", callback_data="confirm:yes")
    kb.button(text="❌ Скасувати", callback_data="confirm:no")
    return kb.as_markup()


def cancel_bookings_kb(bookings) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(text=f"❌ Скасувати {format_day(b['day'])} {b['time']}", callback_data=f"cancel:{b['id']}")
    kb.adjust(1)
    return kb.as_markup()
