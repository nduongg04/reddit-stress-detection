# data-cleaning Specification

## Purpose
Clean and deduplicate raw VOZ.vn posts before LLM labeling, ensuring data quality and reducing redundancy.

## ADDED Requirements

### Requirement: Token Length Filtering
The system SHALL filter posts by token count using the underthesea Vietnamese tokenizer (R3.2.2).

#### Scenario: Post within valid range
- **WHEN** a post has 20-300 tokens (inclusive)
- **THEN** the post SHALL be retained for further processing

#### Scenario: Post too short
- **WHEN** a post has fewer than 20 tokens
- **THEN** the post SHALL be removed and counted in `removed_by_length`

#### Scenario: Post too long
- **WHEN** a post has more than 300 tokens
- **THEN** the post SHALL be removed and counted in `removed_by_length`

---

### Requirement: Embedding Model
The system SHALL use `paraphrase-multilingual-MiniLM-L12-v2` for generating sentence embeddings (R3.4.1).

#### Scenario: Embedding generation
- **WHEN** a post passes token length filtering
- **THEN** the system SHALL generate a 384-dimensional embedding vector

#### Scenario: Model loading
- **WHEN** the cleaning script starts
- **THEN** it SHALL load the MiniLM model from sentence-transformers

---

### Requirement: Semantic Deduplication
The system SHALL remove semantically duplicate posts using cosine similarity on embeddings (R3.4.1).

#### Scenario: Duplicate detection
- **WHEN** two posts have cosine similarity ≥0.90
- **THEN** they SHALL be considered duplicates

#### Scenario: Duplicate resolution
- **WHEN** duplicates are detected
- **THEN** the system SHALL keep the post with the earliest timestamp

#### Scenario: Efficient similarity computation
- **WHEN** computing pairwise similarities
- **THEN** the system SHALL use FAISS for efficient large-scale computation

---

### Requirement: Cleaning Statistics Report
The system SHALL generate a JSON statistics report for auditability (R6.2).

#### Scenario: Report generation
- **WHEN** data cleaning completes
- **THEN** the system SHALL write a report to `reports/cleaning_stats_v1.json`

#### Scenario: Required statistics
- **WHEN** the report is generated
- **THEN** it SHALL include: `original_count`, `removed_by_length`, `removed_by_duplicate`, `final_count`, `removal_rate`

#### Scenario: Metadata inclusion
- **WHEN** the report is generated
- **THEN** it SHALL include: `timestamp`, `input_file`, `output_file`

---

### Requirement: Output Format
The system SHALL output cleaned posts in JSONL format preserving original fields.

#### Scenario: JSONL output
- **WHEN** cleaning completes
- **THEN** cleaned posts SHALL be written to `data/cleaned/voz_posts_cleaned_v1.jsonl`

#### Scenario: Field preservation
- **WHEN** a post is written to output
- **THEN** it SHALL retain all original fields: `post_id`, `text`, `timestamp`, `source`, `url`, `crawled_at`

---

### Requirement: Expected Dataset Size
The cleaning pipeline SHALL reduce the dataset by approximately 20% (R3.3).

#### Scenario: Final count validation
- **WHEN** cleaning completes on 12,000 raw posts
- **THEN** the final count SHOULD be 8,000-10,000 posts
