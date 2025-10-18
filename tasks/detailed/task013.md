# TASK-013: Text Cleaning Pipeline

**Owner:** ML/Spark Engineer
**Priority:** High
**Dependencies:** TASK-004 (Spark Structured Streaming Skeleton)
**Estimate:** 2 days

---

## Overview

Implement a comprehensive text cleaning pipeline in Spark to preprocess Reddit posts and comments for ML model inference. This includes removing URLs, emojis, Markdown formatting, normalizing whitespace, handling Unicode characters, and removing Reddit-specific syntax while maintaining semantic meaning.

---

## Subtasks

### Subtask 013.1: Text Cleaning Requirements Analysis

**Estimate:** 30 minutes

**Description:**
- Analyze Reddit text patterns and edge cases
- Define cleaning rules
- Document expected transformations

**Acceptance Criteria:**
- Cleaning rules documented
- Edge cases identified
- Example transformations documented

**Example Reddit Text Patterns:**
```text
# Input samples:
1. "Check out this link: https://example.com/article u/username r/subreddit"
2. "I'm feeling 😢😭 so stressed **right now**"
3. "```code block here``` and some ~strikethrough~ text"
4. "[deleted]" and "[removed]" content
5. "¯\\_(ツ)_/¯ and other Unicode art"
6. "Multiple    spaces   and\n\nnewlines"

# Expected outputs:
1. "Check out this link"
2. "I'm feeling so stressed right now"
3. "and some text"
4. "" (empty or filtered)
5. "and other Unicode art"
6. "Multiple spaces and newlines"
```

---

### Subtask 013.2: URL Removal Function

**Estimate:** 45 minutes

**Description:**
- Implement regex-based URL detection and removal
- Handle various URL formats (http, https, www, shortened URLs)
- Test with edge cases

**Acceptance Criteria:**
- All URL formats removed
- Text structure preserved
- Edge cases handled

**Files to Create:**
- `spark/streaming_job/src/text_cleaning/url_cleaner.py`

**Implementation:**
```python
import re
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

def remove_urls(text):
    """
    Remove URLs from text using regex patterns
    """
    if not text:
        return text

    # Pattern for URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    # Pattern for www URLs without protocol
    www_pattern = r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    # Pattern for shortened URLs (bit.ly, t.co, etc.)
    short_url_pattern = r'\b(?:bit\.ly|t\.co|tinyurl\.com|goo\.gl)/[a-zA-Z0-9]+'

    # Remove all URL patterns
    text = re.sub(url_pattern, '', text)
    text = re.sub(www_pattern, '', text)
    text = re.sub(short_url_pattern, '', text)

    return text

# Create Spark UDF
remove_urls_udf = udf(remove_urls, StringType())
```

**Unit Tests:**
```python
def test_remove_urls():
    test_cases = [
        ("Check https://example.com out", "Check  out"),
        ("Visit www.reddit.com today", "Visit  today"),
        ("Link: bit.ly/abc123", "Link: "),
        ("No URLs here", "No URLs here"),
        ("Multiple https://test1.com and https://test2.com", "Multiple  and ")
    ]

    for input_text, expected in test_cases:
        result = remove_urls(input_text)
        assert result == expected, f"Failed for: {input_text}"
```

---

### Subtask 013.3: Emoji Removal Function

**Estimate:** 1 hour

**Description:**
- Implement emoji detection using Unicode ranges
- Remove all emojis while preserving text
- Handle emoji variations and skin tones

**Acceptance Criteria:**
- All emojis removed correctly
- Text spacing maintained
- Performance acceptable

**Implementation:**
```python
import emoji
import re

def remove_emojis(text):
    """
    Remove emojis from text using Unicode ranges
    """
    if not text:
        return text

    # Using emoji library for comprehensive removal
    text = emoji.replace_emoji(text, replace='')

    # Additional emoji patterns (Unicode ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "]+",
        flags=re.UNICODE
    )

    text = emoji_pattern.sub(r'', text)

    return text

remove_emojis_udf = udf(remove_emojis, StringType())
```

