#!/usr/bin/env python3
"""Label VOZ posts with stress aspects using Qwen via Ollama."""

import json
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

ASPECTS = [
    {"id": 0, "name": "occupational", "vi": "Công việc"},
    {"id": 1, "name": "self_image", "vi": "Hình ảnh bản thân"},
    {"id": 2, "name": "health", "vi": "Sức khỏe"},
    {"id": 3, "name": "academic", "vi": "Học tập"},
    {"id": 4, "name": "romantic", "vi": "Tình cảm"},
    {"id": 5, "name": "familial", "vi": "Gia đình"},
    {"id": 6, "name": "financial", "vi": "Tài chính"},
    {"id": 7, "name": "life_events", "vi": "Sự kiện"},
    {"id": 8, "name": "existential", "vi": "Hiện sinh"},
]

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích stress trong văn bản tiếng Việt.

Phân loại bài viết theo các khía cạnh stress sau:
0: Công việc (Occupational) - áp lực công việc, sự nghiệp
1: Hình ảnh bản thân (Self Image) - tự ti, ngoại hình, bản sắc
2: Sức khỏe (Health) - lo lắng sức khỏe thể chất và tinh thần
3: Học tập (Academic) - áp lực học hành, thi cử
4: Tình cảm (Romantic) - tình yêu, hẹn hò, chia tay
5: Gia đình (Familial) - mâu thuẫn gia đình, áp lực từ cha mẹ
6: Tài chính (Financial) - tiền bạc, nợ nần, kinh tế khó khăn
7: Sự kiện (Life Events) - sự kiện lớn, mất mát, chấn thương
8: Hiện sinh (Existential) - ý nghĩa cuộc sống, cô đơn, tương lai

Trả lời CHÍNH XÁC theo format JSON (không giải thích thêm):
{"aspects": [danh sách ID số nguyên], "confidence": 0.0-1.0, "reasoning": "giải thích ngắn gọn"}

Nếu không có dấu hiệu stress, trả về: {"aspects": [], "confidence": 0.9, "reasoning": "Không phát hiện stress"}"""

def call_ollama(text: str, model: str = "qwen3:8b", max_retries: int = 3) -> dict:
    """Call Ollama Chat API to label a post."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Phân tích bài viết sau:\n\n{text[:1500]}"}
    ]

    for attempt in range(max_retries):
        try:
            response = requests.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 300},
                    "think": False  # Disable thinking for Qwen3
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            output = result.get("message", {}).get("content", "")

            # Parse JSON from response
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = output[json_start:json_end]
                parsed = json.loads(json_str)
                return {
                    "aspects": parsed.get("aspects", []),
                    "confidence": parsed.get("confidence", 0.5),
                    "reasoning": parsed.get("reasoning", "")
                }
        except (requests.RequestException, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {"aspects": [], "confidence": 0.0, "reasoning": f"Error: {str(e)}"}

    return {"aspects": [], "confidence": 0.0, "reasoning": "Max retries exceeded"}

def label_dataset(input_path: str, output_path: str, model: str = "qwen3:8b",
                  batch_size: int = 10, resume: bool = True):
    """Label entire dataset with Qwen."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Load already processed IDs if resuming
    processed_ids = set()
    if resume and Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    processed_ids.add(record.get("post_id"))
                except json.JSONDecodeError:
                    continue
        print(f"Resuming: {len(processed_ids)} already processed")

    # Process posts
    total = 0
    labeled = 0
    mode = "a" if resume and processed_ids else "w"

    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, mode, encoding="utf-8") as fout:

        batch = []
        for line in fin:
            total += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            post_id = record.get("post_id")
            if post_id in processed_ids:
                continue

            batch.append(record)

            if len(batch) >= batch_size:
                for rec in batch:
                    result = call_ollama(rec["text"], model)
                    output_record = {
                        "post_id": rec["post_id"],
                        "text": rec["text"],
                        "aspects": result["aspects"],
                        "confidence": result["confidence"],
                        "reasoning": result["reasoning"],
                        "model": model,
                        "labeled_at": datetime.now(timezone.utc).isoformat()
                    }
                    fout.write(json.dumps(output_record, ensure_ascii=False) + "\n")
                    fout.flush()
                    labeled += 1

                print(f"Labeled {labeled}/{total} posts...")
                batch = []

        # Process remaining
        for rec in batch:
            result = call_ollama(rec["text"], model)
            output_record = {
                "post_id": rec["post_id"],
                "text": rec["text"],
                "aspects": result["aspects"],
                "confidence": result["confidence"],
                "reasoning": result["reasoning"],
                "model": model,
                "labeled_at": datetime.now(timezone.utc).isoformat()
            }
            fout.write(json.dumps(output_record, ensure_ascii=False) + "\n")
            labeled += 1

    print(f"\nLabeling complete: {labeled} posts labeled")
    return labeled

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label VOZ posts with Qwen")
    parser.add_argument("--input", "-i", default="data/cleaned/voz_cleaned.jsonl")
    parser.add_argument("--output", "-o", default="data/labeled/qwen_labels.jsonl")
    parser.add_argument("--model", "-m", default="qwen3:8b")
    parser.add_argument("--batch-size", "-b", type=int, default=10)
    parser.add_argument("--no-resume", action="store_true", help="Start fresh")
    args = parser.parse_args()

    label_dataset(args.input, args.output, args.model, args.batch_size, not args.no_resume)
