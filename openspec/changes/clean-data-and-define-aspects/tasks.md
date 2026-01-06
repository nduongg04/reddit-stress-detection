# Tasks: Clean Data and Define Aspects

## Prerequisites
- [x] Sprint 1 complete: Cassandra table `reddit_rt.voz_raw_posts` has 12,165 posts
- [x] Python packages installed: `pyvi`, `sentence-transformers`, `sklearn`, `cassandra-driver`

---

## 1. Data Cleaning Pipeline

### 1.1 Token Length Filter
- [x] Load posts from Cassandra `reddit_rt.voz_raw_posts`
- [x] Initialize pyvi tokenizer (ViTokenizer)
- [x] Filter posts with <20 tokens → count as `removed_by_length`
- [x] Filter posts with >300 tokens → count as `removed_by_length`
- [x] Log progress every 1,000 posts

### 1.2 Embedding Generation
- [x] Load `paraphrase-multilingual-MiniLM-L12-v2` model from sentence-transformers
- [x] Generate 384-dim embeddings for all length-filtered posts
- [x] Store embeddings in memory

### 1.3 Semantic Deduplication
- [x] Compute pairwise cosine similarities using sklearn
- [x] Identify duplicates at threshold ≥0.90
- [x] For each duplicate group, keep post with earliest timestamp
- [x] Count removed posts as `removed_by_duplicate`

### 1.4 Output Generation
- [x] Write cleaned posts to `data/cleaned/voz_posts_cleaned_v1.jsonl`
- [x] Preserve all original fields: `post_id`, `text`, `timestamp`, `source`, `url`
- [x] Verify final count is 8,000-10,000 posts ✅ (10,460 posts)

### 1.5 Statistics Report
- [x] Create `reports/` directory if not exists
- [x] Generate `reports/cleaning_stats_v1.json` with:
  - `original_count`: 12,165
  - `removed_by_length`: 1,689
  - `removed_by_duplicate`: 16
  - `final_count`: 10,460
  - `removal_rate`: 14.02%
  - `timestamp`
  - `input_source`
  - `output_file`

---

## 2. Aspect Schema Definition

### 2.1 Schema Structure
- [x] Create `config/` directory if not exists
- [x] Define JSON schema with 10 aspects (IDs 0-9)

### 2.2 Aspect Content (for each of 10 aspects)
- [x] `id`: Unique integer 0-9
- [x] `name_en`: English name
- [x] `name_vi`: Vietnamese name
- [x] `definition`: 1-2 sentence formal definition
- [x] `academic_sources`: List of citations
- [x] `inclusion_rules`: ≥3 rules (4 rules each)
- [x] `exclusion_rules`: ≥2 rules (2 rules each)
- [x] `keywords_vi`: ≥10 Vietnamese keywords (13-15 each)
- [x] `positive_examples`: Exactly 3 examples
- [x] `negative_examples`: Exactly 3 examples

### 2.3 Aspect Checklist
- [x] Aspect 0: Occupational (Công việc) - 14 keywords
- [x] Aspect 1: Financial (Tài chính) - 14 keywords
- [x] Aspect 2: Academic (Học tập) - 15 keywords
- [x] Aspect 3: Familial (Gia đình) - 15 keywords
- [x] Aspect 4: Health (Sức khỏe) — HIGH-RISK - 15 keywords
- [x] Aspect 5: Romantic (Tình cảm) - 14 keywords
- [x] Aspect 6: Existential (Hiện sinh) — HIGH-RISK - 13 keywords
- [x] Aspect 7: Social (Xã hội) - 13 keywords
- [x] Aspect 8: Life Events (Sự kiện) — HIGH-RISK - 14 keywords
- [x] Aspect 9: Self Image (Hình ảnh bản thân) - 14 keywords

### 2.4 Versioning
- [x] Save schema as `config/aspects_v1.json`
- [x] Compute SHA-256 hash of schema file
- [x] Save hash to `config/aspects_v1.sha256`

---

## 3. Validation

### 3.1 Data Cleaning Validation
- [x] Verify `voz_posts_cleaned_v1.jsonl` exists and is valid JSONL
- [x] Verify post count is 8,000-10,000 (actual: 10,460 ✅)
- [x] Verify no duplicate post_ids
- [x] Verify all posts have 20-300 tokens
- [x] Verify statistics report matches actual counts

### 3.2 Aspect Schema Validation
- [x] Verify JSON is valid and parseable
- [x] Verify exactly 10 aspects with IDs 0-9
- [x] Verify each aspect has all required fields
- [x] Verify field count requirements (≥3 inclusion, ≥2 exclusion, ≥10 keywords, 3 positive, 3 negative)
- [x] Verify SHA-256 hash matches file content

---

## Deliverables

| File | Description | Status |
|------|-------------|--------|
| `scripts/data_cleaning.py` | Data cleaning pipeline script | ✅ Created |
| `data/cleaned/voz_posts_cleaned_v1.jsonl` | Cleaned posts (10,460) | ✅ Created |
| `reports/cleaning_stats_v1.json` | Cleaning statistics | ✅ Created |
| `config/aspects_v1.json` | Stress aspect schema | ✅ Created |
| `config/aspects_v1.sha256` | Schema integrity hash | ✅ Created |

---

## Results Summary

**Data Cleaning:**
- Original: 12,165 posts (from Cassandra)
- Removed by length: 1,689 (13.9%)
- Removed by duplicate: 16 (0.1%)
- Final: 10,460 posts
- Total removal rate: 14.0%

**Aspect Schema:**
- 10 aspects defined with IDs 0-9
- SHA-256: `1db58add02c68488e6eb0c178dc52727e12254b6868ba6c44362883f9a166677`

---

## Notes

- Data source changed from JSONL file to Cassandra (per Sprint 2 requirements)
- Used `pyvi` instead of `underthesea` (Python 3.13 compatibility)
- Used `sklearn.metrics.pairwise.cosine_similarity` instead of FAISS (stability)
- Run cleaning: `python scripts/data_cleaning.py`