**Unit Tests:**
```python
def test_remove_emojis():
    test_cases = [
        ("Hello 😊 world 🌍", "Hello  world "),
        ("Feeling 😢😭😰", "Feeling "),
        ("No emojis here", "No emojis here"),
        ("Mixed 😊 text 🎉 content 🔥", "Mixed  text  content ")
    ]

    for input_text, expected in test_cases:
        result = remove_emojis(input_text)
        assert result == expected, f"Failed for: {input_text}"
```

---

### Subtask 013.4: Markdown Formatting Removal

**Estimate:** 1.5 hours

**Description:**
- Remove Markdown syntax (bold, italic, strikethrough, code blocks)
- Preserve text content
- Handle nested formatting

**Acceptance Criteria:**
- All Markdown removed
- Content preserved
- Nested formatting handled

**Implementation:**
```python
def remove_markdown(text):
    """
    Remove Markdown formatting from text
    """
    if not text:
        return text

    # Remove code blocks (``` or `)
    text = re.sub(r'```[^`]*```', '', text)
    text = re.sub(r'`[^`]*`', '', text)

    # Remove bold and italic (**, __, *, _)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'__([^_]+)__', r'\1', text)      # __bold__
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
    text = re.sub(r'_([^_]+)_', r'\1', text)        # _italic_

    # Remove strikethrough (~~)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)

    # Remove headers (# ## ###)
    text = re.sub(r'#{1,6}\s*', '', text)

    # Remove quotes (>)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # Remove horizontal rules (---, ***)
    text = re.sub(r'^[-*]{3,}$', '', text, flags=re.MULTILINE)

    # Remove list markers (-, *, 1.)
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    return text

remove_markdown_udf = udf(remove_markdown, StringType())
```

---

### Subtask 013.5: Reddit-Specific Syntax Removal

**Estimate:** 1 hour

**Description:**
- Remove Reddit usernames (u/username)
- Remove subreddit references (r/subreddit)
- Remove Reddit awards and formatting
- Filter [deleted] and [removed] content

**Acceptance Criteria:**
- Reddit syntax removed
- Deleted content filtered
- Text readable

**Implementation:**
```python
def remove_reddit_syntax(text):
    """
    Remove Reddit-specific syntax
    """
    if not text:
        return text

    # Check for deleted/removed content
    if text.strip().lower() in ['[deleted]', '[removed]', '[removed by reddit]']:
        return ''

    # Remove username mentions (u/username)
    text = re.sub(r'u/[\w-]+', '', text)

    # Remove subreddit references (r/subreddit)
    text = re.sub(r'r/[\w-]+', '', text)

    # Remove Reddit awards text
    text = re.sub(r'\[.*?\s*award.*?\]', '', text, flags=re.IGNORECASE)

    # Remove "Edit:" lines (common in Reddit posts)
    text = re.sub(r'Edit\s*\d*\s*:', '', text, flags=re.IGNORECASE)

    # Remove "Update:" lines
    text = re.sub(r'Update\s*\d*\s*:', '', text, flags=re.IGNORECASE)

    return text

remove_reddit_syntax_udf = udf(remove_reddit_syntax, StringType())
```

---

### Subtask 013.6: Whitespace Normalization

**Estimate:** 45 minutes

**Description:**
- Normalize multiple spaces to single space
- Remove leading/trailing whitespace
- Handle various whitespace characters (tabs, newlines)

**Acceptance Criteria:**
- Consistent whitespace
- Text trimmed properly
- Performance optimized

**Implementation:**
```python
def normalize_whitespace(text):
    """
    Normalize whitespace in text
    """
    if not text:
        return text

    # Replace tabs with spaces
    text = text.replace('\t', ' ')

    # Replace multiple newlines with single newline
    text = re.sub(r'\n+', '\n', text)

    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)

    # Replace newlines with spaces (for model input)
    text = text.replace('\n', ' ')

    # Strip leading/trailing whitespace
    text = text.strip()

    return text

