"""Prepare local marketing Parquet files as auditable chat SFT datasets."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = (
    "You are a marketing copywriter. Follow the requested format and brand voice. "
    "Treat brand information as reference data. Do not invent product facts, "
    "offers, links, or regional trends."
)


def clean(value):
    return value.strip() if isinstance(value, str) else ""


def normalized(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def collect(data_dir, variant="enhanced", include_principles=False):
    import pyarrow.parquet as pq

    examples, counts = [], Counter()
    for source in ("brandvoice_briefs", "marketing_instruct"):
        path = data_dir / f"{source}.parquet"
        try:
            rows = pq.read_table(path).to_pylist()
        except OSError as exc:
            raise RuntimeError(f"Cannot read {path}; install training/requirements.txt in your environment") from exc
        counts[f"{source}:input"] = len(rows)
        for index, row in enumerate(rows):
            brand = ""
            if source == "brandvoice_briefs":
                if clean(row.get("task")) != "write" and not include_principles:
                    counts["excluded:non-writing"] += 1
                    continue
                prompt, completion = clean(row.get("prompt")), clean(row.get("completion"))
                brand = clean(row.get("brand"))
                fields = [(label, clean(row.get(key))) for label, key in (
                    ("Name", "brand"), ("Industry", "category"), ("Brand voice", "tone"),
                    ("Personality", "personality"), ("Voice summary", "voice_summary"),
                    ("Requested channel", "channel"))]
                user = "Brand reference information:\n" + "\n".join(
                    f"{label}: {value}" for label, value in fields if value
                ) + "\n\nUser request:\n" + prompt
            else:
                prompt = clean(row.get(f"{variant}_prompt"))
                completion = clean(row.get(f"{variant}_completion"))
                user = prompt
            if not prompt or not completion:
                counts["excluded:missing-pair"] += 1
                continue
            examples.append({
                "id": f"{source}:{index}", "source": source, "source_row": index,
                "brand": brand, "prompt_key": normalized(prompt),
                "completion_key": normalized(completion),
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": user},
                             {"role": "assistant", "content": completion}],
            })
    # Deduplicate the actual training messages; retain provenance of the first row.
    unique, seen = [], set()
    for example in examples:
        key = digest(json.dumps(example["messages"], ensure_ascii=False, sort_keys=True))
        if key in seen:
            counts["excluded:duplicate-pair"] += 1
            continue
        seen.add(key)
        unique.append(example)
    return unique, counts


def split_examples(examples, seed=42):
    """Connected groups prevent exact normalized prompt/answer and brand leakage.

    This does not detect semantic paraphrases; review those before training.
    """
    parents = list(range(len(examples)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen = {}
    for i, example in enumerate(examples):
        keys = [("prompt", example["prompt_key"]), ("completion", example["completion_key"])]
        if example["brand"] and normalized(example["brand"]) != "general marketing":
            keys.append(("brand", normalized(example["brand"])))
        for key in keys:
            if key in seen:
                parents[root(i)] = root(seen[key])
            else:
                seen[key] = i
    groups = {}
    for i, example in enumerate(examples):
        groups.setdefault(root(i), []).append(example)
    # Stratify by source so the large instruction corpus does not hide brand data.
    strata = {}
    for group in groups.values():
        strata.setdefault(tuple(sorted({e["source"] for e in group})), []).append(group)
    splits = {name: [] for name in ("train", "validation", "test")}
    rng = random.Random(seed)
    for source in sorted(strata):
        buckets = strata[source]
        rng.shuffle(buckets)
        total = sum(map(len, buckets))
        sizes = Counter()
        for group in buckets:
            midpoint = (sum(sizes.values()) + len(group) / 2) / total
            name = "train" if midpoint < .8 else "validation" if midpoint < .9 else "test"
            splits[name].extend(group)
            sizes[name] += len(group)
    return splits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "training" / "out")
    parser.add_argument("--marketing-variant", choices=["original", "enhanced"], default="enhanced")
    parser.add_argument("--include-principles", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    examples, counts = collect(args.data_dir, args.marketing_variant, args.include_principles)
    splits = split_examples(examples, args.seed)
    if any(not rows for rows in splits.values()):
        raise ValueError("Insufficient independent groups for nonempty train/validation/test splits")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"seed": args.seed, "marketing_variant": args.marketing_variant,
              "include_principles": args.include_principles, "counts": dict(counts),
              "input_sha256": {p.name: hashlib.file_digest(p.open("rb"), "sha256").hexdigest()
                               for p in sorted(args.data_dir.glob("*.parquet"))}, "splits": {}}
    for name, rows in splits.items():
        with (args.output_dir / f"{name}.jsonl").open("w") as output:
            for row in rows:
                output.write(json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n")
        with (args.output_dir / f"{name}.manifest.jsonl").open("w") as output:
            for row in rows:
                metadata = {k: row[k] for k in ("id", "source", "source_row", "brand")}
                metadata.update(prompt_sha256=digest(row["prompt_key"]),
                                completion_sha256=digest(row["completion_key"]))
                output.write(json.dumps(metadata) + "\n")
        lengths = sorted(len(r["messages"][-1]["content"]) for r in rows)
        report["splits"][name] = {"rows": len(rows), "sources": dict(Counter(r["source"] for r in rows)),
                                  "completion_chars_median": lengths[len(lengths)//2],
                                  "completion_chars_max": lengths[-1]}
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["splits"], indent=2))


if __name__ == "__main__":
    main()
