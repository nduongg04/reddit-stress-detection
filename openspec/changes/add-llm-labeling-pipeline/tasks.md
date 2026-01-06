# Tasks: LLM Labeling Pipeline

## Prerequisites
- [x] Sprint 2 complete: `data/cleaned/voz_posts_cleaned_v1.jsonl` exists with ~10,000 posts
- [x] Sprint 2 complete: `config/aspects_v1.json` and `config/aspects_v1.sha256` exist
- [x] Ollama installed and running (`ollama serve`)

---

## 1. Ollama Model Setup

### 1.1 Install and Verify Models
- [x] Pull llama3.1:8b: `ollama pull llama3.1:8b` (4.9GB)
- [x] Pull gemma2:9b: `ollama pull gemma2:9b` (5.4GB)
- [x] Pull llama3.2:1b: `ollama pull llama3.2:1b` (smaller alternative for 24GB RAM)
- [x] Verify all models respond: `ollama run <model> "test"`
- [x] Verify HTTP API works: `curl http://localhost:11434/api/tags`

**Note:** Changed from mixtral:8x7b (26GB) to llama3.2:1b due to 24GB RAM constraint.

---

## 2. Prompt Template

### 2.1 Create Frozen Prompt
- [x] Create `config/prompt_v1.txt` with:
  - System instructions for Vietnamese stress aspect classification
  - All 10 aspect definitions (IDs, names, definitions from `aspects_v1.json`)
  - Output JSON schema: `{"aspects": [0,2,5], "reasoning": "..."}`
  - Examples of correct classification
- [x] Compute SHA-256 hash and save to `config/prompt_v1.sha256`

---

## 3. Labeling Script Implementation

### 3.1 Core Structure
- [x] Create `scripts/llm_labeling.py`
- [x] Add argument parsing: `--input`, `--output`, `--batch-size`, `--limit`, `--models`
- [x] Load and validate prompt template (check SHA-256)
- [x] Load and validate aspect schema (check SHA-256)
- [x] Load cleaned posts from input JSONL

### 3.2 Model Execution
- [x] Implement Ollama HTTP client (POST to `/api/generate`)
- [x] Implement model loading/unloading via Ollama API
- [x] Implement sequential execution loop:
  1. Load llama3.1:8b → process all posts → store results
  2. Unload → load gemma2:9b → process all → store
  3. Unload → load llama3.2:1b → process all → store

### 3.3 Request Handling
- [x] Implement 60-second timeout per request
- [x] Implement retry logic (max 2 retries per request)
- [x] Parse JSON response, validate `aspects` and `reasoning` fields
- [x] Handle non-JSON and malformed responses

### 3.4 Failure Handling
- [x] Track failed requests per model per post
- [x] Implement fallback: use 2-vote if 1 model fails
- [x] Implement discard: exclude post if 2+ models fail
- [x] Log all failures to `logs/invalid_outputs.jsonl`

### 3.5 Output Generation
- [x] Create `data/labeled/` directory if not exists
- [x] Create `logs/` directory if not exists
- [x] Write valid results to `data/labeled/llm_outputs_v1.jsonl`
- [x] Include all 3 model outputs per post (or 2 if fallback)

### 3.6 Progress Logging
- [x] Log progress every 100 posts
- [x] Log model switch events
- [x] Log completion summary with counts

---

## 4. Validation

### 4.1 Prompt Validation
- [x] Verify `config/prompt_v1.txt` exists
- [x] Verify SHA-256 hash matches `config/prompt_v1.sha256`
- [x] Verify prompt includes all 10 aspect definitions

### 4.2 Output Validation
- [x] Verify `data/labeled/llm_outputs_v1.jsonl` is valid JSONL
- [x] Verify each record has `post_id`, `text`, `model_outputs`
- [x] Verify `aspects` arrays contain valid IDs (0-9)
- [x] Count posts with all 3 models vs 2-vote fallback vs discarded

### 4.3 Error Log Validation
- [x] Verify `logs/invalid_outputs.jsonl` exists (may be empty)
- [x] Verify each error record has required fields

---

## Deliverables

| File | Description | Status |
|------|-------------|--------|
| `scripts/llm_labeling.py` | Main labeling script | Created |
| `config/prompt_v1.txt` | Frozen prompt template | Created |
| `config/prompt_v1.sha256` | Prompt integrity hash | Created |
| `data/labeled/llm_outputs_v1.jsonl` | Labeled posts output | Created (test) |
| `logs/invalid_outputs.jsonl` | Invalid output log | Created |

---

## Test Results (3 posts sample)

```
Input posts: 3
Full success (3 models): 1
Fallback (2 models): 2
Discarded (<2 models): 0
```

---

## Notes

- Run with: `python scripts/llm_labeling.py`
- Test with limit: `python scripts/llm_labeling.py --limit 10`
- Custom models: `python scripts/llm_labeling.py --models "llama3.1:8b,gemma2:9b,llama3.2:1b"`
- Monitor GPU memory during execution
- Keep Ollama running throughout: `ollama serve`
