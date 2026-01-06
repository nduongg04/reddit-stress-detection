# Training Data Collection Pipeline

## Overview

This document describes the methodology for collecting and preparing Vietnamese mental health training data from Reddit. The pipeline transforms raw social media posts into a labeled dataset suitable for training a stress detection model.

## Data Flow

The training data collection follows a six-phase pipeline:

1. **Raw Data Collection** - Gather Vietnamese posts from Reddit forums
2. **Data Storage** - Persist posts through message queue to database
3. **Data Export** - Extract relevant posts to structured format
4. **Topic Discovery** - Identify mental health themes using statistical modeling
5. **Automated Labeling** - Classify posts using large language model
6. **Dataset Preparation** - Create balanced train/validation/test splits

## Phase 1: Raw Data Collection

### Source Selection

The primary data source is the Vietnamese Reddit community r/vozforums, selected for:
- High volume of Vietnamese language content
- Active discussions about personal experiences
- Presence of stress-related conversations

### Collection Strategy

The system employs keyword-based search to identify potentially stress-related posts. A curated list of 34 Vietnamese stress-related keywords guides the collection, including terms related to:
- Psychological states (anxiety, depression, stress)
- Work pressures (deadlines, workload, burnout)
- Relationship difficulties (conflicts, breakups)
- Life challenges (financial problems, failures)

### Language Validation

Each post undergoes strict Vietnamese language verification through four criteria:
1. Language detection algorithm identifies Vietnamese
2. Presence of Vietnamese diacritical marks (tonal markers)
3. Limited English word ratio (under 50%)
4. Minimum Vietnamese character density (5% diacritics)

This filtering ensures high-quality Vietnamese content and eliminates mixed-language or misclassified posts.

### Rate Management

The collection respects Reddit API limitations:
- Maximum 100 requests per minute sustained rate
- 10-minute averaging window for rate calculation
- Adaptive throttling based on API response headers

## Phase 2: Data Storage

### Message Queue Architecture

Collected posts flow through a message queue system before storage:
- Posts are serialized with standardized schema
- Each post receives a unique correlation identifier for tracing
- Failed messages route to a dead letter queue for later recovery

### Database Persistence

Posts are stored with the following attributes:
- Unique post identifier
- Title and body content
- Source subreddit and author
- Timestamp and engagement metrics
- Search keyword that matched the post

## Phase 3: Data Export

The export process extracts Vietnamese posts from the database:
- Queries posts from a configurable time window (default: 14 days)
- Filters by Vietnamese keyword categories
- Removes duplicate entries
- Outputs structured tabular format for downstream processing

## Phase 4: Topic Discovery

### Latent Dirichlet Allocation

The system applies Latent Dirichlet Allocation (LDA) to discover underlying mental health themes within the collected posts. This unsupervised approach:

1. **Text Preprocessing**
   - Converts text to lowercase
   - Removes URLs and special characters
   - Tokenizes Vietnamese text
   - Filters Vietnamese stopwords
   - Applies minimum word length threshold

2. **Topic Modeling**
   - Trains LDA model with 10 topics
   - Extracts top keywords per topic
   - Generates human-readable topic labels
   - Calculates model coherence score

3. **Output**
   - 10 distinct mental health aspects
   - Each aspect defined by characteristic keywords
   - Topics serve as classification targets for multi-label annotation

## Phase 5: Automated Labeling

### Large Language Model Annotation

The system leverages a large language model to automatically label posts with the discovered mental health aspects:

1. **Prompt Construction**
   - Vietnamese-language prompt describing the classification task
   - Post content included for analysis
   - List of 10 mental health aspects from LDA results

2. **Classification**
   - Model identifies relevant aspects for each post
   - Returns confidence score for annotation quality
   - Supports multi-label classification (posts may exhibit multiple aspects)

3. **Output Format**
   - Binary indicators for each of 10 aspects
   - Confidence score for quality filtering

## Phase 6: Dataset Preparation

### Balancing Strategy

To create a balanced training dataset:
- Select 200 stress-positive posts from collected data
- Select 200 stress-negative posts (filtered to exclude stress keywords)
- Total: 400 labeled examples

### Data Splitting

The dataset divides into three partitions:
- **Training set**: 70% (280 posts) - Model learning
- **Validation set**: 15% (60 posts) - Hyperparameter tuning
- **Test set**: 15% (60 posts) - Final evaluation

### Text Preparation

Each example combines title and body into a single text field, suitable for transformer model input.

## Model Training

The prepared dataset trains a Vietnamese language model:
- Base model: Vietnamese PhoBERT (135 million parameters)
- Fine-tuning approach with focal loss for handling class imbalance
- Data augmentation techniques for Vietnamese text
- Early stopping to prevent overfitting

## Summary

This pipeline transforms raw Vietnamese Reddit posts into a curated, balanced dataset through systematic collection, topic discovery, and automated labeling. The resulting dataset enables training stress detection models specifically tuned for Vietnamese language and cultural context.