normalize_whitespace_udf = udf(normalize_whitespace, StringType())
```

---

### Subtask 013.7: Unicode Normalization

**Estimate:** 1 hour

**Description:**
- Normalize Unicode characters to NFC form
- Handle special characters and accents
- Remove non-printable characters

**Acceptance Criteria:**
- Unicode normalized consistently
- Special characters handled
- Non-printable characters removed

**Implementation:**
```python
import unicodedata

def normalize_unicode(text):
    """
    Normalize Unicode characters
    """
    if not text:
        return text

    # Normalize to NFC (Canonical Decomposition, followed by Canonical Composition)
    text = unicodedata.normalize('NFC', text)

    # Remove non-printable characters
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\r\t')

    # Remove zero-width characters
    zero_width_chars = [
        '\u200b',  # Zero width space
        '\u200c',  # Zero width non-joiner
        '\u200d',  # Zero width joiner
        '\ufeff',  # Zero width no-break space
    ]
    for char in zero_width_chars:
        text = text.replace(char, '')

    return text

normalize_unicode_udf = udf(normalize_unicode, StringType())
```

---

### Subtask 013.8: Text Length Validation

**Estimate:** 30 minutes

**Description:**
- Filter out very short texts (< 10 characters)
- Filter out very long texts (> 10000 characters)
- Add text length metadata

**Acceptance Criteria:**
- Invalid lengths filtered
- Length metadata added
- Thresholds configurable

**Implementation:**
```python
from pyspark.sql.functions import length, col

def add_text_length_validation(df):
    """
    Add text length validation and filtering
    """
    # Add text length column
    df = df.withColumn("text_length", length(col("cleaned_body")))

    # Filter by length (configurable thresholds)
    min_length = 10
    max_length = 10000

    df = df.filter(
        (col("text_length") >= min_length) &
        (col("text_length") <= max_length)
    )

    return df
```

---

### Subtask 013.9: Complete Cleaning Pipeline

**Estimate:** 1.5 hours

**Description:**
- Chain all cleaning functions together
- Create end-to-end cleaning pipeline
- Optimize for performance

**Acceptance Criteria:**
- Pipeline runs efficiently
- All cleaning steps applied
- Performance acceptable (<10ms per post)

**Files to Create:**
- `spark/streaming_job/src/text_cleaning/pipeline.py`

**Implementation:**
```python
from pyspark.sql.functions import col, udf, when
from pyspark.sql.types import StringType
from text_cleaning.url_cleaner import remove_urls
from text_cleaning.emoji_cleaner import remove_emojis
from text_cleaning.markdown_cleaner import remove_markdown
from text_cleaning.reddit_cleaner import remove_reddit_syntax
from text_cleaning.whitespace_cleaner import normalize_whitespace
from text_cleaning.unicode_cleaner import normalize_unicode

def clean_text_field(text):
    """
    Complete text cleaning pipeline for a single text field
    """
    if not text or text.strip() == '':
        return ''

    # Apply cleaning steps in order
    text = remove_reddit_syntax(text)    # Reddit-specific first
    text = remove_urls(text)              # Remove URLs
    text = remove_emojis(text)            # Remove emojis
    text = remove_markdown(text)          # Remove Markdown
    text = normalize_unicode(text)        # Unicode normalization
    text = normalize_whitespace(text)     # Whitespace normalization

    return text

# Create UDF for Spark
clean_text_udf = udf(clean_text_field, StringType())

