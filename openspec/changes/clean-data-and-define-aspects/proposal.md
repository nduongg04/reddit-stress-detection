# Change: Clean Data and Define Stress Aspects

## Why
Sprint 2 combines two parallel workstreams: data cleaning/deduplication and stress aspect schema definition. Raw VOZ.vn posts need token filtering and duplicate removal before LLM labeling. A versioned aspect taxonomy is required to ensure consistent labeling across the pipeline.

## What Changes
- Add data cleaning pipeline with token length filtering (20-300 tokens)
- Add semantic deduplication using MiniLM embeddings (cosine similarity ≥0.90)
- Create versioned stress aspect schema (10 aspects with rules, keywords, examples)
- Generate cleaning statistics report for auditability

## Impact
- Affected specs: `data-cleaning` (new), `aspect-schema` (new)
- Affected code: `scripts/data_cleaning.py`, `config/aspects_v1.json`
- Input: `data/raw/voz_posts_v1.jsonl` (from Sprint 1)
- Output: `data/cleaned/voz_posts_cleaned_v1.jsonl`, `config/aspects_v1.json`
