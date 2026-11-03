import re
from contextlib import suppress
from datetime import date, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import keyboards as kb
from config import DAYS_AHEAD, SERVICES, Config
from db import Database

router = Router()

PHONE_RE = re.compile(r"^\+?\d{10,13}$")


class Booking(StatesGroup):
    service = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


def normalize_phone(raw: str) -> str | None:
    phone = re.sub(r"[\s\-()]", "", raw)
    return phone if PHONE_RE.match(phone) else None


def booking_summary(data: dict) -> str:
    title, price, _ = SERVICES[data["service"]]
    return (
        f"💈 <b>{title}</b> — {price} грн\n"
        f"📅 {kb.format_day(data['day'])} о {data['time']}\n"
        f"👤 {escape(data['name'])}\n"
        f"📱 {data['phone']}"
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Вітаю, {escape(message.from_user.first_name)}! 👋\n"
        "Я бот барбершопу <b>BarberLab</b>. Тут можна записатися на стрижку за 30 секунд.",
        reply_markup=kb.main_menu,
    )


@router.message(F.text == kb.BTN_ABOUT)
async def about(message: Message):
    await message.answer(
        "<b>BarberLab</b>\n📍 Київ, вул. Хрещатик, 1\n🕙 Щодня 10:00–19:00\n📞 +380 00 000 00 00"
    )


@router.message(F.text == kb.BTN_BOOK)
async def book_start(message: Message, state: FSMContext):
    await state.set_state(Booking.service)
    await message.answer("Оберіть послугу:", reply_markup=kb.services_kb())


@router.callback_query(Booking.service, F.data.startswith("svc:"))
async def pick_service(call: CallbackQuery, state: FSMContext):
    service = call.data.split(":", 1)[1]
    if service not in SERVICES:
        await call.answer("Невідома послуга", show_alert=True)
        return
    await state.update_data(service=service)
    await state.set_state(Booking.day)
    await call.message.edit_text("Оберіть день:", reply_markup=kb.days_kb())
    await call.answer()


@router.callback_query(F.data == "back:services")
async def back_to_services(call: CallbackQuery, state: FSMContext):
    await state.set_state(Booking.service)
    await call.message.edit_text("Оберіть послугу:", reply_markup=kb.services_kb())
    await call.answer()


async def show_times(call: CallbackQuery, state: FSMContext, db: Database, day: str, notice: str | None = None):
    slots = kb.free_slots(day, db.busy_slots(day))
    if not slots:
        await state.set_state(Booking.day)
        with suppress(TelegramBadRequest):
            await call.message.edit_text("Оберіть інший день:", reply_markup=kb.days_kb())
        await call.answer(notice or "На цей день вільних місць немає 😔", show_alert=True)
        return
    await state.update_data(day=day)
    await state.set_state(Booking.time)
    await call.message.edit_text(f"Вільний час на {kb.format_day(day)}:", reply_markup=kb.times_kb(slots))
    await call.answer(notice, show_alert=bool(notice))


def is_bookable(day: str) -> bool:
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return False
    today = date.today()
    return today <= d < today + timedelta(days=DAYS_AHEAD)


@router.callback_query(Booking.day, F.data.startswith("day:"))
async def pick_day(call: CallbackQuery, state: FSMContext, db: Database):
    day = call.data.split(":", 1)[1]
    if not is_bookable(day):
        with suppress(TelegramBadRequest):
            await call.message.edit_text("Оберіть день:", reply_markup=kb.days_kb())
        await call.answer("Ця дата вже недоступна, список днів оновлено", show_alert=True)
        return
    await show_times(call, state, db, day)


@router.callback_query(F.data == "back:days")
async def back_to_days(call: CallbackQuery, state: FSMContext):
    await state.set_state(Booking.day)
    await call.message.edit_text("Оберіть день:", reply_markup=kb.days_kb())
    await call.answer()


