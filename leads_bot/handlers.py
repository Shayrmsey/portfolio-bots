import asyncio
import re
from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import COMPANY, FAQ, SERVICES, Config
from storage import Lead, LeadStorage, Users

router = Router()

PHONE_RE = re.compile(r"^\+?\d{10,13}$")

BTN_LEAD = "📝 Залишити заявку"
BTN_FAQ = "❓ Часті питання"
BTN_CONTACTS = "📞 Контакти"
BTN_SKIP = "Пропустити ➡️"
MENU_BUTTONS = {BTN_LEAD, BTN_FAQ, BTN_CONTACTS}

main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_LEAD)], [KeyboardButton(text=BTN_FAQ), KeyboardButton(text=BTN_CONTACTS)]],
    resize_keyboard=True,
)
share_phone = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Надіслати номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)
skip_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_SKIP)]], resize_keyboard=True, one_time_keyboard=True)


class LeadForm(StatesGroup):
    service = State()
    name = State()
    phone = State()
    comment = State()


class Broadcast(StatesGroup):
    message = State()


def services_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, title in SERVICES.items():
        kb.button(text=title, callback_data=f"svc:{code}")
    kb.adjust(2)
    return kb.as_markup()


def faq_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, (question, _) in FAQ.items():
        kb.button(text=question, callback_data=f"faq:{code}")
    kb.adjust(1)
    return kb.as_markup()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, users: Users):
    await state.clear()
    users.add(message.from_user.id)
    await message.answer(
        f"Привіт! Це бот студії <b>{COMPANY}</b> 🚀\n"
        "Розробляємо сайти й Telegram-ботів для бізнесу. Залиште заявку, і менеджер зв'яжеться з вами за 15 хвилин.",
        reply_markup=main_menu,
    )


@router.message(F.text == BTN_CONTACTS)
async def contacts(message: Message):
    await message.answer(f"<b>{COMPANY}</b>\n📞 +380 00 000 00 00\n✉️ hello@example.com\n🕙 Пн–Пт 9:00–18:00")


@router.message(F.text == BTN_FAQ)
async def faq(message: Message):
    await message.answer("Оберіть питання:", reply_markup=faq_kb())


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(call: CallbackQuery):
    item = FAQ.get(call.data.split(":", 1)[1])
    if item:
        await call.message.answer(f"<b>{item[0]}</b>\n{item[1]}")
    await call.answer()


@router.message(F.text == BTN_LEAD)
async def lead_start(message: Message, state: FSMContext):
    await state.set_state(LeadForm.service)
    await message.answer("Що вас цікавить?", reply_markup=services_kb())


@router.callback_query(LeadForm.service, F.data.startswith("svc:"))
async def lead_service(call: CallbackQuery, state: FSMContext):
    code = call.data.split(":", 1)[1]
    if code not in SERVICES:
        await call.answer()
        return
    await state.update_data(service=SERVICES[code])
    await state.set_state(LeadForm.name)
    await call.message.edit_text(f"Послуга: <b>{SERVICES[code]}</b>\n\nЯк вас звати?")
    await call.answer()


@router.message(LeadForm.name, F.text, ~F.text.in_(MENU_BUTTONS))
async def lead_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Ім'я має бути від 2 до 50 символів:")
        return
    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)
    await message.answer("Ваш номер телефону:", reply_markup=share_phone)


@router.message(LeadForm.phone, F.contact | (F.text & ~F.text.in_(MENU_BUTTONS)))
async def lead_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else message.text
    phone = re.sub(r"[\s\-()]", "", raw)
    if not PHONE_RE.match(phone):
        await message.answer("Некоректний номер. Приклад: +380991234567")
        return
    await state.update_data(phone=phone)
    await state.set_state(LeadForm.comment)
    await message.answer("Коротко опишіть задачу (або натисніть «Пропустити»):", reply_markup=skip_kb)


@router.message(LeadForm.comment, F.text, ~F.text.in_(MENU_BUTTONS))
async def lead_comment(message: Message, state: FSMContext, leads: LeadStorage, bot: Bot, config: Config):
    comment = "" if message.text == BTN_SKIP else message.text.strip()[:1000]
    data = await state.get_data()
    await state.clear()
    lead = Lead(
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        name=data["name"],
        phone=data["phone"],
        service=data["service"],
        comment=comment,
        username=f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id),
    )
    await leads.save(lead)
    await message.answer("✅ Дякуємо! Заявку прийнято, менеджер скоро зв'яжеться з вами.", reply_markup=main_menu)
    await bot.send_message(
        config.admin_id,
        f"🔥 <b>Нова заявка</b>\n\n🛠 {escape(lead.service)}\n👤 {escape(lead.name)}\n📱 {lead.phone}\n"
        f"💬 {escape(lead.comment) or '—'}\n🔗 {escape(lead.username)}",
    )


@router.message(Command("stats"))
async def stats(message: Message, users: Users, config: Config):
    if message.from_user.id != config.admin_id:
        return
    total, active = users.count()
    await message.answer(f"👥 Користувачів: {total}\n✅ Активних: {active}")


@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext, config: Config):
    if message.from_user.id != config.admin_id:
        return
    await state.set_state(Broadcast.message)
    await message.answer("Надішліть повідомлення для розсилки (текст, фото чи відео). /cancel — скасувати.")


@router.message(Broadcast.message, Command("cancel"))
async def broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Розсилку скасовано.")


@router.message(Broadcast.message)
async def broadcast_send(message: Message, state: FSMContext, users: Users):
    await state.clear()
    sent = failed = 0
    for user_id in users.active_ids():
        if await send_copy(message, user_id, users):
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(0.05)
    await message.answer(f"📬 Розсилку завершено.\nДоставлено: {sent}\nНе доставлено: {failed}")


async def send_copy(message: Message, user_id: int, users: Users, retry: bool = True) -> bool:
    try:
        await message.copy_to(user_id)
        return True
    except TelegramRetryAfter as e:
        if not retry:
            return False
        await asyncio.sleep(e.retry_after)
        return await send_copy(message, user_id, users, retry=False)
    except TelegramForbiddenError:
        users.deactivate(user_id)
        return False
    except TelegramBadRequest:
        return False


@router.callback_query()
async def stale_button(call: CallbackQuery):
    await call.answer("Кнопка застаріла. Почніть знову з меню.")
