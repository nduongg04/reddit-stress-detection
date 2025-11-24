"""
Vietnamese-specific data augmentation for stress detection training.

Techniques:
1. Synonym replacement using Vietnamese synonym dictionary
2. Word order shuffling (Vietnamese flexible syntax)
3. Punctuation variation
4. Random deletion

Designed to preserve semantic meaning while creating diverse training examples.
"""

import random
import re
from typing import List, Tuple
import pandas as pd

# Vietnamese synonym dictionary for stress-related terms
# Format: {word: [synonym1, synonym2, ...]}
VIETNAMESE_SYNONYMS = {
    # Stress-related
    'căng thẳng': ['áp lực', 'stress', 'lo âu'],
    'áp lực': ['căng thẳng', 'stress', 'gánh nặng'],
    'lo âu': ['lo lắng', 'âu lo', 'bồn chồn', 'căng thẳng'],
    'lo lắng': ['lo âu', 'âu lo', 'bồn chồn'],
    'trầm cảm': ['depression', 'u sầu', 'buồn bã'],
    'mệt mỏi': ['kiệt sức', 'exhausted', 'uể oải'],
    'kiệt sức': ['mệt mỏi', 'burnout', 'cạn kiệt'],
    'suy sụp': ['breakdown', 'đổ vỡ', 'sụp đổ'],
    'sức khỏe tinh thần': ['mental health', 'tâm lý', 'sức khỏe tâm thần'],
    'khủng hoảng': ['crisis', 'khó khăn', 'trục trặc'],

    # Emotion-related
    'buồn': ['buồn bã', 'u sầu', 'sad'],
    'vui': ['vui vẻ', 'hạnh phúc', 'happy'],
    'hạnh phúc': ['vui vẻ', 'sung sướng', 'happy'],
    'tức giận': ['giận dữ', 'bực bội', 'angry'],
    'sợ hãi': ['lo sợ', 'fear', 'hoảng sợ'],

    # Action verbs
    'cảm thấy': ['có cảm giác', 'thấy', 'nhận thấy'],
    'nghĩ': ['suy nghĩ', 'think', 'tưởng'],
    'cần': ['cần phải', 'need', 'thiết phải'],
    'muốn': ['want', 'mong muốn', 'ước'],

    # Common words
    'rất': ['thật', 'thực sự', 'really'],
    'nhiều': ['nhiều lắm', 'a lot', 'thật nhiều'],
    'không': ['ko', 'không có', 'chẳng'],
    'tôi': ['mình', 'em', 'I'],
}

# Common Vietnamese stop words (particles, conjunctions)
VIETNAMESE_STOP_WORDS = {
    'mà', 'và', 'hay', 'hoặc', 'nhưng', 'tuy nhiên', 'thì', 'nên',
    'vì', 'do', 'để', 'cho', 'với', 'của', 'đã', 'sẽ', 'đang',
    'có', 'là', 'được', 'bị', 'rồi', 'nữa', 'thôi'
}