def apply_text_cleaning_pipeline(df):
    """
    Apply text cleaning pipeline to DataFrame
    Cleans both title and body fields
    """
    # Clean title
    df = df.withColumn(
        "cleaned_title",
        when(col("title").isNotNull(), clean_text_udf(col("title")))
        .otherwise("")
    )

    # Clean body
    df = df.withColumn(
        "cleaned_body",
        when(col("body").isNotNull(), clean_text_udf(col("body")))
        .otherwise("")
    )

    # Combine title and body for model input
    df = df.withColumn(
        "text_for_model",
        when(
            (col("cleaned_title") != "") & (col("cleaned_body") != ""),
            concat(col("cleaned_title"), lit(" "), col("cleaned_body"))
        ).when(
            col("cleaned_title") != "",
            col("cleaned_title")
        ).otherwise(
            col("cleaned_body")
        )
    )

    # Filter empty texts
    df = df.filter(col("text_for_model") != "")

    # Add length validation
    df = add_text_length_validation(df)

    return df
```

---

### Subtask 013.10: Special Character Handling

**Estimate:** 1 hour

**Description:**
- Handle HTML entities (&amp;, &lt;, etc.)
- Remove special ASCII art
- Handle currency symbols

**Acceptance Criteria:**
- HTML entities decoded
- Special characters handled appropriately
- Currency symbols preserved if semantic

**Implementation:**
```python
import html

def handle_special_characters(text):
    """
    Handle special characters and HTML entities
    """
    if not text:
        return text

    # Decode HTML entities
    text = html.unescape(text)

    # Remove common ASCII art delimiters
    ascii_art_patterns = [
        r'¯\\\_\(ツ\)\_/¯',
        r'ಠ_ಠ',
        r'ʘ‿ʘ',
        r'┬─┬',
        r'╯°□°）╯',
    ]
    for pattern in ascii_art_patterns:
        text = re.sub(pattern, '', text)

    # Keep currency symbols but remove excessive ones
    # (single $ or £ might be semantic, multiple are decorative)
    text = re.sub(r'[$£€¥]{2,}', '', text)

    return text

handle_special_characters_udf = udf(handle_special_characters, StringType())
```

---

### Subtask 013.11: Unit Tests for Cleaning Functions

**Estimate:** 2 hours

**Description:**
- Write comprehensive tests for each cleaning function
- Test edge cases
- Measure performance

**Acceptance Criteria:**
- All functions tested
- Edge cases covered
- Performance benchmarks documented

**Files to Create:**
- `spark/streaming_job/tests/test_text_cleaning.py`

**Test Implementation:**
```python
import unittest
from text_cleaning.pipeline import clean_text_field
from text_cleaning.url_cleaner import remove_urls
from text_cleaning.emoji_cleaner import remove_emojis
from text_cleaning.markdown_cleaner import remove_markdown
from text_cleaning.reddit_cleaner import remove_reddit_syntax

class TestTextCleaning(unittest.TestCase):

    def test_url_removal(self):
        test_cases = [
            ("Visit https://example.com today", "Visit  today"),
            ("Check www.test.com", "Check "),
            ("Multiple https://a.com and https://b.com links", "Multiple  and  links")
        ]
        for input_text, expected in test_cases:
            result = remove_urls(input_text)
            self.assertEqual(result.strip(), expected.strip())

    def test_emoji_removal(self):
        text = "I'm so happy 😊😊 today!"
        result = remove_emojis(text)
        self.assertNotIn('😊', result)

    def test_markdown_removal(self):
        text = "This is **bold** and *italic* text"
        result = remove_markdown(text)
        self.assertEqual(result, "This is bold and italic text")

    def test_reddit_syntax(self):
        test_cases = [
            ("Check out u/testuser post", "Check out  post"),
            ("Posted in r/testsubreddit", "Posted in "),
            ("[deleted]", ""),
            ("[removed]", "")
        ]
        for input_text, expected in test_cases:
            result = remove_reddit_syntax(input_text)
            self.assertEqual(result.strip(), expected.strip())

    def test_complete_pipeline(self):
        complex_text = """
        **Check this out!** 😊
        Visit https://example.com or u/testuser
        Posted in r/test
        ```code block```
        Multiple    spaces   here
        """

        result = clean_text_field(complex_text)

        # Verify no Markdown, emojis, URLs, Reddit syntax
        self.assertNotIn('**', result)
        self.assertNotIn('😊', result)
        self.assertNotIn('https://', result)
        self.assertNotIn('u/', result)
        self.assertNotIn('r/', result)
        self.assertNotIn('```', result)

        # Verify no multiple spaces
        self.assertNotIn('  ', result)

    def test_empty_and_null_handling(self):
        self.assertEqual(clean_text_field(None), '')
        self.assertEqual(clean_text_field(''), '')
        self.assertEqual(clean_text_field('   '), '')
        self.assertEqual(clean_text_field('[deleted]'), '')

    def test_unicode_normalization(self):
        text = "café résumé naïve"
        result = clean_text_field(text)
        # Should preserve accented characters but normalize form
        self.assertIn('café', result)

