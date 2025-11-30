#!/usr/bin/env python3
"""
LDA Topic Modeling for Vietnamese Stress Posts

Extracts top 10 mental health characteristics from Vietnamese posts in Cassandra.
Reads directly from Kafka → Cassandra pipeline.
Uses gensim for LDA and Vietnamese text preprocessing.
"""

import json
from pathlib import Path
from gensim import corpora, models
from gensim.parsing.preprocessing import preprocess_string, strip_punctuation, strip_numeric
from cassandra.cluster import Cluster
import re

OUTPUT_FILE = "ml/lda/mental_health_topics.json"
NUM_TOPICS = 10

# Vietnamese stopwords (common words to ignore)
VIETNAMESE_STOPWORDS = {
    'và', 'của', 'cho', 'là', 'có', 'này', 'được', 'với', 'để', 'đã', 'trong',
    'một', 'các', 'những', 'khi', 'không', 'từ', 'cũng', 'rất', 'thì', 'như',
    'trên', 'bởi', 'vì', 'về', 'vào', 'ra', 'tôi', 'bạn', 'mình', 'của', 'ở',
    'nếu', 'sẽ', 'đang', 'lúc', 'nào', 'gì', 'ai', 'đó', 'họ', 'chúng'
}

def preprocess_vietnamese_text(text):
    """Preprocess Vietnamese text for LDA."""
    # Lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r'http\S+|www\S+', '', text)

    # Remove special characters but keep Vietnamese diacritics
    text = re.sub(r'[^\w\s\u00C0-\u024F\u1E00-\u1EFF]', ' ', text)

    # Remove numbers
    text = re.sub(r'\d+', '', text)

    # Remove extra whitespace
    text = ' '.join(text.split())

    # Tokenize and remove stopwords
    tokens = text.split()
    tokens = [w for w in tokens if w not in VIETNAMESE_STOPWORDS and len(w) > 2]

    return tokens

def fetch_posts_from_cassandra():
    """Fetch vozforums stress posts from Cassandra for ABSA aspect extraction."""
    print("Connecting to Cassandra...")
    cluster = Cluster(['localhost'], port=9042)
    session = cluster.connect('reddit_rt')

    print("Fetching vozforums stress posts from raw_posts_by_day...")
    # Note: Using ALLOW FILTERING for subreddit filter
    query = "SELECT title, body FROM raw_posts_by_day WHERE subreddit='vozforums' ALLOW FILTERING;"
    rows = session.execute(query)

    texts = []
    for row in rows:
        text = ''
        if row.title:
            text += row.title + ' '
        if row.body:
            text += row.body
        if text.strip():
            texts.append(text)

    cluster.shutdown()
    print(f"✓ Fetched {len(texts)} vozforums posts from Cassandra")
    return texts

def extract_topics(num_topics=10):
    """Extract LDA topics from Vietnamese stress posts."""
    print("Loading data from Cassandra...")
    texts = fetch_posts_from_cassandra()

    print("Preprocessing texts...")
    processed_texts = [preprocess_vietnamese_text(text) for text in texts]

    # Filter out empty documents
    processed_texts = [doc for doc in processed_texts if len(doc) > 5]
    print(f"After preprocessing: {len(processed_texts)} documents")

    # Create dictionary and corpus
    print("Creating dictionary and corpus...")
    dictionary = corpora.Dictionary(processed_texts)

    # Filter extremes
    dictionary.filter_extremes(no_below=5, no_above=0.5, keep_n=2000)

    corpus = [dictionary.doc2bow(doc) for doc in processed_texts]

    # Train LDA model (use LdaModel for auto alpha/eta)
    print(f"Training LDA model with {num_topics} topics...")
    lda_model = models.LdaModel(
        corpus=corpus,
        id2word=dictionary,
        num_topics=num_topics,
        random_state=42,
        passes=10,
        alpha='auto',
        eta='auto',
        per_word_topics=True
    )

    # Extract topics
    print("\n" + "="*70)
    print(f"Top {num_topics} Mental Health Characteristics")
    print("="*70 + "\n")

    topics_data = []
    for topic_id in range(num_topics):
        topic_words = lda_model.show_topic(topic_id, topn=10)

        # Create topic label from top 3 words
        top_words = [word for word, _ in topic_words[:3]]
        topic_label = "_".join(top_words)

        print(f"Topic {topic_id + 1}: {topic_label}")
        print("  Keywords:", ", ".join([f"{word}({prob:.3f})" for word, prob in topic_words]))
        print()

        topics_data.append({
            'topic_id': topic_id,
            'topic_label': topic_label,
            'keywords': [{'word': word, 'probability': float(prob)} for word, prob in topic_words]
        })

    # Save results
    output_path = Path(OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'num_topics': num_topics,
            'num_documents': len(processed_texts),
            'topics': topics_data
        }, f, ensure_ascii=False, indent=2)

    print("="*70)
    print(f"✓ Results saved to {OUTPUT_FILE}")
    print("="*70)

    # Print coherence score
    from gensim.models.coherencemodel import CoherenceModel
    coherence_model = CoherenceModel(model=lda_model, texts=processed_texts,
                                      dictionary=dictionary, coherence='c_v')
    coherence_score = coherence_model.get_coherence()
    print(f"\nCoherence Score: {coherence_score:.4f}")

    return topics_data

if __name__ == '__main__':
    print("="*70)
    print("PHASE 2: LDA Topic Modeling for ABSA Aspect Extraction")
    print("="*70)
    print()

    topics = extract_topics(NUM_TOPICS)

    print("\n" + "="*70)
    print("✓ PHASE 2 COMPLETE: 10 Mental Health Aspects Extracted")
    print("="*70)
    print(f"\nThese topics will be used as ABSA aspects for multi-label classification.")
    print(f"Each aspect represents a mental health dimension discovered from data.\n")
    print("Next steps:")
    print(f"  1. Review aspects in {OUTPUT_FILE}")
    print("  2. Phase 3: python scripts/prepare_vozforums_dataset.py")
    print("  3. Phase 4: Train PhoBERT multi-label ABSA model")
