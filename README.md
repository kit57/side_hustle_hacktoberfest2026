# CartaClara

A restaurant pastes its menu in Spanish and gets a QR menu in English, French and German, with the 14 EU allergens tagged per dish. An open-weight model fine-tuned on Spanish dishes makes the suggestions; the owner confirms every dish before the menu can go public.

Built for the Hacktoberfest Open-Source AI Challenge, Week 2 ("Side Hustle").

## Run it locally

```bash
python -m venv .venv
.venv/Scripts/activate            # source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000. With an empty `.env` the app uses the `mock` backend, which returns placeholder translations so you can click through the whole flow without a model.

Run the tests with `pytest`.

## Model backends

`LLM_BACKEND` picks where suggestions come from. The prompt and output format are the same for all three ([app/prompts.py](app/prompts.py)).

| Backend | What it runs | Needs |
|---|---|---|
| `mock` | Placeholder text, no model | nothing |
| `openai` | Any OpenAI-compatible server, e.g. an open-weight model in Ollama on your laptop | `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| `tinker` | The fine-tuned checkpoint (or the base model) on Tinker | `TINKER_API_KEY`, `TINKER_MODEL_PATH` |

## Fine-tune on Tinker

The dataset is one JSON object per line: a Spanish dish, its three translations and its allergen ids. [training/data/seed.jsonl](training/data/seed.jsonl) has 24 examples to prove the pipeline; a useful model needs a few hundred, each checked by someone who knows the dish.

```bash
export TINKER_API_KEY=...
python -m training.train --data training/data/seed.jsonl --epochs 4
# prints TINKER_MODEL_PATH=tinker://...
python -m training.eval --model-path tinker://...
```

`eval.py` scores the base model and the checkpoint on dishes held out from training: valid JSON rate, and allergen precision and recall. Recall is the number to watch, because a missed allergen is the dangerous mistake.

## Restaurant glossary (Backboard)

With `BACKBOARD_API_KEY` set, each restaurant gets a Backboard assistant. When the owner corrects a suggestion and confirms it, the correction is stored as a memory. The next menu for that restaurant looks up memories for each dish and adds them to the prompt, so a fix is only ever made once. Without the key the app works the same, minus the memory.

## Deploy on Render

[render.yaml](render.yaml) defines the web service and a Postgres database. Create a Blueprint from the repo, then set `TINKER_API_KEY`, `TINKER_MODEL_PATH`, `BACKBOARD_API_KEY` and `BASE_URL` (your public origin, used in the QR codes) in the dashboard.

## How it fits together

- [app/main.py](app/main.py): routes for creating, reviewing, publishing and serving a menu
- [app/llm.py](app/llm.py): the three model backends
- [app/prompts.py](app/prompts.py): prompt and JSON output format, shared with training
- [app/glossary.py](app/glossary.py): Backboard memory client
- [app/allergens.py](app/allergens.py): the 14 allergens and their labels in four languages
- [training/](training/): dataset loading, Tinker LoRA fine-tune, base-vs-tuned eval

## Not built yet

- Menu photos as input (the base model accepts images; the app only takes text so far)
- Owner accounts: the edit link is the only credential
- Database migrations: tables are created on startup
