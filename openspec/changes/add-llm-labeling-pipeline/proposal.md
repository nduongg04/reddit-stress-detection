# Change: Add LLM Labeling Pipeline

## Why
Sprint 3 implements multi-label stress aspect classification using a 3-model ensemble via Ollama. The cleaned posts from Sprint 2 (10,460 posts) need automated labeling before PhoBERT training. An ensemble approach with voting reduces single-model bias and improves label quality.

## What Changes
- Add 3-model LLM ensemble labeling using Ollama (llama3.1:8b, mixtral:8x7b, gemma2:9b)
- Create frozen prompt template with aspect definitions and JSON output schema
- Implement sequential model execution (one model at a time to fit 24GB VRAM)
- Add retry logic (max 2 attempts, 60s timeout) and fallback handling
- Log invalid outputs for debugging and quality monitoring

## Impact
- Affected specs: `llm-labeling` (new)
- Affected code: `scripts/llm_labeling.py`, `config/prompt_v1.txt`
- Requires: Sprint 2 outputs (`data/cleaned/voz_posts_cleaned_v1.jsonl`, `config/aspects_v1.json`)
- Output: `data/labeled/llm_outputs_v1.jsonl`

## Dependencies
- **Sprint 2**: Cleaned posts and aspect schema must exist
- **Ollama**: Must be installed with all 3 models pulled
- **Hardware**: 24GB+ VRAM recommended (sequential execution enables 8GB minimum)
