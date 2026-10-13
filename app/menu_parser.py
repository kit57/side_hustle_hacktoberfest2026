import re
from dataclasses import dataclass

# A trailing price: "12", "12,50", "12.50 €", "€12".
_PRICE = re.compile(r"[\s.·\-–—]*(€\s*)?(\d{1,3}(?:[.,]\d{1,2})?)\s*(€|eur|euros)?\s*$", re.IGNORECASE)


@dataclass
class ParsedDish:
    section: str
    name: str
    price: str


def _is_section(line: str) -> bool:
    if line.startswith("#") or line.endswith(":"):
        return True
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and not _PRICE.search(line)


def parse_menu(text: str) -> list[ParsedDish]:
    """One dish per line. Lines starting with '#', ending with ':' or in ALL CAPS are sections."""
    dishes: list[ParsedDish] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _is_section(line):
            section = line.strip("#: ").title() if line.isupper() else line.strip("#: ")
            continue
        price = ""
        match = _PRICE.search(line)
        if match and match.start() > 0:
            price = match.group(2).replace(".", ",")
            line = line[: match.start()].strip()
        if line:
            dishes.append(ParsedDish(section=section, name=line, price=price))
    return dishes