if __name__ == '__main__':
    unittest.main()
```

---

### Subtask 013.12: Performance Testing

**Estimate:** 1 hour

**Description:**
- Benchmark cleaning pipeline performance
- Measure latency per post
- Optimize bottlenecks
- **[USER TASK]** Verify performance meets requirements (<10ms per post)

**Acceptance Criteria:**
- Performance measured
- Bottlenecks identified
- Optimization applied
- Performance meets target

**Benchmark Script:**
```python
import time
from pyspark.sql import SparkSession

def benchmark_text_cleaning(spark, num_records=10000):
    """
    Benchmark text cleaning pipeline
    """
    # Generate test data with realistic Reddit text
    test_data = spark.createDataFrame([
        (i, f"**Title {i}** from u/user{i}",
         f"This is a test post 😊 with https://example.com links in r/test. "
         f"Multiple    spaces and ```code blocks``` here.")
        for i in range(num_records)
    ], ["id", "title", "body"])

    # Measure cleaning time
    start_time = time.time()

    cleaned_data = apply_text_cleaning_pipeline(test_data)
    cleaned_count = cleaned_data.count()  # Force evaluation

    end_time = time.time()
    duration = end_time - start_time

    # Calculate metrics
    posts_per_second = num_records / duration
    latency_per_post_ms = (duration / num_records) * 1000

    print(f"\nText Cleaning Performance:")
    print(f"  Records processed: {num_records}")
    print(f"  Duration: {duration:.2f} seconds")
    print(f"  Throughput: {posts_per_second:.2f} posts/sec")
    print(f"  Latency per post: {latency_per_post_ms:.3f} ms")

    return {
        'throughput': posts_per_second,
        'latency_ms': latency_per_post_ms
    }
```

---

### Subtask 013.13: Integration with Streaming Pipeline

**Estimate:** 1 hour

**Description:**
- Integrate text cleaning into Spark streaming job
- Add before model inference step
- Test with live data stream

**Acceptance Criteria:**
- Cleaning integrated correctly
- No pipeline disruption
- Performance acceptable

**Files to Update:**
- `spark/streaming_job/src/main.py`

**Integration:**
```python
from text_cleaning.pipeline import apply_text_cleaning_pipeline

def main():
    # ... existing code ...

    # Read from Kafka
    parsed_df = kafka_df.select(
        from_json(col("value").cast("string"), kafka_schema).alias("data")
    ).select("data.*")

    # Apply text cleaning
    cleaned_df = apply_text_cleaning_pipeline(parsed_df)

    # TODO: Apply model inference here
    # For now, write cleaned data to Cassandra
    query = write_stream_to_cassandra(cleaned_df, cassandra_writer)

    query.awaitTermination()
