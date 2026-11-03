import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv

from parser import MAX_PAGES, scrape, summary, to_excel

router = Router()
busy_users: set[int] = set()

BTN_QUICK = "📊 Спарсити 5 сторінок"
menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_QUICK)]], resize_keyboard=True)


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Я збираю каталог книг з books.toscrape.com і надсилаю Excel-файл 📈\n\n"
        f"/parse N — спарсити N сторінок (1–{MAX_PAGES}, на сторінці 20 книг)",
        reply_markup=menu,
    )


async def run_parse(message: Message, pages: int):
    user_id = message.from_user.id
    if user_id in busy_users:
        await message.answer("⏳ Попередній запит ще виконується, зачекайте.")
        return
    busy_users.add(user_id)
    status = await message.answer(f"🔎 Парсю {pages} сторінок...")
    try:
        books = await asyncio.to_thread(scrape, pages)
        data = await asyncio.to_thread(to_excel, books)
    except Exception:
        logging.exception("Помилка парсингу")
        await status.edit_text("❌ Сайт недоступний або змінилась структура. Спробуйте пізніше.")
        return
    finally:
        busy_users.discard(user_id)

    await status.edit_text(summary(books))
    filename = f"books_{datetime.now():%Y%m%d_%H%M}.xlsx"
    await message.answer_document(BufferedInputFile(data, filename=filename), caption="Готово ✅")


@router.message(F.text == BTN_QUICK)
async def quick(message: Message):
    await run_parse(message, 5)


@router.message(Command("parse"))
async def parse_cmd(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    if not arg.isascii() or not arg.isdigit() or not 1 <= int(arg) <= MAX_PAGES:
        await message.answer(f"Вкажіть кількість сторінок від 1 до {MAX_PAGES}, наприклад: /parse 3")
        return
    await run_parse(message, int(arg))


async def main():
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Задайте BOT_TOKEN у файлі .env")
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
