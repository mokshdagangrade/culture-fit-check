"""LoRA supervised fine-tuning on a single NVIDIA GPU (run on Linux).

Quantization is chosen from the card unless you force it: below ~22 GiB of
VRAM the base is loaded in 4-bit (QLoRA), above it in bf16, which avoids the
quantization error for no practical cost on a 24 GB+ GPU.

    python training/train.py                       # auto
    python training/train.py --quantization 4bit   # force QLoRA
    python training/train.py --max-steps 2         # smoke test
"""
import argparse
import json
from pathlib import Path

BASE_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
# Below this, load 4-bit. A 4B in bf16 is ~8 GiB of weights before activations.
BF16_VRAM_FLOOR_GIB = 22


def token_ids(result):
    """Normalise apply_chat_template output to a flat list of ids.

    Depending on the transformers version it returns a list, a nested list, or
    a BatchEncoding, and the default changed under us.
    """
    if hasattr(result, "input_ids"):          # BatchEncoding
        result = result.input_ids
    elif isinstance(result, dict):
        result = result["input_ids"]
    if result and isinstance(result[0], (list, tuple)):
        result = result[0]
    return list(result)


def end_of_turn_id(tokenizer):
    """The token the model must learn to stop on."""
    for name in ("<|im_end|>", "<|endoftext|>"):
        token = tokenizer.convert_tokens_to_ids(name)
        if token is not None and token != tokenizer.unk_token_id:
            return token
    return tokenizer.eos_token_id


def encode_example(messages, tokenizer, max_length):
    """Build the sequence as (inference prefix) + (assistant tokens).

    The prefix is exactly what apply_chat_template produces with
    add_generation_prompt=True -- i.e. what vLLM will send at inference -- so
    the adapter is trained on the string it will actually be asked to continue.

    An earlier version rendered the whole conversation and asserted the
    prompt-only rendering was a token prefix of it. That does not hold for
    every chat template: Qwen3's inserts generation-time scaffolding that the
    full rendering does not reproduce, so the assertion fired on valid data.
    Composing the sequence instead of checking it makes the property true by
    construction.
    """
    prefix = token_ids(tokenizer.apply_chat_template(
        messages[:-1], tokenize=True, add_generation_prompt=True))
    completion = token_ids(tokenizer(messages[-1]["content"], add_special_tokens=False))
    if not completion:
        raise ValueError("Example has no assistant tokens")
    target = completion + [end_of_turn_id(tokenizer)]
    if len(prefix) + len(target) > max_length:
        return None
    return {"input_ids": prefix + target, "attention_mask": [1] * (len(prefix) + len(target)),
            "labels": [-100] * len(prefix) + target}


