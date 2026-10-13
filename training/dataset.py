import json
import random
from pathlib import Path

from app.allergens import ALLERGEN_IDS, TARGET_LANGS

DATA_DIR = Path(__file__).parent / "data"


def load_examples(path: Path) -> list[dict]:
    examples = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        example = json.loads(line)
        missing = [k for k in ("dish", "allergens", *TARGET_LANGS) if k not in example]
        unknown = [a for a in example.get("allergens", []) if a not in ALLERGEN_IDS]
        if missing or unknown:
            raise ValueError(f"{path.name}:{number}: missing {missing}, unknown allergens {unknown}")
        examples.append(example)
    return examples


def split(examples: list[dict], eval_fraction: float, seed: int = 0) -> tuple[list[dict], list[dict]]:
    """Deterministic train/eval split, so eval.py scores dishes train.py never saw."""
    shuffled = examples[:]
    random.Random(seed).shuffle(shuffled)
    n_eval = max(1, round(len(shuffled) * eval_fraction))
    return shuffled[n_eval:], shuffled[:n_eval]
