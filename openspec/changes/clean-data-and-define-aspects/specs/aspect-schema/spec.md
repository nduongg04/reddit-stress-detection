# aspect-schema Specification

## Purpose
Define a versioned stress aspect taxonomy with rules, keywords, and examples for consistent LLM labeling.

## ADDED Requirements

### Requirement: Aspect Count
The system SHALL define exactly 10 stress aspects with unique integer IDs 0-9 (R2.1).

#### Scenario: Aspect enumeration
- **WHEN** the aspect schema is loaded
- **THEN** it SHALL contain exactly 10 aspects with IDs 0 through 9

#### Scenario: ID uniqueness
- **WHEN** aspects are defined
- **THEN** each aspect SHALL have a unique integer ID

---

### Requirement: Stress Aspect Taxonomy
The system SHALL define the following 10 stress aspects (R2.2).

| ID | name_en | name_vi |
|----|---------|---------|
| 0 | Occupational | Công việc |
| 1 | Financial | Tài chính |
| 2 | Academic | Học tập |
| 3 | Familial | Gia đình |
| 4 | Health | Sức khỏe |
| 5 | Romantic | Tình cảm |
| 6 | Existential | Hiện sinh |
| 7 | Social | Xã hội |
| 8 | Life Events | Sự kiện |
| 9 | Self Image | Hình ảnh bản thân |

#### Scenario: Aspect names match taxonomy
- **WHEN** the aspect schema is loaded
- **THEN** each aspect SHALL have matching English and Vietnamese names per the taxonomy table

---

### Requirement: Aspect Properties
Each stress aspect SHALL include the following properties (R2.2.2).

#### Scenario: Required fields present
- **WHEN** an aspect is defined
- **THEN** it SHALL include: `id` (int), `name_en` (str), `name_vi` (str), `definition` (str), `academic_sources` (list), `inclusion_rules` (list), `exclusion_rules` (list), `keywords_vi` (list), `positive_examples` (list), `negative_examples` (list)

#### Scenario: Definition format
- **WHEN** an aspect definition is provided
- **THEN** it SHALL be 1-2 sentences describing the stress type

#### Scenario: Academic sources
- **WHEN** academic sources are listed
- **THEN** they SHALL be formatted as citations (author, year)

---

### Requirement: Inclusion Rules
Each aspect SHALL have at least 3 inclusion rules defining when the aspect applies (R2.2.2).

#### Scenario: Minimum inclusion rules
- **WHEN** an aspect is defined
- **THEN** it SHALL have ≥3 inclusion rules

#### Scenario: Rule clarity
- **WHEN** inclusion rules are written
- **THEN** each rule SHALL describe a specific condition that triggers aspect assignment

---

### Requirement: Exclusion Rules
Each aspect SHALL have at least 2 exclusion rules defining when the aspect does NOT apply (R2.2.2).

#### Scenario: Minimum exclusion rules
- **WHEN** an aspect is defined
- **THEN** it SHALL have ≥2 exclusion rules

#### Scenario: Boundary clarification
- **WHEN** exclusion rules are written
- **THEN** they SHALL clarify boundaries between similar aspects

---

### Requirement: Vietnamese Keywords
Each aspect SHALL have at least 10 Vietnamese keywords for pattern matching (R2.2.2).

#### Scenario: Minimum keywords
- **WHEN** an aspect is defined
- **THEN** it SHALL have ≥10 Vietnamese keywords

#### Scenario: Keyword relevance
- **WHEN** keywords are listed
- **THEN** they SHALL be commonly used Vietnamese terms associated with the stress type

---

### Requirement: Positive Examples
Each aspect SHALL have exactly 3 positive examples showing stress presence (R2.2.2).

#### Scenario: Positive example count
- **WHEN** an aspect is defined
- **THEN** it SHALL have exactly 3 positive examples

#### Scenario: Positive example content
- **WHEN** positive examples are provided
- **THEN** each SHALL be a Vietnamese text snippet clearly expressing the stress aspect

---

### Requirement: Negative Examples
Each aspect SHALL have exactly 3 negative examples showing stress absence (R2.2.2).

#### Scenario: Negative example count
- **WHEN** an aspect is defined
- **THEN** it SHALL have exactly 3 negative examples

#### Scenario: Negative example content
- **WHEN** negative examples are provided
- **THEN** each SHALL be a Vietnamese text snippet that might seem related but does NOT express the stress aspect

---

### Requirement: Schema Versioning
The aspect schema SHALL be versioned in the filename (R2.3).

#### Scenario: Version in filename
- **WHEN** the aspect schema is saved
- **THEN** it SHALL be named `aspects_v{N}.json` where N is the version number

#### Scenario: Initial version
- **WHEN** the first schema is created
- **THEN** it SHALL be named `aspects_v1.json`

---

### Requirement: Schema Integrity
The aspect schema SHALL have an accompanying SHA-256 hash file (R2.3).

#### Scenario: Hash file creation
- **WHEN** the aspect schema is saved
- **THEN** a SHA-256 hash SHALL be computed and stored in `aspects_v1.sha256`

#### Scenario: Hash verification
- **WHEN** the schema is loaded for training
- **THEN** the system SHALL verify the hash matches the file content

---

### Requirement: Schema Location
The aspect schema files SHALL be stored in the config directory.

#### Scenario: File location
- **WHEN** the aspect schema is created
- **THEN** it SHALL be stored at `config/aspects_v1.json`

#### Scenario: Hash file location
- **WHEN** the hash file is created
- **THEN** it SHALL be stored at `config/aspects_v1.sha256`