```

---

### Subtask 013.14: Edge Case Testing

**Estimate:** 1.5 hours

**Description:**
- Test with real Reddit data edge cases
- Verify semantic meaning preserved
- Test multilingual content
- **[USER TASK]** Review cleaned text samples for quality

**Acceptance Criteria:**
- Edge cases handled
- Meaning preserved
- Quality acceptable

**Test Cases:**
```python
edge_case_tests = [
    # Very short text
    ("hi", Expected: filtered out),

    # Very long text (> 10000 chars)
    ("a" * 15000, Expected: filtered out),

    # Only emojis
    ("😊😊😊", Expected: filtered out as empty),

    # Code-heavy post
    ("```python\nprint('hello')\n```", Expected: minimal text),

    # Multilingual
    ("Hello world. Bonjour le monde. Hola mundo.", Expected: preserved),

    # ASCII art
    ("¯\\_(ツ)_/¯ I don't know", Expected: "I don't know"),

    # Nested formatting
    ("***Bold italic*** text", Expected: "Bold italic text"),

    # Mixed content
    ("**Title** 😊 https://test.com u/user r/sub", Expected: "Title")
]
```

---

### Subtask 013.15: Documentation

**Estimate:** 1 hour

**Description:**
- Document text cleaning pipeline
- Add examples of transformations
- Document configuration options

**Acceptance Criteria:**
- Pipeline documented
- Examples provided
- Configuration explained

**Files to Create:**
- `spark/streaming_job/docs/text_cleaning.md`

---

### Subtask 013.16: Monitoring and Metrics

**Estimate:** 45 minutes

**Description:**
- Add metrics for cleaning pipeline
- Track cleaning success rate
- Monitor text length distributions

**Acceptance Criteria:**
- Metrics collected
- Success rate tracked
- Distributions monitored

**Metrics:**
```python
from prometheus_client import Counter, Histogram

text_cleaning_processed = Counter(
    'text_cleaning_processed_total',
    'Total texts processed'
)

text_cleaning_filtered = Counter(
    'text_cleaning_filtered_total',
    'Texts filtered out',
    ['reason']
)

text_length_distribution = Histogram(
    'text_cleaning_length_chars',
    'Distribution of cleaned text lengths',
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
)
```

---

### Subtask 013.17: Final Verification

**Estimate:** 1 hour

**Description:**
- Test pipeline with 10k+ real Reddit posts
- Verify cleaning quality
- Check performance metrics
- **[USER TASK]** Review sample cleaned texts

**Acceptance Criteria:**
- Pipeline processes all posts successfully
- Cleaning quality acceptable
- Performance meets requirements
- No errors or crashes

---

## Rollback Plan

If text cleaning causes issues:

1. **Disable specific cleaning steps:**
   ```python
   # Comment out problematic steps
   # text = remove_markdown(text)
   ```

2. **Revert to basic cleaning:**
   ```python
   def basic_clean(text):
       return text.strip() if text else ''
   ```

3. **Bypass cleaning temporarily:**
   ```python
   df = df.withColumn("text_for_model", col("body"))
   ```

---

## Testing Checklist

- [ ] URL removal works correctly
- [ ] Emoji removal complete
- [ ] Markdown formatting removed
- [ ] Reddit syntax removed
- [ ] Whitespace normalized
- [ ] Unicode normalized
- [ ] HTML entities decoded
- [ ] Text length validation works
- [ ] Empty texts filtered
- [ ] Performance meets target (<10ms/post)
- [ ] Edge cases handled
- [ ] Semantic meaning preserved
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Documentation complete

---

## Dependencies

**Required before starting:**
- TASK-004: Spark streaming skeleton

**Blocks:**
- TASK-014: End-to-End Data Flow Test
- TASK-020: Model Inference Integration

---

## Notes

- Preserve semantic meaning while cleaning
- Balance between thorough cleaning and information retention
- Test with diverse Reddit content
- Consider language-specific cleaning rules
- Monitor false positives (over-cleaning)
- Optimize for performance without sacrificing quality

---

## Estimated Completion

**Total Time:** 16-18 hours (2 days)

**Breakdown:**
- Function Implementation: 8 hours
- Testing & Edge Cases: 5 hours
- Performance Optimization: 3 hours
- Documentation & Integration: 2 hours
