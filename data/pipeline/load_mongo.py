"""
Inserts stitched daily documents into MongoDB.

Reads the JSON file run_extract.py wrote (out/state_signals_daily_<date>.json)
and upserts each document into the state_signals_daily collection, keyed on
(state_code, date) so reruns for the same day overwrite rather than duplicate.

Usage:
    python load_mongo.py                       # loads today's file
    python load_mongo.py --date 2026-09-29      # loads a specific day's file
"""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

PIPELINE_DIR = Path(__file__).resolve().parent
# Existing environment and pipeline settings take precedence; backend is fallback.
load_dotenv(PIPELINE_DIR / ".env", override=False)
load_dotenv(PIPELINE_DIR.parents[1] / "src" / "backend" / ".env", override=False)

OUT_DIR = PIPELINE_DIR / "out"
DB_NAME = os.getenv("MONGODB_DB_NAME", "wavelength")
COLLECTION_NAME = "state_signals_daily"


def load_file(json_path: Path) -> int:
    mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("Set MONGODB_URI in src/backend/.env or data/pipeline/.env (legacy MONGO_URI is also supported)")

    with open(json_path) as f:
        docs = json.load(f)

    client = MongoClient(mongo_uri)
    collection = client[DB_NAME][COLLECTION_NAME]

    upserted = 0
    for doc in docs:
        collection.replace_one(
            {"state_code": doc["state_code"], "date": doc["date"]},
            doc,
            upsert=True,
        )
        upserted += 1

    client.close()
    return upserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    args = parser.parse_args()

    date_str = args.date or __import__("datetime").date.today().isoformat()
    json_path = OUT_DIR / f"state_signals_daily_{date_str}.json"

    if not json_path.exists():
        raise FileNotFoundError(f"No output file found at {json_path} -- run run_extract.py first.")

    count = load_file(json_path)
    print(f"Upserted {count} documents into {DB_NAME}.{COLLECTION_NAME} from {json_path.name}")


if __name__ == "__main__":
    main()