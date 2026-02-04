#!/usr/bin/env python3
"""Clean VOZ posts for training: normalize, filter, deduplicate."""

import json
import re
import argparse
import hashlib
import unicodedata
from datetime import datetime
from pathlib import Path

# Cleaning patterns
HTML_ENTITIES = re.compile(r'&[a-zA-Z]+;|&#\d+;')
URLS = re.compile(r'https?://\S+|www\.\S+')
EMAILS = re.compile(r'\S+@\S+\.\S+')
PHONE_NUMBERS = re.compile(r'(\+84|0)\d{9,10}')
MULTIPLE_SPACES = re.compile(r'\s+')
SPECIAL_CHARS = re.compile(r'[^\w\s.,!?;:\-\'\"àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]')

MIN_LENGTH = 50
MAX_LENGTH = 2000

def normalize_unicode(text: str) -> str:
    """Normalize Vietnamese unicode to NFC form."""
    return unicodedata.normalize('NFC', text)

def clean_text(text: str) -> str:
    """Apply all cleaning transformations."""
    if not text:
        return ""

    # Normalize unicode first
    text = normalize_unicode(text)

    # Remove HTML entities
    text = HTML_ENTITIES.sub(' ', text)

    # Remove URLs
    text = URLS.sub(' ', text)

    # Remove emails
    text = EMAILS.sub(' ', text)

    # Remove phone numbers
    text = PHONE_NUMBERS.sub(' ', text)

    # Remove special characters but keep Vietnamese
    text = SPECIAL_CHARS.sub(' ', text)

    # Collapse multiple whitespace
    text = MULTIPLE_SPACES.sub(' ', text)

    return text.strip()

def compute_hash(text: str) -> str:
    """Compute SHA256 hash of text for deduplication."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

def clean_dataset(input_path: str, output_path: str, stats_path: str = None):
    """Clean entire dataset with filtering and deduplication."""
    seen_hashes = set()
    stats = {
        "total_raw": 0,
        "removed_empty": 0,
        "removed_short": 0,
        "removed_long": 0,
        "removed_duplicates": 0,
        "after_cleaning": 0
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        for line in fin:
            stats["total_raw"] += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            text = record.get("text", "")
            cleaned = clean_text(text)

            # Filter empty
            if not cleaned:
                stats["removed_empty"] += 1
                continue

            # Filter by length
            char_count = len(cleaned)
            if char_count < MIN_LENGTH:
                stats["removed_short"] += 1
                continue
            if char_count > MAX_LENGTH:
                stats["removed_long"] += 1
                continue

            # Deduplicate
            text_hash = compute_hash(cleaned)
            if text_hash in seen_hashes:
                stats["removed_duplicates"] += 1
                continue
            seen_hashes.add(text_hash)

            # Write cleaned record
            output_record = {
                "post_id": record.get("post_id"),
                "text": cleaned,
                "text_hash": text_hash,
                "char_count": char_count,
                "cleaned_at": datetime.utcnow().isoformat() + "Z"
            }
            fout.write(json.dumps(output_record, ensure_ascii=False) + "\n")
            stats["after_cleaning"] += 1

            if stats["after_cleaning"] % 1000 == 0:
                print(f"Cleaned {stats['after_cleaning']} posts...")

    # Save stats
    if stats_path:
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

    print(f"\nCleaning Stats:")
    print(f"  Total raw: {stats['total_raw']}")
    print(f"  Removed empty: {stats['removed_empty']}")
    print(f"  Removed short (<{MIN_LENGTH}): {stats['removed_short']}")
    print(f"  Removed long (>{MAX_LENGTH}): {stats['removed_long']}")
    print(f"  Removed duplicates: {stats['removed_duplicates']}")
    print(f"  After cleaning: {stats['after_cleaning']}")

    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean VOZ posts")
    parser.add_argument("--input", "-i", default="data/raw/voz_exported.jsonl")
    parser.add_argument("--output", "-o", default="data/cleaned/voz_cleaned.jsonl")
    parser.add_argument("--stats", "-s", default="data/cleaned/cleaning_stats.json")
    args = parser.parse_args()

    clean_dataset(args.input, args.output, args.stats)
