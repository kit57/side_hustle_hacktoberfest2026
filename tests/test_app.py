import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LLM_BACKEND"] = "mock"
os.environ["BACKBOARD_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from app import db
from app.main import app
from app.menu_parser import parse_menu
from app.prompts import format_answer, parse_answer

# One shared in-memory database for the whole test run.
db.engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
db.SessionLocal.configure(bind=db.engine)

MENU = "ENTRANTES\nSalmorejo cordobés 6,50\nCroquetas de jamón 8 €\nPostres:\nFlan de huevo"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_parse_menu_sections_and_prices():
    dishes = parse_menu(MENU)
    assert [(d.section, d.name, d.price) for d in dishes] == [
        ("Entrantes", "Salmorejo cordobés", "6,50"),
        ("Entrantes", "Croquetas de jamón", "8"),
        ("Postres", "Flan de huevo", ""),
    ]


def test_parse_answer_drops_unknown_allergens_and_tolerates_wrapping():
    text = 'Sure:\n{"en": "Egg custard", "fr": "Flan", "de": "", "allergens": ["milk", "eggs", "love"]}'
    assert parse_answer(text) == {
        "translations": {"en": "Egg custard", "fr": "Flan"},
        "allergens": ["eggs", "milk"],
    }
    assert parse_answer("no json here") is None


def test_format_answer_round_trips():
    example = {"dish": "x", "en": "a", "fr": "b", "de": "c", "allergens": ["fish"]}
    assert parse_answer(format_answer(example)) == {
        "translations": {"en": "a", "fr": "b", "de": "c"},
        "allergens": ["fish"],
    }


def _create(client) -> str:
    r = client.post(
        "/menus", data={"restaurant_name": "Casa Lola", "menu_text": MENU}, follow_redirects=False
    )
    assert r.status_code == 303
    return r.headers["location"]


def _dish_ids(edit_url: str) -> list[int]:
    token = edit_url.rsplit("/", 1)[1]
    with db.SessionLocal() as session:
        menu = session.scalar(select(db.Menu).where(db.Menu.edit_token == token))
        return [d.id for d in menu.dishes]


def test_menu_is_private_until_every_dish_is_confirmed(client):
    edit_url = _create(client)
    page = client.get(edit_url)
    assert page.status_code == 200 and "Salmorejo cordobés" in page.text

    ids = _dish_ids(edit_url)
    form = {f"en_{i}": f"Dish {i}" for i in ids}
    form[f"allergens_{ids[0]}"] = ["gluten", "eggs"]

    # Publishing with unconfirmed dishes is refused.
    r = client.post(edit_url, data={**form, "action": "publish"}, follow_redirects=False)
    assert r.headers["location"].endswith("notice=unconfirmed")

    confirmed = {**form, **{f"confirmed_{i}": "on" for i in ids}}
    r = client.post(edit_url, data={**confirmed, "action": "publish"}, follow_redirects=False)
    assert r.headers["location"].endswith("notice=published")

    with db.SessionLocal() as session:
        slug = session.scalar(select(db.Menu.slug).order_by(db.Menu.id.desc()))
    public = client.get(f"/m/{slug}?lang=de")
    assert public.status_code == 200
    assert "Eier" in public.text and "Gluten" in public.text
    assert client.get(f"/m/{slug}/qr.svg").headers["content-type"].startswith("image/svg")

    # Un-confirming a dish takes the menu offline again.
    client.post(edit_url, data={**form, "action": "save"})
    assert client.get(f"/m/{slug}").status_code == 404


def test_empty_menu_is_rejected(client):
    r = client.post("/menus", data={"restaurant_name": "X", "menu_text": "  "})
    assert r.status_code == 400
