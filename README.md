# Портфоліо: Telegram-боти та парсинг на Python

| Проєкт | Що робить | Стек |
|---|---|---|
| [💈 booking_bot](booking_bot) | Онлайн-запис клієнтів: послуги, вільні слоти, скасування, сповіщення адміну | aiogram 3, SQLite, FSM |
| [☕ shop_bot](shop_bot) | Магазин: каталог, кошик, оформлення з НП, статуси замовлень | aiogram 3, SQLite, FSM |
| [📝 leads_bot](leads_bot) | Заявки в Google Таблицю, FAQ, розсилки, статистика | aiogram 3, gspread, SQLite |
| [📊 parser_bot](parser_bot) | Парсинг каталогу сайту → стилізований Excel прямо в Telegram | requests, BS4, openpyxl, aiogram 3 |

Кожен проєкт самостійний: свій `requirements.txt`, `.env.example` і інструкція запуску.

```bash
cd booking_bot
pip install -r requirements.txt
cp .env.example .env
python bot.py
```
