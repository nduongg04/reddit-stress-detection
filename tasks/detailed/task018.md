# TASK-018: Dataset Collection & Labeling

**Owner:** ML Engineer
**Priority:** Critical
**Dependencies:** TASK-010 (Historical Backfill)
**Estimate:** 3 days

---

## Overview

Create a high-quality labeled dataset of Reddit posts for training the stress detection model. This involves extracting posts from the historical backfill, designing labeling guidelines, collecting annotations, ensuring quality, and preparing the final dataset splits.

---

## Subtasks

### Subtask 018.1: Data Extraction from Cassandra

**Estimate:** 2 hours

**Description:**
- Extract Reddit posts from Cassandra `raw_posts_by_day` table
- Sample diverse posts across subreddits and time periods
- Export to format suitable for labeling
- Target: 15,000 raw posts (to get 10,000+ after filtering)

**Acceptance Criteria:**
- 15k+ posts extracted
- Diverse subreddit representation
- Data exported as CSV/JSON
- No duplicates

**Files to Create:**
`ml/dataset/scripts/extract_data.py`

```python
from cassandra.cluster import Cluster
import pandas as pd
import json
from datetime import datetime, timedelta
import random

class DataExtractor:
    def __init__(self, contact_points=['localhost'], keyspace='reddit_rt'):
        self.cluster = Cluster(contact_points)
        self.session = self.cluster.connect(keyspace)

    def extract_posts(self, num_posts=15000, subreddits=None):
        """Extract posts for labeling"""
        if subreddits is None:
            subreddits = ['anxiety', 'depression', 'stress', 'mentalhealth']

        posts_per_subreddit = num_posts // len(subreddits)

        all_posts = []

        for subreddit in subreddits:
            print(f"Extracting from r/{subreddit}...")

            # Query posts from last 6 months
            query = """
                SELECT post_id, title, body, author, subreddit,
                       created_utc, score, num_comments
                FROM raw_posts_by_day
                WHERE subreddit = %s
                  AND day_bucket >= %s
                LIMIT %s
            """

            # Get posts from 6 months ago
            six_months_ago = datetime.now() - timedelta(days=180)
            day_bucket = six_months_ago.strftime('%Y-%m-%d')

            rows = self.session.execute(query, (subreddit, day_bucket, posts_per_subreddit * 2))

            posts = [
                {
                    'post_id': row.post_id,
                    'title': row.title or '',
                    'body': row.body or '',
                    'text': f"{row.title or ''} {row.body or ''}".strip(),
                    'author': row.author,
                    'subreddit': row.subreddit,
                    'created_utc': row.created_utc,
                    'score': row.score,
                    'num_comments': row.num_comments
                }
                for row in rows
            ]

            # Filter out deleted/removed posts
            posts = [p for p in posts if p['text'] and len(p['text']) > 20]

            # Random sample
            if len(posts) > posts_per_subreddit:
                posts = random.sample(posts, posts_per_subreddit)

            all_posts.extend(posts)

        # Shuffle all posts
        random.shuffle(all_posts)

        return all_posts

    def save_to_csv(self, posts, output_file):
        """Save posts to CSV for labeling"""
        df = pd.DataFrame(posts)
        df.to_csv(output_file, index=False)
        print(f"Saved {len(posts)} posts to {output_file}")

    def save_to_json(self, posts, output_file):
        """Save posts to JSON"""
        with open(output_file, 'w') as f:
            json.dump(posts, f, indent=2)
        print(f"Saved {len(posts)} posts to {output_file}")

def main():
    extractor = DataExtractor()

    posts = extractor.extract_posts(num_posts=15000)

    print(f"\nExtracted {len(posts)} posts")
    print(f"Subreddit distribution:")
    from collections import Counter
    subreddit_counts = Counter(p['subreddit'] for p in posts)
    for subreddit, count in subreddit_counts.items():
        print(f"  r/{subreddit}: {count}")

    # Save in both formats
    extractor.save_to_csv(posts, 'ml/dataset/raw/unlabeled_posts.csv')
    extractor.save_to_json(posts, 'ml/dataset/raw/unlabeled_posts.json')

if __name__ == "__main__":
    main()
```

