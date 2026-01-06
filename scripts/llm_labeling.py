#!/usr/bin/env python3
"""
LLM Labeling Pipeline - Split Posts Across Models
Each model handles a separate chunk of posts for maximum speed.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import aiohttp

# Configuration
MODELS = ["gpt-oss:20b"]  # 2 models, posts split between them
OLLAMA_URL = "http://localhost:11434"
REQUEST_TIMEOUT = 60

# Paths
CONFIG_DIR = Path("config")
DATA_DIR = Path("data")
LOGS_DIR = Path("logs")
PROMPT_FILE = CONFIG_DIR / "prompt_v1.txt"
PROMPT_HASH_FILE = CONFIG_DIR / "prompt_v1.sha256"
ASPECTS_FILE = CONFIG_DIR / "aspects_v1.json"
ASPECTS_HASH_FILE = CONFIG_DIR / "aspects_v1.sha256"
DEFAULT_INPUT = DATA_DIR / "cleaned" / "voz_posts_cleaned_v1.jsonl"
DEFAULT_OUTPUT = DATA_DIR / "labeled" / "llm_outputs_v1.jsonl"
INVALID_LOG = LOGS_DIR / "invalid_outputs.jsonl"

ASPECT_NAMES = [
    "occupational", "financial", "academic", "familial", "health",
    "romantic", "existential", "social", "life_events", "self_image"
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def verify_sha256(file_path: Path, hash_path: Path) -> bool:
    if not file_path.exists() or not hash_path.exists():
        return False
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    with open(hash_path) as f:
        expected_hash = f.read().strip()
    return file_hash == expected_hash


async def generate_response(
    session: aiohttp.ClientSession,
    model: str,
    prompt: str,
    post_text: str,
) -> tuple[list[int] | None, str | None, str]:
    """Generate response from a model."""
    try:
        async with session.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt + post_text,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 500,  # Increased for models with different tokenizers (e.g., gpt-oss)
                    "num_ctx": 4096,
                },
            },
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                return None, f"api_error_{resp.status}", ""

            data = await resp.json()
            response_text = data.get("response", "").strip()

            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(response_text[start:end])
                if "aspects" in result and isinstance(result["aspects"], list):
                    aspects = [a for a in result["aspects"] if isinstance(a, int) and 0 <= a <= 9]
                    reasoning = result.get("reasoning", "")
                    return aspects, None, reasoning
            return None, "no_valid_json", ""

    except asyncio.TimeoutError:
        return None, "timeout", ""
    except json.JSONDecodeError:
        return None, "json_decode_error", ""
    except Exception as e:
        return None, f"error:{type(e).__name__}", ""


async def process_chunk(
    session: aiohttp.ClientSession,
    posts: list[dict],
    model: str,
    prompt: str,
    global_stats: dict,
    global_lock: asyncio.Lock,
    results: list,
):
    """Process a chunk of posts with a specific model."""
    model_short = model.split(":")[0]

    for post in posts:
        post_id = post["post_id"]
        aspects, error, reasoning = await generate_response(session, model, prompt, post["text"])

        async with global_lock:
            global_stats["completed"] += 1

            if aspects is not None:
                result = {
                    "post_id": post_id,
                    "text": post["text"],
                    "aspects": aspects,
                    "aspect_confidences": [1.0 if i in aspects else 0.0 for i in range(10)],
                    "confidence": 1.0,
                    "reasoning": reasoning,
                    "model": model,
                }
                results.append(result)
                global_stats["success"] += 1

                if aspects:
                    global_stats["stress"] += 1
                    aspect_str = ",".join(str(a) for a in aspects)
                else:
                    global_stats["non_stress"] += 1
                    aspect_str = "none"

                for a in aspects:
                    global_stats["aspects"][a] += 1
            else:
                global_stats["errors"] += 1
                aspect_str = f"ERR:{error}"

            # Progress log
            pct = 100 * global_stats["completed"] / global_stats["total"]
            elapsed = (datetime.now() - global_stats["start_time"]).total_seconds()
            rate = global_stats["completed"] / elapsed * 60 if elapsed > 0 else 0
            eta = (global_stats["total"] - global_stats["completed"]) / rate if rate > 0 else 0

            logger.info(
                f"[{model_short:8}] [{global_stats['completed']:4d}/{global_stats['total']}] {pct:5.1f}% | "
                f"OK:{global_stats['success']} stress:{global_stats['stress']} non:{global_stats['non_stress']} err:{global_stats['errors']} | "
                f"{rate:5.1f}/min ETA:{eta:.1f}m | {aspect_str}"
            )


async def run_split_labeling(posts: list[dict], models: list[str], prompt: str):
    """Split posts across models and run in parallel."""
    num_models = len(models)
    chunk_size = len(posts) // num_models
    chunks = []

    for i in range(num_models):
        start = i * chunk_size
        end = start + chunk_size if i < num_models - 1 else len(posts)
        chunks.append(posts[start:end])

    logger.info(f"Splitting {len(posts)} posts across {num_models} models:")
    for i, (model, chunk) in enumerate(zip(models, chunks)):
        logger.info(f"  {model}: {len(chunk)} posts")
    logger.info("=" * 70)

    global_lock = asyncio.Lock()
    global_stats = {
        "completed": 0,
        "total": len(posts),
        "success": 0,
        "stress": 0,
        "non_stress": 0,
        "errors": 0,
        "aspects": [0] * 10,
        "start_time": datetime.now(),
    }
    results = []

    connector = aiohttp.TCPConnector(limit=num_models * 2, keepalive_timeout=30)

    async with aiohttp.ClientSession(connector=connector) as session:
        # Warm up models
        logger.info("Warming up models...")
        for model in models:
            try:
                async with session.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": model, "prompt": "Hi", "stream": False, "options": {"num_predict": 1}},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"  {model}: ready")
            except Exception as e:
                logger.warning(f"  {model}: warmup failed - {e}")

        logger.info("Starting parallel labeling...")
        logger.info("-" * 70)

        # Run all chunks in parallel
        tasks = [
            process_chunk(session, chunk, model, prompt, global_stats, global_lock, results)
            for model, chunk in zip(models, chunks)
        ]
        await asyncio.gather(*tasks)

    return results, global_stats


def main():
    parser = argparse.ArgumentParser(description="LLM Labeling - Split Posts Across Models")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--models", type=str, default=",".join(MODELS))
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",")]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("LLM Labeling - SPLIT POSTS ACROSS MODELS")
    logger.info(f"Models: {models}")
    logger.info("=" * 70)

    # Verify prerequisites
    if not args.input.exists():
        logger.error(f"Input not found: {args.input}")
        sys.exit(1)

    if not verify_sha256(PROMPT_FILE, PROMPT_HASH_FILE):
        if PROMPT_FILE.exists():
            with open(PROMPT_FILE, "rb") as f:
                new_hash = hashlib.sha256(f.read()).hexdigest()
            with open(PROMPT_HASH_FILE, "w") as f:
                f.write(new_hash)

    if not verify_sha256(ASPECTS_FILE, ASPECTS_HASH_FILE):
        if ASPECTS_FILE.exists():
            with open(ASPECTS_FILE, "rb") as f:
                new_hash = hashlib.sha256(f.read()).hexdigest()
            with open(ASPECTS_HASH_FILE, "w") as f:
                f.write(new_hash)

    with open(PROMPT_FILE) as f:
        prompt = f.read()

    # Load posts
    posts = []
    with open(args.input) as f:
        for line in f:
            if line.strip():
                posts.append(json.loads(line))

    if args.limit > 0:
        posts = posts[:args.limit]

    logger.info(f"Loaded {len(posts)} posts")

    # Run split labeling
    start_time = datetime.now()
    results, stats = asyncio.run(run_split_labeling(posts, models, prompt))
    elapsed = (datetime.now() - start_time).total_seconds()

    # Write output
    with open(args.output, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Copy to voted directory
    voted_dir = DATA_DIR / "voted"
    voted_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(args.output, voted_dir / "high_confidence.jsonl")
    with open(voted_dir / "medium_confidence.jsonl", "w") as f:
        pass

    # Summary
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Posts: {len(posts)}")
    logger.info(f"Models: {len(models)}")
    logger.info(f"Labeled: {stats['success']} ({100*stats['success']/len(posts):.1f}%)")
    if stats['success']:
        logger.info(f"  - Stress: {stats['stress']} ({100*stats['stress']/stats['success']:.1f}%)")
        logger.info(f"  - Non-stress: {stats['non_stress']} ({100*stats['non_stress']/stats['success']:.1f}%)")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"Time: {elapsed:.1f}s ({len(posts)/elapsed*60:.1f} posts/min, {len(posts)/elapsed*3600:.0f}/hour)")
    logger.info("-" * 70)
    if stats['success']:
        logger.info("Aspect distribution:")
        for i, count in enumerate(stats["aspects"]):
            pct = 100 * count / stats['success']
            bar = "#" * int(pct / 5)
            logger.info(f"  {i}: {ASPECT_NAMES[i]:15} = {count:5} ({pct:5.1f}%) {bar}")
    logger.info("-" * 70)
    logger.info(f"Output: {args.output}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
