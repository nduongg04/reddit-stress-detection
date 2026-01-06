# Design: LLM Labeling Pipeline

## Context
Sprint 3 requires labeling ~10,000 Vietnamese posts with multi-label stress aspects. The 10 aspects from Sprint 2 schema need consistent classification across posts. Using multiple LLMs with voting improves reliability over single-model labeling.

**Constraints:**
- GPU VRAM: Target 24GB, support 8GB with sequential execution
- Throughput target: ~500 posts/hour
- Total runtime: ~20 hours for 10k posts
- Ollama as local LLM runtime (no cloud API costs)

## Goals / Non-Goals

**Goals:**
- Label all cleaned posts with 3-model ensemble
- Produce reproducible outputs with versioned prompts
- Handle model failures gracefully with fallbacks
- Log invalid outputs for debugging

**Non-Goals:**
- Real-time labeling (batch processing is acceptable)
- Model fine-tuning (use off-the-shelf models)
- Cloud LLM integration (Ollama only)

## Decisions

### Decision 1: Sequential Model Execution
**What:** Load one model at a time, process all posts, unload, then load next model.

**Why:**
- mixtral:8x7b requires 26GB VRAM if loaded alone
- Sequential execution allows any single GPU ≥8GB to run the pipeline
- Avoids OOM errors from concurrent model loading

**Alternatives considered:**
- Parallel execution: Faster but requires 48GB+ VRAM
- Model quantization: Reduces quality, not worth the complexity

### Decision 2: Three-Model Ensemble
**What:** Use llama3.1:8b, mixtral:8x7b, gemma2:9b for voting.

**Why:**
- Model diversity reduces single-model bias
- All models support Vietnamese text understanding
- Mixtral (MoE) provides different architectural perspective
- 2-of-3 voting enables robust consensus

**Model sizes:**
| Model | VRAM | Notes |
|-------|------|-------|
| llama3.1:8b | 4.9GB | Fast, good baseline |
| mixtral:8x7b | 26GB | MoE architecture, diverse |
| gemma2:9b | 5.4GB | Google's multilingual |

### Decision 3: Structured JSON Output
**What:** Require strict JSON format: `{"aspects": [0,2,5], "reasoning": "..."}`

**Why:**
- Machine-parseable without post-processing
- Reasoning field enables debugging and quality review
- Aspect IDs match Sprint 2 schema (0-9)

### Decision 4: Retry with Fallback
**What:** Max 2 retries per request, 60s timeout. If 1 model fails → use 2 votes. If 2+ fail → discard post.

**Why:**
- Network/timeout errors are transient, worth retrying
- 60s timeout prevents infinite hangs
- 2-vote fallback maintains some confidence
- Discarding 2+ failure posts avoids low-quality labels

## Data Flow

```
data/cleaned/voz_posts_cleaned_v1.jsonl (10,460 posts)
              │
              ▼
┌─────────────────────────────────────────┐
│         scripts/llm_labeling.py         │
│  ┌─────────────────────────────────┐    │
│  │  Load config/prompt_v1.txt      │    │
│  │  Load config/aspects_v1.json    │    │
│  └─────────────────────────────────┘    │
│              │                          │
│  ┌───────────▼────────────────────┐     │
│  │  Sequential Model Execution    │     │
│  │  ┌───────────────────────────┐ │     │
│  │  │ 1. llama3.1:8b → all posts│ │     │
│  │  │ 2. Unload, load mixtral   │ │     │
│  │  │ 3. mixtral:8x7b → all     │ │     │
│  │  │ 4. Unload, load gemma2    │ │     │
│  │  │ 5. gemma2:9b → all posts  │ │     │
│  │  └───────────────────────────┘ │     │
│  └────────────────────────────────┘     │
│              │                          │
│  ┌───────────▼────────────────────┐     │
│  │  Merge Results + Validate JSON │     │
│  └────────────────────────────────┘     │
└─────────────────────────────────────────┘
              │
     ┌────────┴────────┐
     ▼                 ▼
data/labeled/      logs/
llm_outputs_v1.jsonl   invalid_outputs.jsonl
```

## Output Schema

### llm_outputs_v1.jsonl
```json
{
  "post_id": "abc123",
  "text": "Original post text...",
  "model_outputs": {
    "llama3.1": {"aspects": [0, 2], "reasoning": "..."},
    "mixtral": {"aspects": [0, 2, 5], "reasoning": "..."},
    "gemma2": {"aspects": [0], "reasoning": "..."}
  }
}
```

### invalid_outputs.jsonl
```json
{
  "post_id": "xyz789",
  "model": "gemma2",
  "raw_output": "Invalid JSON here...",
  "error_type": "json_decode_error",
  "timestamp": "2024-12-30T12:00:00Z"
}
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Model unavailable | Check model availability at startup |
| VRAM exceeded | Sequential execution, clear GPU between models |
| Slow throughput | Batch size 8, progress logging every 100 posts |
| Invalid JSON | Retry twice, log failures, use 2-vote fallback |
| Inconsistent labels | 3-model voting reduces variance |

## Open Questions

None - all requirements specified in Sprint 3 definition.
