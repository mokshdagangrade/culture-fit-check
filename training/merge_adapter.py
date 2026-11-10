"""Merge a trained LoRA adapter into the base weights for serving.

vLLM can serve an adapter without merging, but a merged model is what you
need to convert to GGUF for llama.cpp/Ollama, and it removes the adapter as a
moving part at demo time.

    python training/merge_adapter.py \\
        --adapter training/checkpoints/brand-qwen/adapter \\
        --output  training/checkpoints/brand-qwen/merged

Runs on CPU if no GPU is free (slower, needs ~16 GB RAM for a 4B). If the
adapter was trained with --quantization 4bit, merging into bf16 weights is
standard and slightly lossy; the alternative is serving base+adapter in vLLM,
which keeps the 4-bit training path exact but cannot be converted to GGUF.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", help="defaults to the base recorded in the adapter config")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--dtype", choices=["bfloat16", "float16"], default="bfloat16")
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    config = json.loads((args.adapter / "adapter_config.json").read_text())
    base = args.base or config.get("base_model_name_or_path")
    if not base:
        raise SystemExit("Could not determine the base model; pass --base")

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = getattr(torch, args.dtype)
    if device == "cpu" and dtype is torch.bfloat16:
        print("note: bf16 on CPU is slow; this is a one-off merge, not inference")

    print(f"base    : {base}")
    print(f"adapter : {args.adapter}")
    print(f"device  : {device} ({args.dtype})")

    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=dtype, device_map={"": device}, low_cpu_mem_usage=True)
    model = PeftModel.from_pretrained(model, str(args.adapter))
    model = model.merge_and_unload()
    model.config.use_cache = True

    args.output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.output, safe_serialization=True)
    # Prefer the adapter's tokenizer: training saved it there, so it is the one
    # whose chat template produced the training prefixes.
    try:
        tokenizer = AutoTokenizer.from_pretrained(args.adapter)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(base)
    tokenizer.save_pretrained(args.output)

    (args.output / "merge_info.json").write_text(json.dumps({
        "base_model": base, "adapter": str(args.adapter), "dtype": args.dtype,
        "lora_r": config.get("r"), "lora_alpha": config.get("lora_alpha"),
        "target_modules": config.get("target_modules"),
    }, indent=2, default=str) + "\n")

    size = sum(f.stat().st_size for f in args.output.glob("*.safetensors")) / 1024 ** 3
    print(f"\nmerged -> {args.output}  ({size:.1f} GiB)")
    print("\nServe it:")
    print(f"  vllm serve {args.output} --host 0.0.0.0 --port 8000 --max-model-len 4096")
    print("\nOr convert for llama.cpp / Ollama:")
    print(f"  python llama.cpp/convert_hf_to_gguf.py {args.output} --outfile wavelength.gguf --outtype f16")
    print("  llama.cpp/llama-quantize wavelength.gguf wavelength-q4.gguf Q4_K_M")


if __name__ == "__main__":
    main()