class VietnameseAugmenter:
    """Vietnamese text augmentation for training data."""

    def __init__(self, synonym_dict: dict = None):
        """Initialize augmenter with synonym dictionary."""
        self.synonyms = synonym_dict or VIETNAMESE_SYNONYMS

    def synonym_replacement(self, text: str, n: int = None) -> str:
        """Replace n words with their Vietnamese synonyms.

        Args:
            text: Input text
            n: Number of words to replace (default: 10% of words)

        Returns:
            Augmented text
        """
        words = text.split()
        if len(words) == 0:
            return text

        # Default: replace ~10% of words
        if n is None:
            n = max(1, int(len(words) * 0.1))

        # Find words that have synonyms
        replaceable_indices = []
        for i, word in enumerate(words):
            # Check exact match and lowercase match
            if word in self.synonyms or word.lower() in self.synonyms:
                replaceable_indices.append(i)

        if not replaceable_indices:
            return text

        # Randomly select n words to replace
        n = min(n, len(replaceable_indices))
        indices_to_replace = random.sample(replaceable_indices, n)

        # Replace words
        new_words = words.copy()
        for idx in indices_to_replace:
            word = words[idx]
            # Try exact match first, then lowercase
            synonyms = self.synonyms.get(word) or self.synonyms.get(word.lower())
            if synonyms:
                new_words[idx] = random.choice(synonyms)

        return ' '.join(new_words)

    def random_deletion(self, text: str, p: float = 0.1) -> str:
        """Randomly delete words with probability p, excluding stop words.

        Args:
            text: Input text
            p: Probability of deleting each word

        Returns:
            Augmented text
        """
        words = text.split()
        if len(words) <= 1:
            return text

        # Keep at least 1 word
        new_words = []
        for word in words:
            # Don't delete stop words (preserve grammar)
            if word.lower() in VIETNAMESE_STOP_WORDS:
                new_words.append(word)
            elif random.random() > p:
                new_words.append(word)

        # If all words deleted, return original
        if len(new_words) == 0:
            return text

        return ' '.join(new_words)

    def random_swap(self, text: str, n: int = None) -> str:
        """Randomly swap positions of n pairs of words.

        Vietnamese has relatively flexible word order in some contexts.

        Args:
            text: Input text
            n: Number of swaps (default: 5% of words)

        Returns:
            Augmented text
        """
        words = text.split()
        if len(words) < 2:
            return text

        # Default: swap ~5% of words
        if n is None:
            n = max(1, int(len(words) * 0.05))

        new_words = words.copy()
        for _ in range(n):
            # Pick two random indices
            idx1, idx2 = random.sample(range(len(new_words)), 2)
            # Swap
            new_words[idx1], new_words[idx2] = new_words[idx2], new_words[idx1]

        return ' '.join(new_words)

    def punctuation_variation(self, text: str) -> str:
        """Add or remove punctuation for paraphrasing.

        Args:
            text: Input text

        Returns:
            Augmented text
        """
        # Vietnamese common punctuation variations
        variations = [
            # Add emphasis
            lambda t: t.replace('.', '...') if random.random() > 0.5 else t,
            # Add/remove commas
            lambda t: t.replace(',', '') if random.random() > 0.5 else t,
            # Add question marks for emphasis (Vietnamese style)
            lambda t: t.replace('.', ' không?') if 'không' in t and random.random() > 0.7 else t,
        ]

        result = text
        for variation in variations:
            if random.random() > 0.7:  # Apply with 30% probability
                result = variation(result)

        return result

    def augment(self, text: str, num_aug: int = 1, techniques: List[str] = None) -> List[str]:
        """Generate multiple augmented versions of text.

        Args:
            text: Input text
            num_aug: Number of augmented samples to generate
            techniques: List of techniques to use. Options:
                       ['synonym', 'deletion', 'swap', 'punctuation']
                       Default: all techniques

        Returns:
            List of augmented texts
        """
        if techniques is None:
            techniques = ['synonym', 'deletion', 'swap', 'punctuation']

        augmented_texts = []

        for _ in range(num_aug):
            augmented = text

            # Randomly apply techniques
            if 'synonym' in techniques and random.random() > 0.5:
                augmented = self.synonym_replacement(augmented)

            if 'deletion' in techniques and random.random() > 0.5:
                augmented = self.random_deletion(augmented)

            if 'swap' in techniques and random.random() > 0.5:
                augmented = self.random_swap(augmented)

            if 'punctuation' in techniques and random.random() > 0.5:
                augmented = self.punctuation_variation(augmented)

            # Only add if different from original
            if augmented != text:
                augmented_texts.append(augmented)

        return augmented_texts

