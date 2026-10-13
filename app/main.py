import asyncio
import io
import logging
import re
import secrets
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path

import segno
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, glossary, llm
from app.allergens import ALLERGEN_IDS, ALLERGENS, LANG_NAMES, SOURCE_LANG, TARGET_LANGS
from app.db import Dish, Menu, get_session, init_db
from app.menu_parser import parse_menu

log = logging.getLogger(__name__)
HERE = Path(__file__).parent
MAX_DISHES = 120


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CartaClara", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(
    ALLERGENS=ALLERGENS, LANG_NAMES=LANG_NAMES, TARGET_LANGS=TARGET_LANGS, SOURCE_LANG=SOURCE_LANG
)


def _slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:60] or "menu"
    return f"{base}-{secrets.token_hex(2)}"


def _menu_by_token(session: Session, token: str) -> Menu:
    menu = session.scalar(select(Menu).where(Menu.edit_token == token))
    if menu is None:
        raise HTTPException(404)
    return menu


def _glossary_line(dish: Dish) -> str:
    parts = [f"{lang}: {dish.translations[lang]}" for lang in TARGET_LANGS if dish.translations.get(lang)]
    allergens = ", ".join(dish.allergens) or "none"
    return f'"{dish.name}" -> {"; ".join(parts)}; allergens: {allergens}'


@app.get("/healthz")
def healthz():
    return {"ok": True, "backend": config.LLM_BACKEND}


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"backend": config.LLM_BACKEND})


@app.post("/menus")
async def create_menu(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    restaurant_name = str(form.get("restaurant_name", "")).strip()
    parsed = parse_menu(str(form.get("menu_text", "")))[:MAX_DISHES]
    if not restaurant_name or not parsed:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"backend": config.LLM_BACKEND, "error": "Add a restaurant name and at least one dish."},
            status_code=400,
        )

    # An existing restaurant re-uses its glossary by passing its edit token back in.
    assistant_id = None
    previous_token = str(form.get("previous_token", "")).strip()
    if previous_token:
        previous = session.scalar(select(Menu).where(Menu.edit_token == previous_token))
        assistant_id = previous.backboard_assistant_id if previous else None
    if assistant_id is None:
        assistant_id = await glossary.create_assistant(restaurant_name)

    semaphore = asyncio.Semaphore(config.LLM_CONCURRENCY)

    async def suggest(name: str) -> dict | None:
        async with semaphore:
            try:
                house_rules = await glossary.recall(assistant_id, name)
                return await llm.suggest(name, house_rules)
            except Exception:
                log.exception("Suggestion failed for %r", name)
                return None

    suggestions = await asyncio.gather(*(suggest(d.name) for d in parsed))

    menu = Menu(
        slug=_slugify(restaurant_name),
        edit_token=secrets.token_urlsafe(24),
        restaurant_name=restaurant_name,
        backboard_assistant_id=assistant_id,
    )
    for position, (dish, suggestion) in enumerate(zip(parsed, suggestions)):
        suggestion = suggestion or {"translations": {}, "allergens": []}
        menu.dishes.append(
            Dish(
                position=position,
                section=dish.section,
                name=dish.name,
                price=dish.price,
                translations=suggestion["translations"],
                allergens=suggestion["allergens"],
                suggested=suggestion,
            )
        )
    session.add(menu)
    session.commit()
    return RedirectResponse(f"/edit/{menu.edit_token}", status_code=303)


@app.get("/edit/{token}")
def edit_menu(token: str, request: Request, session: Session = Depends(get_session)):
    menu = _menu_by_token(session, token)
    return templates.TemplateResponse(
        request,
        "edit.html",
        {
            "menu": menu,
            "public_url": f"{config.BASE_URL}/m/{menu.slug}",
            "unconfirmed": sum(not d.confirmed for d in menu.dishes),
            "notice": request.query_params.get("notice", ""),
            "glossary_enabled": glossary.enabled,
        },
    )


@app.post("/edit/{token}")
async def save_menu(token: str, request: Request, session: Session = Depends(get_session)):
    menu = _menu_by_token(session, token)
    form = await request.form()

    corrections: list[Dish] = []
    for dish in menu.dishes:
        dish.translations = {
            lang: value
            for lang in TARGET_LANGS
            if (value := str(form.get(f"{lang}_{dish.id}", "")).strip())
        }
        picked = set(form.getlist(f"allergens_{dish.id}"))
        dish.allergens = [a for a in ALLERGEN_IDS if a in picked]
        dish.confirmed = form.get(f"confirmed_{dish.id}") == "on"

        current = {"translations": dish.translations, "allergens": dish.allergens}
        if dish.confirmed and current != dish.suggested:
            corrections.append(dish)
            # Remembered once; later saves of the same values are not corrections.
            dish.suggested = current

    # A menu is only ever public while every dish on it is confirmed.
    all_confirmed = all(d.confirmed for d in menu.dishes)
    notice = "saved"
    if form.get("action") == "unpublish":
        menu.published = False
    elif not all_confirmed:
        if menu.published or form.get("action") == "publish":
            notice = "unconfirmed"
        menu.published = False
    elif form.get("action") == "publish":
        menu.published = True
        notice = "published"
    session.commit()

    await asyncio.gather(
        *(glossary.remember(menu.backboard_assistant_id, _glossary_line(d), d.name) for d in corrections)
    )
    return RedirectResponse(f"/edit/{token}?notice={notice}", status_code=303)


def _published_menu(session: Session, slug: str) -> Menu:
    menu = session.scalar(select(Menu).where(Menu.slug == slug))
    if menu is None or not menu.published:
        raise HTTPException(404)
    return menu


@app.get("/m/{slug}")
def public_menu(slug: str, request: Request, lang: str = "en", session: Session = Depends(get_session)):
    menu = _published_menu(session, slug)
    if lang not in LANG_NAMES:
        lang = "en"
    return templates.TemplateResponse(request, "menu.html", {"menu": menu, "lang": lang})


@app.get("/m/{slug}/qr.svg")
def qr_code(slug: str, session: Session = Depends(get_session)):
    menu = session.scalar(select(Menu).where(Menu.slug == slug))
    if menu is None:
        raise HTTPException(404)
    buffer = io.BytesIO()
    segno.make(f"{config.BASE_URL}/m/{menu.slug}", error="m").save(buffer, kind="svg", scale=8, border=2)
    return Response(buffer.getvalue(), media_type="image/svg+xml")