**Run:**
```bash
mkdir -p ml/dataset/{raw,labeled,processed,splits}
python ml/dataset/scripts/extract_data.py
```

---

### Subtask 018.2: Create Labeling Guidelines

**Estimate:** 2 hours

**Description:**
- Define clear criteria for "stress" vs "non-stress" posts
- Create examples of each category
- Document edge cases and how to handle them
- **[USER TASK]** Review and refine labeling guidelines

**Acceptance Criteria:**
- Clear labeling criteria documented
- Examples provided for each category
- Edge cases addressed
- Guidelines reviewed by team

**Files to Create:**
`ml/dataset/LABELING_GUIDELINES.md`

```markdown
# Stress Detection Labeling Guidelines

## Task
Label each Reddit post as either **STRESS** or **NON-STRESS**.

## Definitions

### STRESS
Posts that express stress, anxiety, worry, or overwhelm. Indicators include:
- Explicit mentions of feeling stressed, anxious, worried, overwhelmed
- Describing difficult life situations causing distress
- Seeking help for stress-related problems
- Expressing inability to cope with challenges
- Physical symptoms of stress (insomnia, headaches, tension)

### NON-STRESS
Posts that do NOT primarily express stress:
- General questions or information requests
- Sharing success stories or recovery
- Offering support to others (without personal stress)
- Casual conversation
- Humor or memes
- Non-emotional factual content

## Examples

### STRESS Examples

**Example 1:**
"I have a huge exam tomorrow and I haven't studied enough. I can't sleep and I feel like I'm going to fail. My heart is racing and I can't calm down."
→ **STRESS** (explicit stress expression, physical symptoms)

**Example 2:**
"Work has been overwhelming lately. I have three deadlines this week and I don't know how I'm going to manage. Anyone else feeling this way?"
→ **STRESS** (overwhelm, multiple stressors)

**Example 3:**
"DAE get anxiety about checking their email? I feel my stomach drop every time I see a notification."
→ **STRESS** (anxiety symptoms, avoidance behavior)

### NON-STRESS Examples

**Example 1:**
"What are some good breathing exercises for anxiety? I'm looking for recommendations to share with a friend."
→ **NON-STRESS** (information seeking, not expressing personal stress)

**Example 2:**
"Just wanted to share that I finally graduated after 6 years! To anyone struggling, keep going!"
→ **NON-STRESS** (success story, encouragement)

**Example 3:**
"Is there a difference between stress and anxiety? I've always wondered about this."
→ **NON-STRESS** (factual question, educational)

## Edge Cases

### Ambiguous Posts
If uncertain, consider:
1. Is the poster expressing *current personal distress*?
2. Does the emotional tone suggest stress?
3. When in doubt, label as **NON-STRESS**

### Posts with Mixed Content
- If >50% of the post expresses stress → **STRESS**
- If stress is mentioned but not the main focus → **NON-STRESS**

### Humor/Sarcasm
- "Stress memes" without personal expression → **NON-STRESS**
- Humorous posts with underlying stress → Use judgment

### Support Requests
- Asking for help due to stress → **STRESS**
- Asking general questions → **NON-STRESS**

## What to Ignore
- Grammatical errors or typos
- Post length (stress can be expressed briefly or at length)
- Username or subreddit
- Number of upvotes/comments

## Quality Guidelines
- Read the entire post before labeling
- Focus on the poster's emotional state
- Be consistent across similar posts
- Take breaks to avoid fatigue
- Flag posts you're uncertain about for review

## Inter-Annotator Agreement
- Multiple annotators will label the same posts
- Disagreements will be discussed and resolved
- Target agreement: >80% (Cohen's Kappa >0.8)
```

---

### Subtask 018.3: Set Up Labeling Platform

**Estimate:** 2 hours

**Description:**
- Choose labeling tool (Label Studio, Prodigy, or custom interface)
- Set up labeling platform
- Configure project with guidelines
- Test labeling workflow

**Acceptance Criteria:**
- Labeling platform operational
- Guidelines integrated
- Test labeling completed
- Platform accessible to annotators

**Option 1: Label Studio (Recommended)**

```bash
# Install Label Studio
pip install label-studio

# Start Label Studio
label-studio start ml/dataset/labelstudio
```

