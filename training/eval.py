"""Compare the base model with the fine-tuned checkpoint on the held-out dishes.

    python -m training.eval --model-path tinker://<run_id>/sampler_weights/menu-v1

Scores allergen tagging (the part that can be scored automatically) and prints the
translations side by side for a human to judge.
"""

import argparse
from pathlib import Path

import tinker

from app import config
from app.prompts import build_messages, chat_prompt_text, parse_answer
from training.dataset import load_examples, split


def predict(client, tokenizer, dish: str) -> dict | None:
    tokens = tokenizer.encode(
        chat_prompt_text(tokenizer, build_messages(dish)), add_special_tokens=False
    )
    result = client.sample(
        prompt=tinker.types.ModelInput.from_ints(tokens),
        num_samples=1,
        sampling_params=tinker.types.SamplingParams(max_tokens=400, temperature=0.0),
    ).result()
    return parse_answer(tokenizer.decode(result.sequences[0].tokens, skip_special_tokens=True))


def score(label: str, client, examples: list[dict]) -> None:
    tokenizer = client.get_tokenizer()
    invalid = exact = tp = fp = fn = 0
    print(f"\n=== {label} ===")
    for example in examples:
        prediction = predict(client, tokenizer, example["dish"])
        if prediction is None:
            invalid += 1
            fn += len(example["allergens"])
            print(f"{example['dish']}: unusable reply")
            continue
        gold, got = set(example["allergens"]), set(prediction["allergens"])
        exact += gold == got
        tp += len(gold & got)
        fp += len(got - gold)
        fn += len(gold - got)
        print(f"{example['dish']}: {prediction['translations'].get('en', '-')}")
        print(f"    allergens {sorted(got)} (expected {sorted(gold)})")
    n = len(examples)
    precision = tp / (tp + fp) if tp + fp else 0.0
    # Recall is the number that matters: a missed allergen is the dangerous error.
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(
        f"{label}: valid JSON {n - invalid}/{n}, exact allergen set {exact}/{n}, "
        f"precision {precision:.2f}, recall {recall:.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("training/data/seed.jsonl"))
    parser.add_argument("--base-model", default=config.TINKER_BASE_MODEL)
    parser.add_argument("--model-path", default=config.TINKER_MODEL_PATH)
    parser.add_argument("--eval-fraction", type=float, default=0.15)
    args = parser.parse_args()

    _, eval_examples = split(load_examples(args.data), args.eval_fraction)
    service = tinker.ServiceClient()
    score("base", service.create_sampling_client(base_model=args.base_model), eval_examples)
    if args.model_path:
        score("fine-tuned", service.create_sampling_client(model_path=args.model_path), eval_examples)
    else:
        print("\nNo --model-path given; only the base model was scored.")


if __name__ == "__main__":
    main()
