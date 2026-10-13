"""Per-restaurant glossary, stored as Backboard memories.

Each restaurant gets one Backboard assistant. When the owner corrects a suggestion,
the correction is saved as a memory; the next time that restaurant generates a menu,
memories relevant to each dish are looked up and added to the prompt.

Everything here is best-effort: with no BACKBOARD_API_KEY, or if Backboard is down,
the app keeps working without a glossary.
"""

import logging

import httpx

from app.config import BACKBOARD_API_KEY, BACKBOARD_BASE_URL

log = logging.getLogger(__name__)

enabled = bool(BACKBOARD_API_KEY)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BACKBOARD_BASE_URL, headers={"X-API-Key": BACKBOARD_API_KEY}, timeout=15
    )


async def create_assistant(restaurant_name: str) -> str | None:
    if not enabled:
        return None
    try:
        async with _client() as client:
            r = await client.post(
                "/assistants",
                json={
                    "name": f"Menu glossary: {restaurant_name}"[:100],
                    "system_prompt": "Stores a restaurant's confirmed dish translations and allergens.",
                },
            )
            r.raise_for_status()
            return r.json().get("assistant_id")
    except httpx.HTTPError as e:
        log.warning("Backboard create_assistant failed: %s", e)
        return None


async def remember(assistant_id: str | None, content: str, dish: str) -> None:
    if not (enabled and assistant_id):
        return
    try:
        async with _client() as client:
            r = await client.post(
                f"/assistants/{assistant_id}/memories",
                json={"content": content, "metadata": {"dish": dish}},
            )
            r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Backboard remember failed: %s", e)


async def recall(assistant_id: str | None, dish: str, limit: int = 3) -> list[str]:
    if not (enabled and assistant_id):
        return []
    try:
        async with _client() as client:
            r = await client.post(
                f"/assistants/{assistant_id}/memories/search",
                json={"query": dish, "limit": limit},
            )
            r.raise_for_status()
            return [m["content"] for m in r.json().get("memories", []) if m.get("content")]
    except httpx.HTTPError as e:
        log.warning("Backboard recall failed: %s", e)
        return []
