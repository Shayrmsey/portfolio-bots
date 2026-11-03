import argparse
import io
import logging
import time
from dataclasses import astuple, dataclass
from html import escape
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

BASE_URL = "https://books.toscrape.com/catalogue/"
PAGE_URL = BASE_URL + "page-{}.html"
MAX_PAGES = 50
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
HEADERS = ["Назва", "Ціна, £", "Рейтинг", "Наявність", "Посилання"]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Book:
    title: str
    price: float
    rating: int
    in_stock: bool
    url: str


def parse_page(html: str) -> list[Book]:
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        rating_class = card.select_one("p.star-rating")["class"][-1]
        price_text = card.select_one("p.price_color").get_text(strip=True)
        books.append(
            Book(
                title=link["title"],
                price=float(price_text.lstrip("£Â")),
                rating=RATINGS.get(rating_class, 0),
                in_stock="In stock" in card.select_one("p.availability").get_text(),
                url=urljoin(BASE_URL, link["href"]),
            )
        )
    return books


def scrape(pages: int, delay: float = 0.3) -> list[Book]:
    pages = max(1, min(pages, MAX_PAGES))
    books: list[Book] = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "Mozilla/5.0 (portfolio parser demo)"
        for page in range(1, pages + 1):
            resp = session.get(PAGE_URL.format(page), timeout=15)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            resp.encoding = "utf-8"
            books.extend(parse_page(resp.text))
            log.info("Сторінка %s: всього %s книг", page, len(books))
            time.sleep(delay)
    return books


def to_excel(books: list[Book]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Books"
    ws.append(HEADERS)
    for book in books:
        title, price, rating, in_stock, url = astuple(book)
        ws.append([title, price, "★" * rating, "Так" if in_stock else "Ні", url])
        ws.cell(row=ws.max_row, column=5).hyperlink = url

    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
    for idx, width in enumerate([55, 10, 10, 12, 60], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def summary(books: list[Book]) -> str:
    if not books:
        return "Нічого не знайдено."
    avg = sum(b.price for b in books) / len(books)
    best = sorted((b for b in books if b.rating == 5), key=lambda b: b.price)[:3]
    lines = [
        f"📚 Зібрано книг: <b>{len(books)}</b>",
        f"💷 Середня ціна: <b>£{avg:.2f}</b>",
        f"✅ В наявності: <b>{sum(b.in_stock for b in books)}</b>",
    ]
    if best:
        lines.append("\n⭐ Найдешевші з рейтингом 5/5:")
        lines += [f"• {escape(b.title)} — £{b.price:.2f}" for b in best]
    return "\n".join(lines)


def main():
    logging.basicConfig(level=logging.INFO)
    args = argparse.ArgumentParser(description="Парсер books.toscrape.com → Excel")
    args.add_argument("--pages", type=int, default=3, help=f"кількість сторінок (1–{MAX_PAGES})")
    args.add_argument("--out", default="books.xlsx", help="файл для збереження")
    opts = args.parse_args()

    books = scrape(opts.pages)
    with open(opts.out, "wb") as f:
        f.write(to_excel(books))
    print(f"Збережено {len(books)} книг у {opts.out}")


if __name__ == "__main__":
    main()
