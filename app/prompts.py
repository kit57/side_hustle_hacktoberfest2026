"""Prompt and output format, shared by the app and by training/.

Training and serving must render the exact same prompt, so both import from here.
"""

import json

from app.allergens import ALLERGEN_IDS, TARGET_LANGS

SYSTEM_PROMPT = (
    "You translate dishes from Spanish restaurant menus and flag allergens.\n"
    "Given a dish name in Spanish, reply with one JSON object and nothing else:\n"
    '{"en": "...", "fr": "...", "de": "...", "allergens": ["..."]}\n'
    "Each translation keeps the dish's own name when it has no real equivalent and "
    "adds a short description a tourist would understand.\n"
    '"allergens" lists the allergens the traditional recipe contains, using only these ids: '
    + ", ".join(ALLERGEN_IDS)
    + ". Use an empty list when there are none."
)


def build_messages(dish: str, glossary: list[str] | None = None) -> list[dict]:
    user = dish.strip()
    if glossary:
        # House rules the owner already confirmed for this restaurant.
        user += "\n\nHouse glossary (follow it):\n" + "\n".join(f"- {g}" for g in glossary)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def format_answer(example: dict) -> str:
    """The assistant turn for one training example."""
    out = {lang: example[lang] for lang in TARGET_LANGS}
    out["allergens"] = example["allergens"]
    return json.dumps(out, ensure_ascii=False)


def parse_answer(text: str) -> dict | None:
    """Pull the JSON object out of a model reply. None if it is unusable."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    translations = {
        lang: data[lang].strip()
        for lang in TARGET_LANGS
        if isinstance(data.get(lang), str) and data[lang].strip()
    }
    if not translations:
        return None
    raw = data.get("allergens")
    allergens = [a for a in ALLERGEN_IDS if isinstance(raw, list) and a in raw]
    return {"translations": translations, "allergens": allergens}


def chat_prompt_text(tokenizer, messages: list[dict]) -> str:
    """Render messages up to the start of the assistant turn, thinking off."""
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
