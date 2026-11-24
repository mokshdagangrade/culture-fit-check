"""Validate fictional fixtures, then upsert only the shared brand_presets collection.

Run with --dry-run first. This command never creates accounts or changes user profiles.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from models import ProfileUpdate

DEFAULT_FILE = Path(__file__).resolve().parents[2] / 'data' / 'fixtures' / 'brand_presets.json'
PROFILE_FIELDS = {'business_name', 'industry', 'tone', 'description', 'target_audience',
                  'products', 'states', 'past_taglines', 'brand_details'}


def read_presets(path):
    payload = json.loads(Path(path).read_text())
    if payload.get('schema_version') != 1 or not isinstance(payload.get('brands'), list) or not payload['brands']:
        raise ValueError('Expected schema_version 1 and a nonempty brands list.')
    records, seen = [], set()
    for brand in payload['brands']:
        preset_id = brand.get('id', '')
        if not isinstance(preset_id, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', preset_id) or preset_id in seen:
            raise ValueError('Preset IDs must be unique lowercase slugs.')
        seen.add(preset_id)
        if brand.get('is_fictional') is not True:
            raise ValueError(f'{preset_id}: preset must be explicitly fictional.')
        profile = brand.get('profile', {})
        if not isinstance(profile, dict) or set(profile) - PROFILE_FIELDS:
            raise ValueError(f'{preset_id}: unsupported profile fields.')
        parsed = ProfileUpdate.model_validate(profile).model_dump(exclude_none=True)
        for key in PROFILE_FIELDS - {'brand_details'}:
            if not parsed.get(key):
                raise ValueError(f'{preset_id}: missing {key}.')
        for key in ('label', 'summary'):
            if not isinstance(brand.get(key), str) or not brand[key].strip():
                raise ValueError(f'{preset_id}: missing {key}.')
        briefs = brand.get('suggested_test_briefs', [])
        if not isinstance(briefs, list) or not all(isinstance(b, str) and 0 < len(b) <= 4000 for b in briefs):
            raise ValueError(f'{preset_id}: invalid test briefs.')
        records.append({'preset_id': preset_id, 'label': brand['label'], 'summary': brand['summary'],
                        'is_fictional': True, 'profile': parsed, 'suggested_test_briefs': briefs,
                        'schema_version': 1})
    return records


def upsert_presets(collection, records):
    collection.create_index('preset_id', unique=True)
    now = datetime.now(timezone.utc)
    for record in records:
        collection.update_one({'preset_id': record['preset_id']},
                              {'$set': {**record, 'updated_at': now}, '$setOnInsert': {'created_at': now}}, upsert=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=DEFAULT_FILE)
    parser.add_argument('--dry-run', action='store_true', help='Validate and list presets without connecting to MongoDB')
    args = parser.parse_args()
    records = read_presets(args.file)
    if args.dry_run:
        print('Validated presets: ' + ', '.join(r['preset_id'] for r in records))
        return
    from dotenv import load_dotenv
    from pymongo import MongoClient
    load_dotenv(Path(__file__).resolve().parent / '.env')
    client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'), serverSelectionTimeoutMS=5000)
    try:
        database = client[os.getenv('MONGODB_DB_NAME', 'wavelength')]
        upsert_presets(database['brand_presets'], records)
    finally:
        client.close()
    print(f'Imported {len(records)} brand presets. Refresh Brand settings to see them. User profiles were not changed.')


if __name__ == '__main__':
    main()
