"""Model backends. Each turns chat messages into the model's raw text reply.

The backend is picked with LLM_BACKEND, so the same app runs against the
fine-tuned Tinker checkpoint, a local open-weight model, or a canned mock.
"""

import asyncio
import json

import httpx

from app import config
from app.prompts import build_messages, chat_prompt_text, parse_answer

MAX_TOKENS = 400


class MockBackend:
    """No model at all: lets the UI and tests run offline."""

    name = "mock"

    async def complete(self, messages: list[dict]) -> str:
        dish = messages[-1]["content"].splitlines()[0]
        return json.dumps(
            {"en": f"[en] {dish}", "fr": f"[fr] {dish}", "de": f"[de] {dish}", "allergens": []}
        )


class OpenAIBackend:
    """Any OpenAI-compatible server, e.g. Ollama running an open-weight model locally."""

    name = "openai"

    async def complete(self, messages: list[dict]) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                json={
                    "model": config.OPENAI_MODEL,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": MAX_TOKENS,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]


class TinkerBackend:
    """Samples from a Tinker checkpoint (or the base model when no path is set)."""

    name = "tinker"

    def __init__(self) -> None:
        self._client = None
        self._tokenizer = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> None:
        async with self._lock:
            if self._client is not None:
                return
            import tinker

            service = tinker.ServiceClient()
            if config.TINKER_MODEL_PATH:
                self._client = await service.create_sampling_client_async(
                    model_path=config.TINKER_MODEL_PATH
                )
            else:
                self._client = await service.create_sampling_client_async(
                    base_model=config.TINKER_BASE_MODEL
                )
            self._tokenizer = self._client.get_tokenizer()

    async def complete(self, messages: list[dict]) -> str:
        import tinker

        await self._ensure()
        tokens = self._tokenizer.encode(
            chat_prompt_text(self._tokenizer, messages), add_special_tokens=False
        )
        result = await self._client.sample_async(
            prompt=tinker.types.ModelInput.from_ints(tokens),
            num_samples=1,
            sampling_params=tinker.types.SamplingParams(max_tokens=MAX_TOKENS, temperature=0.0),
        )
        return self._tokenizer.decode(result.sequences[0].tokens, skip_special_tokens=True)


_BACKENDS = {"mock": MockBackend, "openai": OpenAIBackend, "tinker": TinkerBackend}
_backend = None


def get_backend():
    global _backend
    if _backend is None:
        if config.LLM_BACKEND not in _BACKENDS:
            raise RuntimeError(
                f"LLM_BACKEND={config.LLM_BACKEND!r}; expected one of {sorted(_BACKENDS)}"
            )
        _backend = _BACKENDS[config.LLM_BACKEND]()
    return _backend


async def suggest(dish: str, glossary: list[str] | None = None) -> dict | None:
    """Translations and allergens for one dish, or None if the model's reply was unusable."""
    text = await get_backend().complete(build_messages(dish, glossary))
    return parse_answer(text)