**Label Studio Config:**
`ml/dataset/labelstudio/config.xml`

```xml
<View>
  <Header value="Label Reddit Post for Stress Detection"/>

  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Text name="subreddit" value="Subreddit: $subreddit"/>
    <Text name="title" value="$title"/>
    <Text name="text" value="$text"/>
  </View>

  <Choices name="label" toName="text" choice="single" showInLine="true">
    <Choice value="STRESS" background="red"/>
    <Choice value="NON_STRESS" background="green"/>
    <Choice value="UNCLEAR" background="yellow"/>
  </Choices>

  <TextArea name="notes" toName="text"
            placeholder="Optional: Add notes about this labeling decision"
            rows="2" editable="true"/>
</View>
```

**Option 2: Simple Custom Interface**

`ml/dataset/scripts/label_ui.py`

```python
import pandas as pd
import streamlit as st
import json

st.set_page_config(page_title="Reddit Stress Labeling", layout="wide")

# Load data
if 'posts' not in st.session_state:
    df = pd.read_csv('ml/dataset/raw/unlabeled_posts.csv')
    st.session_state.posts = df.to_dict('records')
    st.session_state.current_idx = 0
    st.session_state.labels = {}

# Progress
total = len(st.session_state.posts)
labeled = len(st.session_state.labels)
st.sidebar.metric("Progress", f"{labeled}/{total}", f"{labeled/total*100:.1f}%")

# Show current post
if st.session_state.current_idx < total:
    post = st.session_state.posts[st.session_state.current_idx]

    st.header(f"Post {st.session_state.current_idx + 1}/{total}")
    st.subheader(f"r/{post['subreddit']} - {post['score']} points")

    st.markdown(f"**Title:** {post['title']}")
    st.markdown(f"**Body:**\n\n{post['body']}")

    col1, col2, col3 = st.columns(3)

    if col1.button("😰 STRESS", use_container_width=True):
        st.session_state.labels[post['post_id']] = 'STRESS'
        st.session_state.current_idx += 1
        st.rerun()

    if col2.button("✅ NON-STRESS", use_container_width=True):
        st.session_state.labels[post['post_id']] = 'NON_STRESS'
        st.session_state.current_idx += 1
        st.rerun()

    if col3.button("❓ SKIP", use_container_width=True):
        st.session_state.current_idx += 1
        st.rerun()

    # Save progress
    if st.sidebar.button("💾 Save Progress"):
        with open('ml/dataset/labels.json', 'w') as f:
            json.dump(st.session_state.labels, f)
        st.sidebar.success("Saved!")

else:
    st.success("All posts labeled!")
    st.balloons()
```

**Run:**
```bash
pip install streamlit
streamlit run ml/dataset/scripts/label_ui.py
```

---

### Subtask 018.4: Pilot Labeling Round

**Estimate:** 2 hours

**Description:**
- Label 100 posts as pilot
- Calculate initial inter-annotator agreement
- Refine guidelines based on confusion
- **[USER TASK]** Complete pilot labeling

**Acceptance Criteria:**
- 100 posts labeled by 2+ annotators
- Agreement calculated
- Guidelines refined if needed
- Ready for full labeling

**Create Pilot Set:**
```python
# Extract 100 random posts for pilot
import pandas as pd
import random

df = pd.read_csv('ml/dataset/raw/unlabeled_posts.csv')
pilot = df.sample(n=100, random_state=42)
pilot.to_csv('ml/dataset/raw/pilot_set.csv', index=False)
```

**Calculate Agreement:**
```python
from sklearn.metrics import cohen_kappa_score

def calculate_agreement(labels_annotator1, labels_annotator2):
    """Calculate Cohen's Kappa"""
    kappa = cohen_kappa_score(labels_annotator1, labels_annotator2)
    print(f"Cohen's Kappa: {kappa:.3f}")

    if kappa > 0.8:
        print("✓ Excellent agreement")
    elif kappa > 0.6:
        print("⚠ Moderate agreement - review guidelines")
    else:
        print("✗ Poor agreement - revise guidelines")

    return kappa
```

---

### Subtask 018.5: Full Dataset Labeling

**Estimate:** 16-20 hours (spread across multiple annotators)

