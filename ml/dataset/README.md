# Reddit Stress Detection Dataset

**Version**: 1.0.0
**Created**: 2025-10-12
**Purpose**: Binary classification of stress-related content in Reddit posts

---

## Overview

A labeled dataset of Reddit posts for training a stress detection model. Posts are labeled as either **STRESS** (expressing current personal stress/distress) or **NON-STRESS** (not expressing current personal stress).

---

## Quick Start

### Current Dataset: Ollama Auto-Labeled (RECOMMENDED)

The project uses **Ollama (llama3.1:8b)** auto-labeled data as the primary training source:

```bash
# Primary labeled dataset (already created)
ml/dataset/labeled/reddit_crawl_ollama_labeled.csv  # 11,270 labeled posts

# Prepare dataset for training
pip install pandas scikit-learn numpy
python ml/dataset/scripts/prepare_dataset.py \
    --input ml/dataset/labeled/reddit_crawl_ollama_labeled.csv

# Output: ml/dataset/splits/{train,val,test}.csv
```

### Alternative: Extract & Label New Data

If you need to create a new labeled dataset:

#### 1. Extract Data from Cassandra

```bash
# Extract posts for labeling
python ml/dataset/scripts/extract_data.py --num-posts 15000

# Output: ml/dataset/raw/unlabeled_posts.csv
```

#### 2. Auto-Label with Ollama

Labeling scripts have been removed after data was labeled. The ollama labeling process involved:
- Using llama3.1:8b model via Ollama API
- Binary classification: STRESS vs NON_STRESS
- Confidence scoring and reasoning capture
- Result: `reddit_crawl_ollama_labeled.csv` (11,270 posts)

#### 3. Prepare Dataset for Training

```bash
# Run full preparation pipeline
pip install pandas scikit-learn numpy
python ml/dataset/scripts/prepare_dataset.py \
    --input ml/dataset/labeled/reddit_crawl_ollama_labeled.csv

# Output: ml/dataset/splits/{train,val,test}.csv
```

### 4. Use in Training

```python
import pandas as pd

# Load splits
train = pd.read_csv('ml/dataset/splits/train.csv')
val = pd.read_csv('ml/dataset/splits/val.csv')
test = pd.read_csv('ml/dataset/splits/test.csv')

# Access features and labels
X_train = train['text']
y_train = train['label']
```

---

## Dataset Structure

### Directory Layout

```
ml/dataset/
├── raw/                           # Raw extracted data
│   ├── unlabeled_posts.csv       # Extracted from Cassandra
│   └── pilot_set.csv             # 100-post pilot for agreement testing
│
├── labeled/                       # Labeled data
│   ├── labels.json               # Label assignments (by post_id)
│   ├── labeled_posts.csv         # Posts with labels
│   └── progress.json             # Labeling progress tracker
│
├── processed/                     # Processed data
│   └── balanced_dataset.csv      # Balanced, cleaned dataset
│
├── splits/                        # Train/val/test splits
│   ├── train.csv                 # Training set (70%)
│   ├── val.csv                   # Validation set (15%)
│   └── test.csv                  # Test set (15%)
│
├── scripts/                       # Data processing scripts
│   ├── extract_data.py           # Extract from Cassandra
│   ├── label_ui.py               # Labeling interface
│   └── prepare_dataset.py        # Quality checks & splits
│
├── LABELING_GUIDELINES.md        # Annotation guidelines
├── metadata.json                  # Dataset metadata
└── README.md                      # This file
```

---

## Data Fields

### Raw Data (from Cassandra)

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | string | Unique Reddit post ID |
| `title` | string | Post title |
| `body` | string | Post body text |
| `text` | string | Combined title + body |
| `author` | string | Reddit username |
| `subreddit` | string | Source subreddit |
| `created_utc` | int | Unix timestamp |
| `score` | int | Reddit score (upvotes - downvotes) |
| `num_comments` | int | Number of comments |
| `day_bucket` | string | Date partition (YYYY-MM-DD) |

### Labeled Data (after annotation)

All fields from raw data, plus:

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | **STRESS** or **NON_STRESS** |
| `labeled_at` | string | ISO 8601 timestamp |
| `notes` | string | Optional annotator notes |

---

## Dataset Statistics

Expected distribution (will vary based on actual labeling):

### Target Metrics

- **Total samples**: 10,000-15,000
- **Train**: 70% (~7,000-10,500)
- **Validation**: 15% (~1,500-2,250)
- **Test**: 15% (~1,500-2,250)

### Class Distribution

- **STRESS**: ~50% (balanced)
- **NON_STRESS**: ~50% (balanced)

### Subreddit Distribution

Target subreddits (can be customized):
- r/anxiety
- r/depression
- r/stress
- r/mentalhealth
- r/Anxiety (capitalized)
- r/depression_help
- r/mentalillness

### Text Length

- **Min**: 10 characters (filtered)
- **Median**: ~200-500 characters (typical)
- **Max**: ~10,000 characters (Reddit limit)

---

## Labeling Process

### Guidelines

See **`LABELING_GUIDELINES.md`** for complete annotation guidelines.

**Summary**:
- **STRESS**: Post expresses current personal stress/distress
- **NON-STRESS**: Post does NOT express current personal stress

### Quality Control

1. **Pilot Round**: 100 posts labeled by 2+ annotators
2. **Inter-Annotator Agreement**: Target Cohen's Kappa > 0.8
3. **Disagreement Resolution**: Discussed and adjudicated
4. **Quality Checks**: Automated validation of labels

### Labeling Tools

- **Streamlit UI** (`label_ui.py`): Simple web interface
- **Label Studio** (optional): Advanced annotation platform
- **Manual**: Direct CSV editing (not recommended)

---

## Data Processing Pipeline

### Step 1: Extraction

