"""LoRA fine-tune an open-weight model on dish -> translations + allergens, on Tinker.

    python -m training.train --data training/data/seed.jsonl --epochs 4

Prints the tinker:// checkpoint path to put in TINKER_MODEL_PATH.
"""

import argparse
import random
from pathlib import Path

import tinker

from app import config
from app.prompts import build_messages, chat_prompt_text, format_answer
from training.dataset import load_examples, split


def to_datum(tokenizer, example: dict) -> tinker.Datum:
    prompt = tokenizer.encode(
        chat_prompt_text(tokenizer, build_messages(example["dish"])), add_special_tokens=False
    )
    # The end-of-turn token is part of the target, so the model learns to stop.
    completion = tokenizer.encode(
        format_answer(example) + tokenizer.eos_token, add_special_tokens=False
    )
    tokens = prompt + completion
    # Loss only on the answer, not on the prompt.
    weights = [0.0] * len(prompt) + [1.0] * len(completion)
    return tinker.Datum(
        model_input=tinker.ModelInput.from_ints(tokens[:-1]),
        loss_fn_inputs={"target_tokens": tokens[1:], "weights": weights[1:]},
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("training/data/seed.jsonl"))
    parser.add_argument("--base-model", default=config.TINKER_BASE_MODEL)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--eval-fraction", type=float, default=0.15)
    parser.add_argument("--name", default="menu-v1")
    args = parser.parse_args()

    train_examples, eval_examples = split(load_examples(args.data), args.eval_fraction)
    print(f"{len(train_examples)} train / {len(eval_examples)} held out for eval")

    service = tinker.ServiceClient()
    training = service.create_lora_training_client(base_model=args.base_model, rank=args.rank)
    tokenizer = training.get_tokenizer()
    data = [to_datum(tokenizer, e) for e in train_examples]

    rng = random.Random(0)
    step = 0
    for epoch in range(args.epochs):
        rng.shuffle(data)
        for start in range(0, len(data), args.batch_size):
            batch = data[start : start + args.batch_size]
            # Queue both before waiting so they land in the same training clock cycle.
            fwdbwd = training.forward_backward(batch, "cross_entropy")
            optim = training.optim_step(tinker.AdamParams(learning_rate=args.lr))
            result = fwdbwd.result()
            optim.result()
            step += 1
            print(f"epoch {epoch + 1} step {step} metrics {dict(result.metrics)}")

    checkpoint = training.save_weights_for_sampler(name=args.name).result()
    print(f"\nTINKER_MODEL_PATH={checkpoint.path}")


if __name__ == "__main__":
    main()
