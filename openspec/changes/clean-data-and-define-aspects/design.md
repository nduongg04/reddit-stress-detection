# Design: Data Cleaning and Aspect Schema

## Overview
This design addresses two parallel workstreams that can execute independently but both feed into Sprint 3 (LLM labeling).

## Data Cleaning Pipeline

### Token Length Filtering
- **Tokenizer**: `underthesea` (Vietnamese word tokenizer)
- **Range**: 20-300 tokens (per R3.2.2)
- **Rationale**: Posts <20 tokens lack context; >300 tokens exceed PhoBERT's effective window

### Semantic Deduplication
- **Embedding Model**: `paraphrase-multilingual-MiniLM-L12-v2` (384-dim)
- **Similarity Measure**: Cosine similarity
- **Threshold**: ≥0.90 (per R3.4.1)
- **Tie-breaker**: Keep post with earliest timestamp
- **Efficiency**: Use FAISS for pairwise similarity on large datasets

### Processing Flow
```
voz_posts_v1.jsonl
    │
    ▼
┌─────────────────┐
│ Token Filter    │ → removed_by_length
│ (20-300 tokens) │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ MiniLM Embed    │
│ (384-dim)       │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ FAISS Cosine    │ → removed_by_duplicate
│ Dedup (≥0.90)   │
└─────────────────┘
    │
    ▼
voz_posts_cleaned_v1.jsonl
```

### Statistics Output
```json
{
  "original_count": 12000,
  "removed_by_length": 1500,
  "removed_by_duplicate": 800,
  "final_count": 9700,
  "removal_rate": 0.192,
  "timestamp": "2024-01-15T10:30:00Z",
  "input_file": "data/raw/voz_posts_v1.jsonl",
  "output_file": "data/cleaned/voz_posts_cleaned_v1.jsonl"
}
```

## Aspect Schema Design

### Schema Structure
Each aspect contains:
- `id`: Integer 0-9 (unique identifier)
- `name_en`: English name
- `name_vi`: Vietnamese name
- `definition`: 1-2 sentence formal definition
- `academic_sources`: List of academic citations
- `inclusion_rules`: ≥3 rules for when aspect applies
- `exclusion_rules`: ≥2 rules for when aspect does NOT apply
- `keywords_vi`: ≥10 Vietnamese keywords
- `positive_examples`: Exactly 3 examples where aspect is present
- `negative_examples`: Exactly 3 examples where aspect is NOT present

### Aspect Taxonomy (R2.2)
| ID | English | Vietnamese | Description |
|----|---------|------------|-------------|
| 0 | Occupational | Công việc | Work-related stress |
| 1 | Financial | Tài chính | Money-related stress |
| 2 | Academic | Học tập | Education-related stress |
| 3 | Familial | Gia đình | Family-related stress |
| 4 | Health | Sức khỏe | Physical/mental health stress |
| 5 | Romantic | Tình cảm | Relationship stress |
| 6 | Existential | Hiện sinh | Meaning/identity stress |
| 7 | Social | Xã hội | Social/interpersonal stress |
| 8 | Life Events | Sự kiện | Major life change stress |
| 9 | Self Image | Hình ảnh bản thân | Self-perception stress |

**Note**: R2.2 specifies "Environmental/Contextual" for aspect 9, but the user requirements specify "Self_Image". Using Self_Image per user specification.

### Versioning Strategy
- Filename: `aspects_v{N}.json` where N is version number
- Hash file: `aspects_v{N}.sha256` for integrity verification
- Model metadata must reference aspect version used during training (R2.3)

## Dependencies
- Sprint 1 output: `data/raw/voz_posts_v1.jsonl`
- Python packages: `underthesea`, `sentence-transformers`, `faiss-cpu`

## Trade-offs Considered

### Token Filter
- **Alternative**: Character count filtering
- **Decision**: Token count with underthesea for linguistic accuracy

### Deduplication
- **Alternative**: Exact string matching, n-gram Jaccard similarity
- **Decision**: MiniLM embeddings capture semantic duplicates (paraphrases)

### Aspect Count
- **Alternative**: Fewer aspects (easier labeling), more aspects (finer granularity)
- **Decision**: 10 aspects per R2.1, balancing granularity with labeler agreement