```bash
python ml/dataset/scripts/extract_data.py \
    --num-posts 15000 \
    --output ml/dataset/raw/unlabeled_posts.csv
```

**What it does**:
- Queries Cassandra `raw_posts_by_day` table
- Samples across subreddits and time periods
- Removes very short posts (<20 chars)
- Filters out [deleted] and [removed] posts
- Deduplicates by post_id

### Step 2: Labeling

```bash
streamlit run ml/dataset/scripts/label_ui.py
```

**What it does**:
- Presents posts one at a time
- Records STRESS / NON-STRESS labels
- Tracks progress automatically
- Allows notes for difficult cases
- Exports to CSV with labels

### Step 3: Quality Checks & Balancing

```bash
python ml/dataset/scripts/prepare_dataset.py \
    --input ml/dataset/labeled/labeled_posts.csv
```

**What it does**:
- Validates data quality
- Removes very short posts (<10 chars)
- Removes duplicates
- Balances classes to 50/50
- Creates stratified train/val/test splits
- Generates metadata JSON

---

## Usage Examples

### Load Dataset

```python
import pandas as pd

# Load all splits
train = pd.read_csv('ml/dataset/splits/train.csv')
val = pd.read_csv('ml/dataset/splits/val.csv')
test = pd.read_csv('ml/dataset/splits/test.csv')

print(f"Train: {len(train)} samples")
print(f"Val: {len(val)} samples")
print(f"Test: {len(test)} samples")
```

### Basic Analysis

```python
# Class distribution
print("Label distribution:")
print(train['label'].value_counts())

# Text length statistics
train['text_length'] = train['text'].str.len()
print("\nText length stats:")
print(train['text_length'].describe())

# Subreddit distribution
if 'subreddit' in train.columns:
    print("\nTop subreddits:")
    print(train['subreddit'].value_counts().head())
```

### Prepare for Model Training

```python
from sklearn.model_selection import train_test_split

# Extract features and labels
X_train = train['text'].values
y_train = (train['label'] == 'STRESS').astype(int).values

X_val = val['text'].values
y_val = (val['label'] == 'STRESS').astype(int).values

X_test = test['text'].values
y_test = (test['label'] == 'STRESS').astype(int).values

print(f"Training samples: {len(X_train)}")
print(f"Positive class ratio: {y_train.mean():.2%}")
```

---

## Known Limitations

### Sampling Bias

- **Limited subreddits**: Only mental health-related subreddits
- **Active users**: Biased toward users who post frequently
- **Time period**: Limited to data collection window
- **Language**: English only

### Labeling Challenges

- **Subjectivity**: Stress expression can be subjective
- **Context**: Limited context (no comment thread)
- **Sarcasm**: Difficult to detect humor/sarcasm
- **Mixed posts**: Some posts have both stressed and non-stressed content

### Data Quality

- **Deleted content**: Some posts may be deleted after collection
- **Short posts**: Very short posts filtered out
- **Reddit-specific**: May not generalize to other platforms

---

## Ethical Considerations

### Privacy

- **Public data**: All data is from public Reddit posts
- **Anonymization**: Consider removing usernames in final dataset
- **Sensitive content**: Posts may contain personal mental health information

### Use Cases

- **Intended use**: Research and educational purposes
- **Not for**: Clinical diagnosis or medical advice
- **Limitations**: Model should not replace professional mental health support

### Bias

- **Demographic**: Reddit user base is not representative of general population
- **Mental health**: Posts from mental health subreddits may not represent typical stress
- **Language**: English-only limits global applicability

---

## Citation

If you use this dataset in your research, please cite:

```
@dataset{reddit_stress_detection_2025,
  title={Reddit Stress Detection Dataset},
  author={Your Name/Team},
  year={2025},
  version={1.0.0},
  source={Reddit via PRAW/PSAW},
  url={https://github.com/your-repo}
}
```

---

## License

**For research and educational purposes only.**

This dataset is derived from Reddit data and is subject to:
- Reddit Terms of Service
- Reddit API Terms of Use
- Fair use for research purposes

**Not for commercial use without proper licensing.**

---

## Troubleshooting

### Issue: No data extracted

**Problem**: `extract_data.py` returns 0 posts

**Solution**:
```bash
# Check Cassandra has data
docker exec -it reddit-cassandra cqlsh -e "
SELECT COUNT(*) FROM reddit_rt.raw_posts_by_day;
"

# If empty, run backfill first (TASK-010)
```

### Issue: Labeling UI won't start

**Problem**: Streamlit error or missing file

**Solution**:
```bash
# Install dependencies
pip install streamlit pandas

# Check data file exists
ls ml/dataset/raw/unlabeled_posts.csv

# Run with explicit path
streamlit run ml/dataset/scripts/label_ui.py
```

### Issue: Imbalanced dataset

**Problem**: One class dominates (>70%)

**Solution**:
```bash
# Balance during preparation
python ml/dataset/scripts/prepare_dataset.py \
    --input ml/dataset/labeled/labeled_posts.csv \
    --balance-method oversample  # or undersample
```

---

## Next Steps

After dataset preparation:

1. **Review splits**: Check `ml/dataset/splits/*.csv`
2. **Check metadata**: Review `ml/dataset/metadata.json`
3. **Start training**: Move to TASK-019 (Model Training)

---

## Support

For questions or issues:
1. Check this README
2. Review `LABELING_GUIDELINES.md`
3. Check task documentation: `tasks/detailed/task018.md`
4. Review script help: `python script.py --help`

---

## Version History

- **v1.0.0** (2025-10-12): Initial dataset creation
  - Extraction script
  - Labeling UI
  - Quality checks and preparation pipeline
  - Documentation

---

**Dataset created as part of TASK-018: Dataset Collection & Labeling**
