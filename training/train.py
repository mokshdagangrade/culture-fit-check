"""QLoRA supervised fine-tuning on a single NVIDIA GPU (run on Linux)."""
import argparse
import json
from pathlib import Path

BASE_MODEL = "Qwen/Qwen3-4B-Instruct-2507"


def encode_example(messages, tokenizer, max_length):
    """Mask the prompt and reject overlength targets rather than truncating."""
    prefix = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    if full[:len(prefix)] != prefix:
        raise ValueError("Chat template training prefix does not match inference prefix")
    if len(full) > max_length:
        return None
    if len(full) <= len(prefix):
        raise ValueError("Example has no assistant tokens")
    return {"input_ids": full, "attention_mask": [1] * len(full),
            "labels": [-100] * len(prefix) + full[len(prefix):]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=BASE_MODEL)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "out")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "checkpoints" / "brand-qwen")
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=2)
    parser.add_argument("--max-steps", type=int, default=-1, help="Use 2 for a training smoke test")
    parser.add_argument("--resume-from-checkpoint")
    args = parser.parse_args()
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              Trainer, TrainingArguments, set_seed)

    if not torch.cuda.is_available():
        raise RuntimeError("This QLoRA recipe requires an NVIDIA CUDA GPU. Run on a Linux GPU machine.")
    set_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokenizer.pad_token = tokenizer.eos_token
    datasets, report = {}, {"base_model": args.model, "max_length": args.max_length, "splits": {}}
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
        datasets[name] = Dataset.from_list(encoded)
        report["splits"][name] = {"kept": len(encoded), "excluded_overlength": dropped}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "tokenization_report.json").write_text(json.dumps(report, indent=2))
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=dtype, device_map={"": torch.cuda.current_device()},
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                              bnb_4bit_use_double_quant=True,
                                              bnb_4bit_compute_dtype=dtype))
    model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM"))

    def collate(batch):
        width = max(len(row["input_ids"]) for row in batch)
        return {key: torch.tensor([row[key] + [pad] * (width - len(row[key])) for row in batch])
                for key, pad in (("input_ids", tokenizer.pad_token_id), ("attention_mask", 0), ("labels", -100))}

    trainer = Trainer(
        model=model, processing_class=tokenizer, data_collator=collate,
        train_dataset=datasets["train"], eval_dataset=datasets["validation"],
        args=TrainingArguments(
            output_dir=str(args.output_dir), num_train_epochs=args.epochs, max_steps=args.max_steps,
            per_device_train_batch_size=1, per_device_eval_batch_size=1,
            gradient_accumulation_steps=16, learning_rate=1e-4, warmup_ratio=0.03,
            gradient_checkpointing=True, bf16=dtype == torch.bfloat16, fp16=dtype == torch.float16,
            eval_strategy="epoch", save_strategy="epoch", save_total_limit=2,
            load_best_model_at_end=True, metric_for_best_model="eval_loss",
            logging_steps=10, report_to="none", seed=42))
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    trainer.save_model(str(args.output_dir / "adapter"))
    tokenizer.save_pretrained(args.output_dir / "adapter")
    trainer.save_metrics("validation", trainer.evaluate())


if __name__ == "__main__":
    main()