**Description:**
- Recruit 2-3 annotators (ideally with psychology/mental health background)
- Distribute posts among annotators
- Monitor labeling progress
- **[USER TASK]** Complete full dataset labeling (primary user task)

**Acceptance Criteria:**
- All posts labeled
- Quality checks passed
- Annotator fatigue monitored
- Progress tracked

**Annotation Strategy:**

**Option A: Full Overlap (Higher Quality, More Time)**
- Each post labeled by all annotators
- Resolve disagreements through discussion
- Best for critical applications

**Option B: Partial Overlap (Balanced)**
- 20% posts labeled by all annotators (for quality check)
- 80% posts labeled by single annotator
- Review disagreements on overlapped posts

**Option C: Crowdsourcing (Faster, Lower Cost)**
- Use Amazon Mechanical Turk, Scale AI, or similar
- Each post labeled by 3 workers
- Use majority vote
- Require qualification test

**Quality Monitoring:**
```python
# Track labeling progress
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt

def monitor_labeling_progress():
    labels = pd.read_csv('ml/dataset/labeled/labels.csv')

    print(f"Total labeled: {len(labels)}")
    print(f"Label distribution: {Counter(labels['label'])}")

    # Check for annotator bias
    if 'annotator' in labels.columns:
        by_annotator = labels.groupby(['annotator', 'label']).size().unstack()
        print("\nLabels by annotator:")
        print(by_annotator)

    # Plot progress over time
    labels['timestamp'] = pd.to_datetime(labels['timestamp'])
    labels.set_index('timestamp').resample('1H')['post_id'].count().plot()
    plt.title("Labeling Progress Over Time")
    plt.ylabel("Posts Labeled")
    plt.show()
```

---

### Subtask 018.6: Calculate Inter-Annotator Agreement

**Estimate:** 1 hour

**Description:**
- Calculate Cohen's Kappa on overlapped annotations
- Identify systematic disagreements
- Document agreement metrics

**Acceptance Criteria:**
- Kappa >0.8 achieved
- Disagreements analyzed
- Metrics documented

**Files to Create:**
`ml/dataset/scripts/calculate_agreement.py`

```python
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix
import numpy as np

def load_annotations(file1, file2):
    """Load annotations from two annotators"""
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    # Merge on post_id
    merged = df1.merge(df2, on='post_id', suffixes=('_1', '_2'))

    return merged['label_1'].values, merged['label_2'].values

def calculate_metrics(labels1, labels2):
    """Calculate agreement metrics"""
    # Cohen's Kappa
    kappa = cohen_kappa_score(labels1, labels2)

    # Percent agreement
    agreement = np.mean(labels1 == labels2)

    # Confusion matrix
    cm = confusion_matrix(labels1, labels2)

    print(f"Cohen's Kappa: {kappa:.3f}")
    print(f"Percent Agreement: {agreement*100:.1f}%")
    print(f"\nConfusion Matrix:")
    print(cm)

    return kappa, agreement, cm

def find_disagreements(file1, file2, output_file):
    """Find and export disagreements for review"""
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    merged = df1.merge(df2, on='post_id', suffixes=('_1', '_2'))
    disagreements = merged[merged['label_1'] != merged['label_2']]

    print(f"Found {len(disagreements)} disagreements ({len(disagreements)/len(merged)*100:.1f}%)")

    disagreements.to_csv(output_file, index=False)
    return disagreements

if __name__ == "__main__":
    labels1, labels2 = load_annotations(
        'ml/dataset/labeled/annotator1.csv',
        'ml/dataset/labeled/annotator2.csv'
    )

    kappa, agreement, cm = calculate_metrics(labels1, labels2)

    find_disagreements(
        'ml/dataset/labeled/annotator1.csv',
        'ml/dataset/labeled/annotator2.csv',
        'ml/dataset/labeled/disagreements.csv'
    )
```

---

### Subtask 018.7: Resolve Disagreements

**Estimate:** 3 hours

**Description:**
- Review all disagreements
- Discuss with annotators
- Reach consensus labels
- **[USER TASK]** Adjudicate disagreements

**Acceptance Criteria:**
- All disagreements resolved
- Consensus labels recorded
- Process documented

