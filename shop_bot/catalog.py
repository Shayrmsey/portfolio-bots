from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: int
    category: str
    name: str
    price: int
    description: str


CATEGORIES = {
    "coffee": "☕ Кава в зернах",
    "tea": "🍵 Чай",
    "gear": "🫖 Аксесуари",
}

PRODUCTS = [
    Product(1, "coffee", "Ефіопія Іргачеф 250 г", 420, "Світле обсмаження, ноти бергамоту та жасмину."),
    Product(2, "coffee", "Колумбія Супремо 250 г", 360, "Середнє обсмаження, шоколад і горіх."),
    Product(3, "coffee", "Бразилія Сантос 1 кг", 990, "Темне обсмаження для еспресо."),
    Product(4, "tea", "Сенча 100 г", 210, "Японський зелений чай, свіжий трав'янистий смак."),
    Product(5, "tea", "Ассам 100 г", 180, "Міцний чорний чай для ранку."),
    Product(6, "gear", "Френч-прес 600 мл", 550, "Скло і нержавіюча сталь."),
    Product(7, "gear", "Ручна кавомолка", 890, "Керамічні жорна, 15 ступенів помелу."),
]

PRODUCTS_BY_ID = {p.id: p for p in PRODUCTS}


def products_in(category: str) -> list[Product]:
    return [p for p in PRODUCTS if p.category == category]
