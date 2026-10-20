import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
    from datasets import load_dataset
    from huggingface_hub import hf_hub_download
except ImportError as exc:
    print(f"Missing dependency: {exc}")
    print(
        "Install the required packages with:\n"
        "python -m pip install -U datasets huggingface_hub pandas pyarrow"
    )
    sys.exit(1)


MARKETING_INSTRUCT_REPO = "suehuynh/marketing-instruct-8k"
BRANDVOICE_BRIEFS_REPO = "manifesta/brandvoice-marketing-briefs"


PIPELINE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = PIPELINE_DIR / "out"


def write_json(path: Path, data) -> None:
    """Same atomic-write pattern as run_extract.py's write_json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    temporary.replace(path)


def export_dataframe(label: str, df: pd.DataFrame, json_path: Path) -> None:
    records = df.to_dict(orient="records")
    write_json(json_path, records)
    print(f"  Wrote {len(records):,} rows -> {json_path}")


def export_marketing_instruct():
    
    print(f"\nLoading {MARKETING_INSTRUCT_REPO}")
    try:
        dataset = load_dataset(MARKETING_INSTRUCT_REPO, split="train")
    except Exception as exc:
        print(f"marketing_instruct export failed: {exc}")
        print("If the repository requires authentication, run `hf auth login` and retry")
        raise

    df = dataset.to_pandas()
    print(f"  Source rows: {len(df):,}")
    print(f"  Columns: {list(df.columns)}")

    export_dataframe("marketing_instruct", df, OUT_DIR / "marketing_instruct.json")


def export_brandvoice_briefs():
    
    print(f"\nLoading {BRANDVOICE_BRIEFS_REPO}")
    try:
        csv_path = hf_hub_download(
            repo_id=BRANDVOICE_BRIEFS_REPO,
            repo_type="dataset",
            filename="brandvoice_briefs.csv",
        )
    except Exception as exc:
        print(f"brandvoice_briefs export failed: {exc}")
        print("If the repository requires authentication, run `hf auth login` and retry")
        raise

    df = pd.read_csv(csv_path)
    print(f"  Source rows: {len(df):,}")
    print(f"  Columns: {list(df.columns)}")

    if "task" in df.columns:
        print("\n  Task distribution:")
        print(df["task"].value_counts(dropna=False).to_string())

    required = {"brand", "completion"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df[
        df["brand"].notna()
        & df["completion"].notna()
        & df["brand"].astype(str).str.strip().ne("")
        & df["completion"].astype(str).str.strip().ne("")
    ].copy()

    if df.empty:
        raise ValueError("No rows have both a brand and a non-empty completion.")

    unique_brands = df["brand"].nunique()
    export_dataframe("brandvoice_briefs", df, OUT_DIR / "brandvoice_briefs.json")
    print(f"  Unique brands: {unique_brands}")
    if unique_brands != 83:
        print(
            "  NOTE: expected 83 brands per the dataset card -- review the brand distribution above before treating this as the final held-out set."
        )


EXPORTERS = {
    "marketing_instruct": export_marketing_instruct,
    "brandvoice_briefs": export_brandvoice_briefs,
}


def main():
    parser = argparse.ArgumentParser(description="Export the two HF marketing datasets to JSON + Parquet")
    parser.add_argument("--dataset", choices=[*EXPORTERS, "both"], default="both",
                        help="Which dataset to export (default: both).")
    args = parser.parse_args()

    targets = EXPORTERS.values() if args.dataset == "both" else [EXPORTERS[args.dataset]]
    for export in targets:
        export()

    print("\nExport completed")


if __name__ == "__main__":
    main()