**Adjudication Process:**
1. Review each disagreement
2. Re-read labeling guidelines
3. Discuss with annotators
4. Reach consensus (or use majority vote if 3+ annotators)
5. Document reasoning for difficult cases

---

### Subtask 018.8: Data Quality Checks

**Estimate:** 2 hours

**Description:**
- Check for labeling errors (e.g., all same label)
- Validate data integrity
- Remove low-quality posts if necessary
- Verify minimum text length

**Acceptance Criteria:**
- Quality checks passed
- Errors corrected
- Dataset cleaned

**Quality Check Script:**
`ml/dataset/scripts/quality_checks.py`

```python
import pandas as pd
import numpy as np

def run_quality_checks(labels_file):
    """Run comprehensive quality checks"""
    df = pd.read_csv(labels_file)

    print("=" * 60)
    print("DATASET QUALITY CHECKS")
    print("=" * 60)

    # Check 1: Total count
    print(f"\n1. Total labeled posts: {len(df)}")
    assert len(df) >= 10000, "❌ Insufficient labels (<10k)"
    print("   ✓ Pass")

    # Check 2: Class balance
    label_dist = df['label'].value_counts()
    print(f"\n2. Label distribution:")
    for label, count in label_dist.items():
        pct = count / len(df) * 100
        print(f"   {label}: {count} ({pct:.1f}%)")

    stress_ratio = label_dist.get('STRESS', 0) / len(df)
    assert 0.4 <= stress_ratio <= 0.6, "❌ Imbalanced classes"
    print("   ✓ Pass (balanced)")

    # Check 3: Missing values
    missing = df.isnull().sum()
    print(f"\n3. Missing values:")
    print(missing)
    assert df['label'].isnull().sum() == 0, "❌ Missing labels"
    print("   ✓ Pass")

    # Check 4: Text length
    df['text_length'] = df['text'].str.len()
    print(f"\n4. Text length statistics:")
    print(f"   Min: {df['text_length'].min()}")
    print(f"   Median: {df['text_length'].median()}")
    print(f"   Max: {df['text_length'].max()}")

    # Remove very short posts
    too_short = df[df['text_length'] < 10]
    if len(too_short) > 0:
        print(f"   ⚠ Warning: {len(too_short)} posts <10 chars")

    # Check 5: Duplicates
    duplicates = df.duplicated(subset=['text']).sum()
    print(f"\n5. Duplicate texts: {duplicates}")
    if duplicates > 0:
        print(f"   ⚠ Warning: Found {duplicates} duplicates")

    # Check 6: Subreddit distribution
    print(f"\n6. Subreddit distribution:")
    subreddit_dist = df['subreddit'].value_counts()
    for subreddit, count in subreddit_dist.items():
        print(f"   r/{subreddit}: {count}")

    print("\n" + "=" * 60)
    print("QUALITY CHECKS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    run_quality_checks('ml/dataset/labeled/final_labels.csv')
```

---

### Subtask 018.9: Balance Dataset

**Estimate:** 1 hour

**Description:**
- Ensure 50/50 class distribution
- Oversample or undersample as needed
- Maintain diversity across subreddits

**Acceptance Criteria:**
- Balanced class distribution (45-55% each class)
- Diversity maintained
- Final count: 10,000+ posts

**Balancing Script:**
```python
import pandas as pd
from sklearn.utils import resample

def balance_dataset(input_file, output_file, target_size=10000):
    """Balance dataset to 50/50 class distribution"""
    df = pd.read_csv(input_file)

    # Separate by class
    stress = df[df['label'] == 'STRESS']
    non_stress = df[df['label'] == 'NON_STRESS']

    print(f"Original distribution:")
    print(f"  STRESS: {len(stress)}")
    print(f"  NON_STRESS: {len(non_stress)}")

    # Target: target_size/2 of each class
    target_per_class = target_size // 2

    # Resample
    if len(stress) > target_per_class:
        stress = resample(stress, n_samples=target_per_class, random_state=42)
    else:
        stress = resample(stress, n_samples=target_per_class, replace=True, random_state=42)

    if len(non_stress) > target_per_class:
        non_stress = resample(non_stress, n_samples=target_per_class, random_state=42)
    else:
        non_stress = resample(non_stress, n_samples=target_per_class, replace=True, random_state=42)

    # Combine
    balanced = pd.concat([stress, non_stress])
    balanced = balanced.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"\nBalanced distribution:")
    print(f"  STRESS: {len(balanced[balanced['label'] == 'STRESS'])}")
    print(f"  NON_STRESS: {len(balanced[balanced['label'] == 'NON_STRESS'])}")
    print(f"  Total: {len(balanced)}")

    balanced.to_csv(output_file, index=False)
    return balanced

if __name__ == "__main__":
    balance_dataset(
        'ml/dataset/labeled/final_labels.csv',
        'ml/dataset/processed/balanced_dataset.csv',
        target_size=10000
    )
```

