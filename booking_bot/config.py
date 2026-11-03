import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

SERVICES = {
    "haircut": ("Чоловіча стрижка", 400, 60),
    "beard": ("Моделювання бороди", 250, 30),
    "combo": ("Стрижка + борода", 600, 90),
    "kids": ("Дитяча стрижка", 300, 45),
}

WORK_HOURS = range(10, 19)
DAYS_AHEAD = 7


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int
    db_path: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    admin_id = os.getenv("ADMIN_ID")
    if not token or not admin_id:
        raise RuntimeError("Задайте BOT_TOKEN та ADMIN_ID у файлі .env")
    return Config(
        bot_token=token,
        admin_id=int(admin_id),
        db_path=os.getenv("DB_PATH", "booking.db"),
    )
