"""
Loads the cleaned signal_candidate table into MongoDB for the backend.

The cleaning notebook writes signal_candidate.parquet, but nothing moved it
into Mongo, so the backend could not see it. This closes that gap.

    python data/pipeline/load_candidates.py                  # latest clean day
    python data/pipeline/load_candidates.py --date 2026-10-20

Upserts on signal_id, so re-running a day replaces rather than duplicates.
"""
import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

PIPELINE_DIR = Path(__file__).resolve().parent
load_dotenv(PIPELINE_DIR / ".env", override=False)
load_dotenv(PIPELINE_DIR.parents[1] / "src" / "backend" / ".env", override=False)

CLEAN_DIR = PIPELINE_DIR / "out" / "clean"
DB_NAME = os.getenv("MONGODB_DB_NAME", "wavelength")
COLLECTION_NAME = "signal_candidates"

# Only what the backend reads. Everything else stays in the parquet.
KEEP = ["signal_id", "state_code", "date", "source", "position", "text", "context",
        "is_national", "is_dup", "is_noise", "is_within_window", "is_past",
        "geo_scope", "geo_confidence"]


def find_parquet(date_str: str | None) -> Path:
    """Handles both out/clean/date=YYYY-MM-DD/ and a flat out/clean/."""
    if date_str:
        candidates = [CLEAN_DIR / f"date={date_str}" / "signal_candidate.parquet"]
    else:
        candidates = sorted(CLEAN_DIR.glob("date=*/signal_candidate.parquet"), reverse=True)
    candidates.append(CLEAN_DIR / "signal_candidate.parquet")
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        f"No signal_candidate.parquet under {CLEAN_DIR} -- run the cleaning notebook first.")


def to_documents(df: pd.DataFrame) -> list[dict]:
    frame = df[[c for c in KEEP if c in df.columns]].copy()
    # Mongo and the backend compare dates as ISO strings, as the other
    # collections already do.
    frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
    for flag in ("is_national", "is_dup", "is_noise", "is_within_window", "is_past"):
        if flag in frame:
            frame[flag] = frame[flag].fillna(False).astype(bool)
    frame = frame.where(pd.notna(frame), None)
    return frame.to_dict("records")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD; defaults to the latest clean day")
    args = parser.parse_args()

    mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("Set MONGODB_URI in src/backend/.env or data/pipeline/.env")

    path = find_parquet(args.date)
    docs = to_documents(pd.read_parquet(path))
    if not docs:
        raise SystemExit(f"{path.name} is empty -- nothing to load.")

    client = MongoClient(mongo_uri)
    try:
        collection = client[DB_NAME][COLLECTION_NAME]
        collection.create_index([("state_code", ASCENDING), ("date", ASCENDING)])
        collection.create_index([("is_national", ASCENDING), ("date", ASCENDING)])
        collection.create_index([("signal_id", ASCENDING)], unique=True)
        for doc in docs:
            collection.replace_one({"signal_id": doc["signal_id"]}, doc, upsert=True)
    finally:
        client.close()

    days = sorted({d["date"] for d in docs})
    print(f"Upserted {len(docs)} candidates ({', '.join(days)}) into "
          f"{DB_NAME}.{COLLECTION_NAME} from {path.relative_to(PIPELINE_DIR)}")


if __name__ == "__main__":
    main()