@router.callback_query(Booking.time, F.data.startswith("time:"))
async def pick_time(call: CallbackQuery, state: FSMContext):
    await state.update_data(time=call.data.split(":", 1)[1])
    await state.set_state(Booking.name)
    await call.message.edit_text("Як до вас звертатися? Напишіть ім'я:")
    await call.answer()


@router.message(Booking.name, F.text, ~F.text.in_(kb.MENU_BUTTONS))
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Ім'я має бути від 2 до 50 символів. Спробуйте ще раз:")
        return
    await state.update_data(name=name)
    await state.set_state(Booking.phone)
    await message.answer("Надішліть номер телефону кнопкою нижче або напишіть його:", reply_markup=kb.share_phone)


@router.message(Booking.phone, F.contact | (F.text & ~F.text.in_(kb.MENU_BUTTONS)))
async def enter_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw)
    if not phone:
        await message.answer("Схоже, номер некоректний. Приклад: +380991234567")
        return
    await state.update_data(phone=phone)
    await state.set_state(Booking.confirm)
    data = await state.get_data()
    await message.answer("Перевірте дані:", reply_markup=ReplyKeyboardRemove())
    await message.answer(booking_summary(data), reply_markup=kb.confirm_kb())


@router.callback_query(Booking.confirm, F.data == "confirm:no")
async def confirm_no(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Запис скасовано.")
    await call.message.answer("Головне меню:", reply_markup=kb.main_menu)
    await call.answer()


@router.callback_query(Booking.confirm, F.data == "confirm:yes")
async def confirm_yes(call: CallbackQuery, state: FSMContext, db: Database, bot: Bot, config: Config):
    data = await state.get_data()
    booking_id = db.add(call.from_user.id, data["service"], data["day"], data["time"], data["name"], data["phone"])
    if booking_id is None:
        await show_times(call, state, db, data["day"], notice="Цей час щойно зайняли. Оберіть інший 🙏")
        return

    await state.clear()
    await call.message.edit_text(f"✅ Ви записані!\n\n{booking_summary(data)}\n\nЧекаємо на вас!")
    await call.message.answer("Головне меню:", reply_markup=kb.main_menu)
    await call.answer()
    await bot.send_message(config.admin_id, f"🆕 <b>Новий запис #{booking_id}</b>\n\n{booking_summary(data)}")


@router.message(F.text == kb.BTN_MY)
async def my_bookings(message: Message, db: Database):
    bookings = db.user_upcoming(message.from_user.id)
    if not bookings:
        await message.answer("У вас немає активних записів.")
        return
    lines = [f"• {SERVICES[b['service']][0]} — {kb.format_day(b['day'])} о {b['time']}" for b in bookings]
    await message.answer("Ваші записи:\n" + "\n".join(lines), reply_markup=kb.cancel_bookings_kb(bookings))


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_booking(call: CallbackQuery, db: Database, bot: Bot, config: Config):
    row = db.cancel(int(call.data.split(":", 1)[1]), call.from_user.id)
    if not row:
        await call.answer("Запис не знайдено", show_alert=True)
        return
    await call.message.edit_text(f"Запис на {kb.format_day(row['day'])} о {row['time']} скасовано.")
    await call.answer()
    await bot.send_message(
        config.admin_id, f"❌ Клієнт {escape(row['name'])} скасував запис на {kb.format_day(row['day'])} о {row['time']}"
    )


@router.message(Command("admin"))
async def admin_panel(message: Message, db: Database, config: Config):
    if message.from_user.id != config.admin_id:
        return
    bookings = db.all_upcoming()
    if not bookings:
        await message.answer("Найближчих записів немає.")
        return
    lines = [
        f"#{b['id']} {kb.format_day(b['day'])} {b['time']} — {SERVICES[b['service']][0]}, "
        f"{escape(b['name'])}, {b['phone']}"
        for b in bookings
    ]
    await message.answer("<b>Найближчі записи:</b>\n" + "\n".join(lines))


@router.callback_query()
async def stale_button(call: CallbackQuery):
    await call.answer("Кнопка застаріла. Почніть знову з меню.")