def attention_implementation():
    """FlashAttention-2 needs Ampere or newer; SDPA everywhere else."""
    try:
        import flash_attn  # noqa: F401
        import torch

        if torch.cuda.get_device_capability()[0] >= 8:
            return "flash_attention_2"
    except Exception:
        pass
    return "sdpa"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=BASE_MODEL)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "out")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "checkpoints" / "brand-qwen")
    parser.add_argument("--max-length", type=int, default=4096,
                        help="Serving-shaped prompts run ~550 tokens; headroom is cheap on a big GPU")
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--max-steps", type=int, default=-1, help="Use 2 for a training smoke test")
    parser.add_argument("--quantization", choices=["auto", "4bit", "none"], default="auto")
    parser.add_argument("--batch-size", type=int, default=0, help="0 picks from VRAM")
    parser.add_argument("--grad-accum", type=int, default=0, help="0 targets an effective batch of 16")
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--neftune", type=float, default=5.0,
                        help="Embedding noise; helps small-data SFT. 0 disables.")
    parser.add_argument("--resume-from-checkpoint")
    args = parser.parse_args()
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              Trainer, TrainingArguments, set_seed)

    if not torch.cuda.is_available():
        raise RuntimeError("This recipe requires an NVIDIA CUDA GPU. Run on a Linux GPU machine.")
    set_seed(42)

    device = torch.cuda.current_device()
    vram_gib = torch.cuda.get_device_properties(device).total_memory / 1024 ** 3
    quantization = args.quantization
    if quantization == "auto":
        quantization = "none" if vram_gib >= BF16_VRAM_FLOOR_GIB else "4bit"
    batch_size = args.batch_size or (4 if vram_gib >= 40 else 2 if vram_gib >= 22 else 1)
    grad_accum = args.grad_accum or max(1, 16 // batch_size)
    attn = attention_implementation()
    print(f"GPU {torch.cuda.get_device_name(device)} ({vram_gib:.0f} GiB) | "
          f"quantization={quantization} | attn={attn} | "
          f"batch={batch_size} x accum={grad_accum}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokenizer.pad_token = tokenizer.eos_token
    datasets, report = {}, {
        "base_model": args.model, "max_length": args.max_length, "splits": {},
        # Recorded so a result can be traced to the machine that produced it.
        "gpu": torch.cuda.get_device_name(device), "vram_gib": round(vram_gib, 1),
        "quantization": quantization, "attn_implementation": attn,
        "effective_batch": batch_size * grad_accum, "epochs": args.epochs,
        "learning_rate": args.learning_rate, "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha, "neftune": args.neftune,
    }
    for name in ("train", "validation"):
        encoded, dropped = [], 0
        for line in (args.data_dir / f"{name}.jsonl").read_text().splitlines():
            row = encode_example(json.loads(line)["messages"], tokenizer, args.max_length)
            if row is None:
                dropped += 1
            else:
                encoded.append(row)
        if not encoded:
            raise ValueError(f"No usable examples in {name}")
        if dropped:
            print(f"WARNING: {name} dropped {dropped} overlength examples "
                  f"(--max-length {args.max_length})", flush=True)
        datasets[name] = Dataset.from_list(encoded)
        report["splits"][name] = {"kept": len(encoded), "excluded_overlength": dropped}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "tokenization_report.json").write_text(json.dumps(report, indent=2))

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    load_args = {"torch_dtype": dtype, "device_map": {"": device}, "attn_implementation": attn}
    if quantization == "4bit":
        load_args["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype)
    model = AutoModelForCausalLM.from_pretrained(args.model, **load_args)
    if quantization == "4bit":
        model = prepare_model_for_kbit_training(model)
    else:
        # Gradient checkpointing needs grads reaching the inputs; prepare_model_
        # for_kbit_training does this for the 4-bit path.
        model.enable_input_require_grads()
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.05,
        target_modules="all-linear", task_type="CAUSAL_LM"))
    model.print_trainable_parameters()

    def collate(batch):
        width = max(len(row["input_ids"]) for row in batch)
        return {key: torch.tensor([row[key] + [pad] * (width - len(row[key])) for row in batch])
                for key, pad in (("input_ids", tokenizer.pad_token_id), ("attention_mask", 0), ("labels", -100))}

    # transformers 5.x removed warmup_ratio; warmup_steps exists in both, so
    # compute it here rather than pinning the library version.
    steps_per_epoch = max(1, -(-len(datasets["train"]) // (batch_size * grad_accum)))
    total_steps = args.max_steps if args.max_steps > 0 else int(steps_per_epoch * args.epochs)
    warmup_steps = max(1, round(args.warmup_ratio * total_steps))
    report["total_optimizer_steps"] = total_steps
    report["warmup_steps"] = warmup_steps
    print(f"{steps_per_epoch} steps/epoch -> {total_steps} optimizer steps, "
          f"{warmup_steps} warmup", flush=True)

    trainer = Trainer(
        model=model, processing_class=tokenizer, data_collator=collate,
        train_dataset=datasets["train"], eval_dataset=datasets["validation"],
        args=TrainingArguments(
            output_dir=str(args.output_dir), num_train_epochs=args.epochs, max_steps=args.max_steps,
            per_device_train_batch_size=batch_size, per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=grad_accum, learning_rate=args.learning_rate,
            lr_scheduler_type="cosine", warmup_steps=warmup_steps,
            gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
            bf16=dtype == torch.bfloat16, fp16=dtype == torch.float16,
            neftune_noise_alpha=args.neftune or None,
            eval_strategy="epoch", save_strategy="epoch", save_total_limit=2,
            load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
            logging_steps=10, report_to="none", seed=42))
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    trainer.save_model(str(args.output_dir / "adapter"))
    tokenizer.save_pretrained(args.output_dir / "adapter")
    metrics = trainer.evaluate()
    trainer.save_metrics("validation", metrics)
    report["final_validation"] = metrics
    (args.output_dir / "tokenization_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()