import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

COMPANY = "WebStudio"

SERVICES = {
    "landing": "Лендінг",
    "shop": "Інтернет-магазин",
    "bot": "Telegram-бот",
    "seo": "SEO-просування",
    "other": "Інше",
}

FAQ = {
    "price": ("Скільки коштує?", "Лендінг — від 8 000 грн, бот — від 3 000 грн. Точну ціну назвемо після брифу."),
    "time": ("Які терміни?", "Лендінг — 5–7 днів, інтернет-магазин — від 3 тижнів, бот — 2–5 днів."),
    "pay": ("Як оплачувати?", "50% передоплата, 50% після здачі. Працюємо як ФОП, даємо документи."),
    "support": ("Чи є підтримка?", "Так, 1 місяць безкоштовної підтримки після запуску."),
}


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int
    db_path: str
    sheet_id: str | None
    credentials_file: str
    csv_path: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    admin_id = os.getenv("ADMIN_ID")
    if not token or not admin_id:
        raise RuntimeError("Задайте BOT_TOKEN та ADMIN_ID у файлі .env")
    return Config(
        bot_token=token,
        admin_id=int(admin_id),
        db_path=os.getenv("DB_PATH", "leads.db"),
        sheet_id=os.getenv("GOOGLE_SHEET_ID") or None,
        credentials_file=os.getenv("GOOGLE_CREDENTIALS", "credentials.json"),
        csv_path=os.getenv("CSV_PATH", "leads.csv"),
    )