def oversample_minority_class(
    df: pd.DataFrame,
    text_col: str = 'text',
    label_col: str = 'binary_label',
    target_ratio: float = 0.5,
    num_aug_per_sample: int = 2
) -> pd.DataFrame:
    """Oversample minority class using Vietnamese augmentation.

    Args:
        df: DataFrame with text and labels
        text_col: Name of text column
        label_col: Name of label column (binary: 0 or 1)
        target_ratio: Target ratio for minority class (default: 0.5 for 50:50)
        num_aug_per_sample: Number of augmented samples per original sample

    Returns:
        Balanced DataFrame with augmented samples
    """
    # Count classes
    label_counts = df[label_col].value_counts()
    print(f"\nOriginal class distribution:")
    print(f"  Class 0 (NON_STRESS): {label_counts.get(0, 0)}")
    print(f"  Class 1 (STRESS): {label_counts.get(1, 0)}")

    # Identify minority and majority classes
    minority_label = label_counts.idxmin()
    majority_label = label_counts.idxmax()

    minority_count = label_counts[minority_label]
    majority_count = label_counts[majority_label]

    # Calculate how many samples we need to add
    # target_ratio = minority / (minority + majority)
    # minority + samples_to_add = target_ratio * (minority + samples_to_add + majority)
    # samples_to_add = (target_ratio * majority - (1 - target_ratio) * minority) / (1 - target_ratio)

    samples_needed = int(
        (target_ratio * majority_count - (1 - target_ratio) * minority_count) / (1 - target_ratio)
    )

    if samples_needed <= 0:
        print(f"No augmentation needed (minority class already at {minority_count}/{minority_count + majority_count} = {minority_count/(minority_count + majority_count):.2%})")
        return df

    print(f"\nAugmenting minority class (label={minority_label}):")
    print(f"  Need {samples_needed} additional samples to reach {target_ratio:.0%} ratio")

    # Get minority class samples
    minority_df = df[df[label_col] == minority_label].copy()

    # Calculate augmentations per sample
    aug_per_sample = max(1, samples_needed // len(minority_df))
    print(f"  Generating ~{aug_per_sample} augmented samples per original sample")

    # Augment
    augmenter = VietnameseAugmenter()
    augmented_rows = []

    for idx, row in minority_df.iterrows():
        text = row[text_col]

        # Generate augmented texts
        augmented_texts = augmenter.augment(text, num_aug=aug_per_sample)

        # Create new rows
        for aug_text in augmented_texts:
            new_row = row.copy()
            new_row[text_col] = aug_text
            augmented_rows.append(new_row)

        # Stop if we have enough
        if len(augmented_rows) >= samples_needed:
            break

    # Trim to exact number needed
    augmented_rows = augmented_rows[:samples_needed]

    # Combine with original dataset
    augmented_df = pd.DataFrame(augmented_rows)
    balanced_df = pd.concat([df, augmented_df], ignore_index=True)

    # Shuffle
    balanced_df = balanced_df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Print results
    new_label_counts = balanced_df[label_col].value_counts()
    print(f"\nBalanced class distribution:")
    print(f"  Class 0 (NON_STRESS): {new_label_counts.get(0, 0)}")
    print(f"  Class 1 (STRESS): {new_label_counts.get(1, 0)}")
    print(f"  Total samples: {len(df)} → {len(balanced_df)} (+{len(balanced_df) - len(df)} augmented)")

    minority_ratio = new_label_counts[minority_label] / len(balanced_df)
    print(f"  Minority class ratio: {minority_ratio:.2%} (target: {target_ratio:.0%})")

    return balanced_df

# Example usage
if __name__ == '__main__':
    # Test augmentation
    augmenter = VietnameseAugmenter()

    test_texts = [
        "Tôi đang rất căng thẳng và lo âu về công việc",
        "Cảm thấy mệt mỏi và kiệt sức sau một ngày dài",
        "Hôm nay tôi rất vui vẻ và hạnh phúc"
    ]

    print("Vietnamese Text Augmentation Examples")
    print("="*70)

    for i, text in enumerate(test_texts, 1):
        print(f"\n{i}. Original: {text}")
        augmented = augmenter.augment(text, num_aug=3)
        for j, aug_text in enumerate(augmented, 1):
            print(f"   Aug {j}:   {aug_text}")