---

### Subtask 018.10: Train/Val/Test Split

**Estimate:** 30 minutes

**Description:**
- Split dataset: 70% train, 15% validation, 15% test
- Ensure stratification by class and subreddit
- Save splits separately

**Acceptance Criteria:**
- Splits created (70/15/15)
- Class balance maintained in each split
- Splits saved and versioned

**Split Script:**
```python
from sklearn.model_selection import train_test_split
import pandas as pd

def create_splits(input_file, output_dir):
    """Create train/val/test splits"""
    df = pd.read_csv(input_file)

    # First split: 70% train, 30% temp
    train, temp = train_test_split(
        df,
        test_size=0.3,
        random_state=42,
        stratify=df['label']
    )

    # Second split: 15% val, 15% test (from 30% temp)
    val, test = train_test_split(
        temp,
        test_size=0.5,
        random_state=42,
        stratify=temp['label']
    )

    print(f"Train: {len(train)} ({len(train)/len(df)*100:.1f}%)")
    print(f"Val:   {len(val)} ({len(val)/len(df)*100:.1f}%)")
    print(f"Test:  {len(test)} ({len(test)/len(df)*100:.1f}%)")

    # Verify class balance in each split
    for name, split in [('train', train), ('val', val), ('test', test)]:
        stress_pct = (split['label'] == 'STRESS').mean() * 100
        print(f"{name} - STRESS: {stress_pct:.1f}%")

    # Save splits
    train.to_csv(f'{output_dir}/train.csv', index=False)
    val.to_csv(f'{output_dir}/val.csv', index=False)
    test.to_csv(f'{output_dir}/test.csv', index=False)

    return train, val, test

if __name__ == "__main__":
    create_splits(
        'ml/dataset/processed/balanced_dataset.csv',
        'ml/dataset/splits'
    )
```

---

### Subtask 018.11: Dataset Versioning

**Estimate:** 1 hour

**Description:**
- Create dataset version metadata
- Use DVC or similar for version control
- Document dataset characteristics

**Acceptance Criteria:**
- Dataset versioned properly
- Metadata documented
- Reproducible

**Create Metadata:**
`ml/dataset/metadata.json`

```json
{
  "dataset_name": "reddit_stress_detection_v1",
  "version": "1.0.0",
  "creation_date": "2024-10-07",
  "total_samples": 10000,
  "splits": {
    "train": 7000,
    "val": 1500,
    "test": 1500
  },
  "class_distribution": {
    "STRESS": 5000,
    "NON_STRESS": 5000
  },
  "subreddit_distribution": {
    "anxiety": 2500,
    "depression": 2500,
    "stress": 2500,
    "mentalhealth": 2500
  },
  "inter_annotator_agreement": {
    "cohens_kappa": 0.85,
    "percent_agreement": 92.5
  },
  "annotators": [
    "annotator_1",
    "annotator_2",
    "annotator_3"
  ],
  "labeling_guidelines_version": "1.0",
  "date_range": {
    "start": "2024-04-01",
    "end": "2024-10-01"
  },
  "source": "reddit_historical_backfill",
  "preprocessing": "none",
  "notes": "Initial dataset for model training. Balanced class distribution."
}
```

**Set up DVC (optional):**
```bash
pip install dvc
dvc init
dvc add ml/dataset/splits/*.csv
git add ml/dataset/splits/*.csv.dvc .dvc/config
git commit -m "Add dataset v1.0.0"
dvc push  # If using remote storage
```

---

### Subtask 018.12: Dataset Documentation

**Estimate:** 2 hours

**Description:**
- Create comprehensive dataset documentation
- Include statistics and visualizations
- Document known limitations

