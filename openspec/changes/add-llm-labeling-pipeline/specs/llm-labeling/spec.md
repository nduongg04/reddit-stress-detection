# Capability: LLM Labeling

Multi-label stress aspect classification using 3-model LLM ensemble via Ollama.

## ADDED Requirements

### Requirement: Ollama Model Availability
The system SHALL verify that all 3 required models are available in Ollama before starting the labeling pipeline.

#### Scenario: All models available
- **WHEN** the labeling script starts
- **THEN** the system SHALL verify llama3.1:8b, mixtral:8x7b, and gemma2:9b respond via Ollama HTTP API at localhost:11434

#### Scenario: Missing model
- **WHEN** any required model is not available
- **THEN** the system SHALL exit with an error listing the missing models

---

### Requirement: Frozen Prompt Template
The system SHALL use a versioned prompt template stored in `config/prompt_v1.txt` with SHA-256 hash verification.

#### Scenario: Prompt loading
- **WHEN** the labeling script starts
- **THEN** the system SHALL load the prompt from `config/prompt_v1.txt`
- **AND** verify its SHA-256 hash matches `config/prompt_v1.sha256`

#### Scenario: Prompt includes aspect definitions
- **WHEN** generating prompts for a post
- **THEN** the prompt SHALL include all 10 aspect definitions from `config/aspects_v1.json`
- **AND** require JSON output format: `{"aspects": [0,2,5], "reasoning": "..."}`

---

### Requirement: Sequential Model Execution
The system SHALL process posts through each model sequentially, loading only one model at a time.

#### Scenario: Model execution order
- **WHEN** processing posts
- **THEN** the system SHALL:
  1. Load llama3.1:8b and label all posts
  2. Unload llama3.1:8b and load mixtral:8x7b, then label all posts
  3. Unload mixtral:8x7b and load gemma2:9b, then label all posts

#### Scenario: Batch processing
- **WHEN** labeling posts with a model
- **THEN** the system SHALL process posts in batches of 8 for memory efficiency

---

### Requirement: Request Timeout and Retry
The system SHALL implement timeout and retry logic for LLM requests.

#### Scenario: Request timeout
- **WHEN** an LLM request does not complete within 60 seconds
- **THEN** the request SHALL be terminated and retried

#### Scenario: Retry on failure
- **WHEN** an LLM request fails (timeout or error)
- **THEN** the system SHALL retry up to 2 times before marking the request as failed

---

### Requirement: Model Failure Fallback
The system SHALL handle model failures with graceful degradation.

#### Scenario: Single model failure
- **WHEN** 1 of 3 models fails to produce valid output for a post
- **THEN** the system SHALL use the 2 remaining model outputs for that post

#### Scenario: Multiple model failure
- **WHEN** 2 or more models fail to produce valid output for a post
- **THEN** the system SHALL log the post to `logs/invalid_outputs.jsonl` and exclude it from final output

---

### Requirement: Invalid Output Logging
The system SHALL log all invalid LLM outputs for debugging and quality monitoring.

#### Scenario: Invalid JSON output
- **WHEN** a model produces non-JSON or malformed JSON output
- **THEN** the system SHALL log to `logs/invalid_outputs.jsonl` with:
  - `post_id`: The post identifier
  - `model`: The model name (e.g., "llama3.1")
  - `raw_output`: The raw model response
  - `error_type`: One of `json_decode_error`, `missing_fields`, `timeout`, `api_error`
  - `timestamp`: ISO 8601 timestamp

---

### Requirement: Labeled Output Format
The system SHALL produce labeled output in JSONL format with all model responses.

#### Scenario: Output file format
- **WHEN** labeling completes
- **THEN** the system SHALL write results to `data/labeled/llm_outputs_v1.jsonl`

#### Scenario: Output record schema
- **WHEN** writing a labeled post
- **THEN** each record SHALL contain:
  - `post_id`: Original post identifier
  - `text`: Original post text
  - `model_outputs`: Object with keys `llama3.1`, `mixtral`, `gemma2`, each containing `{"aspects": [...], "reasoning": "..."}`