**Acceptance Criteria:**
- Complete documentation
- Statistics included
- Limitations documented

**Files to Create:**
`ml/dataset/README.md`

```markdown
# Reddit Stress Detection Dataset v1.0.0

## Overview
A labeled dataset of 10,000 Reddit posts for binary classification of stress-related content.

## Dataset Statistics
- **Total samples:** 10,000
- **Train:** 7,000 (70%)
- **Validation:** 1,500 (15%)
- **Test:** 1,500 (15%)

## Class Distribution
- **STRESS:** 5,000 (50%)
- **NON_STRESS:** 5,000 (50%)

## Subreddit Distribution
- r/anxiety: 2,500
- r/depression: 2,500
- r/stress: 2,500
- r/mentalhealth: 2,500

## Data Collection
- **Source:** Reddit Historical Backfill (PSAW)
- **Date Range:** April 1, 2024 - October 1, 2024
- **Sampling:** Stratified random sampling across subreddits

## Labeling Process
- **Annotators:** 3 trained annotators
- **Inter-annotator Agreement:** Cohen's Kappa = 0.85
- **Labeling Guidelines:** See LABELING_GUIDELINES.md
- **Quality Control:** Pilot round + disagreement adjudication

## Data Fields
- `post_id`: Unique Reddit post ID
- `title`: Post title
- `body`: Post body text
- `text`: Combined title + body
- `subreddit`: Source subreddit
- `created_utc`: Unix timestamp
- `score`: Reddit score
- `num_comments`: Number of comments
- `label`: STRESS or NON_STRESS

## Known Limitations
- Limited to 4 mental health subreddits
- English language only
- 6-month time window
- Potential selection bias toward active users
- Removed [deleted] and very short posts

## Usage
```python
import pandas as pd

train = pd.read_csv('splits/train.csv')
val = pd.read_csv('splits/val.csv')
test = pd.read_csv('splits/test.csv')
```

## Citation
If using this dataset, please cite:
```
Reddit Stress Detection Dataset v1.0.0
Created: 2024-10-07
Source: Reddit via PSAW
```

## License
For research and educational purposes only.
```

---

## Rollback Plan

If dataset issues are found:

1. **Revert to previous version:**
   ```bash
   git checkout HEAD~1 ml/dataset/
   # Or use DVC
   dvc checkout ml/dataset/splits/*.csv
   ```

2. **Re-label problematic posts:**
   - Identify issues
   - Re-extract and re-label
   - Merge with existing labeled data

3. **Adjust sampling strategy:**
   - Extract new sample
   - Repeat labeling process

---

## Testing Checklist

- [ ] 15k+ posts extracted from Cassandra
- [ ] Labeling guidelines created and reviewed
- [ ] Labeling platform set up and tested
- [ ] Pilot round completed (100 posts)
- [ ] Inter-annotator agreement >0.8 on pilot
- [ ] Full dataset labeled (10k+)
- [ ] Inter-annotator agreement >0.8 on full set
- [ ] Disagreements resolved
- [ ] Quality checks passed
- [ ] Dataset balanced (50/50)
- [ ] Train/val/test splits created (70/15/15)
- [ ] Dataset versioned
- [ ] Metadata documented
- [ ] README complete
- [ ] Known limitations documented

---

## Dependencies

**Required before starting:**
- TASK-010: Historical Backfill (provides data)
- Cassandra populated with posts

**Blocks:**
- TASK-019: Model Selection & Fine-Tuning

---

## Notes

- Labeling is time-consuming; budget 20-30 hours of annotator time
- Consider annotator mental health when labeling distressing content
- Inter-annotator agreement should be calculated on overlapping subset
- Dataset size can be increased later if model performance is insufficient
- Keep raw unlabeled data for future labeling
- Document all preprocessing decisions
- Save intermediate results frequently

---

## Estimated Completion

**Total Time:** 24-30 hours (3 days, with multiple annotators in parallel)

**Breakdown:**
- Data extraction: 2 hours
- Guidelines & setup: 4 hours
- Pilot labeling: 2 hours
- Full labeling: 16-20 hours (parallelized across annotators)
- Quality checks & processing: 4 hours
- Documentation: 2 hours
