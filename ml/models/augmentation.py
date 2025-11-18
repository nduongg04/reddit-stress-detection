"""
Advanced text augmentation techniques for imbalanced dataset
"""

import random
import re
import numpy as np
from typing import List


class TextAugmenter:
    """Text augmentation using Easy Data Augmentation (EDA) techniques"""

    def __init__(self, random_state=42):
        random.seed(random_state)
        np.random.seed(random_state)

    def synonym_replacement(self, text: str, n: int = 2) -> str:
        """Replace n words with synonyms (simplified version)"""
        words = text.split()
        if len(words) < 3:
            return text

        # Simple synonym dictionary for common words
        synonyms = {
            'feel': ['sense', 'experience', 'perceive'],
            'very': ['really', 'extremely', 'incredibly'],
            'bad': ['terrible', 'awful', 'horrible'],
            'good': ['great', 'wonderful', 'excellent'],
            'scared': ['frightened', 'terrified', 'afraid'],
            'worried': ['concerned', 'anxious', 'troubled'],
            'happy': ['glad', 'pleased', 'joyful'],
            'sad': ['unhappy', 'miserable', 'depressed'],
            'think': ['believe', 'consider', 'suppose'],
            'know': ['understand', 'realize', 'recognize'],
            'hard': ['difficult', 'tough', 'challenging'],
            'easy': ['simple', 'straightforward', 'effortless']
        }

        aug_words = words.copy()
        random_indices = random.sample(range(len(words)), min(n, len(words)))

        for idx in random_indices:
            word_lower = words[idx].lower()
            if word_lower in synonyms:
                aug_words[idx] = random.choice(synonyms[word_lower])

        return ' '.join(aug_words)

    def random_insertion(self, text: str, n: int = 2) -> str:
        """Insert n random words from the sentence"""
        words = text.split()
        if len(words) < 3:
            return text

        for _ in range(n):
            random_word = random.choice(words)
            random_idx = random.randint(0, len(words))
            words.insert(random_idx, random_word)

        return ' '.join(words)

    def random_swap(self, text: str, n: int = 2) -> str:
        """Randomly swap n pairs of words"""
        words = text.split()
        if len(words) < 2:
            return text

        for _ in range(n):
            if len(words) >= 2:
                idx1, idx2 = random.sample(range(len(words)), 2)
                words[idx1], words[idx2] = words[idx2], words[idx1]

        return ' '.join(words)

    def random_deletion(self, text: str, p: float = 0.1) -> str:
        """Randomly delete words with probability p"""
        words = text.split()
        if len(words) < 3:
            return text

        new_words = [word for word in words if random.random() > p]

        # If all words are deleted, return random word
        if len(new_words) == 0:
            return random.choice(words)

        return ' '.join(new_words)

    def back_translation_simulation(self, text: str) -> str:
        """Simulate back-translation by reordering phrases"""
        # Simple simulation: reverse some word pairs
        words = text.split()
        if len(words) < 4:
            return text

        # Reverse every other pair
        result = []
        i = 0
        while i < len(words):
            if i + 1 < len(words) and random.random() > 0.5:
                result.extend([words[i+1], words[i]])
                i += 2
            else:
                result.append(words[i])
                i += 1

        return ' '.join(result)

    def augment(self, text: str, num_aug: int = 1, techniques: List[str] = None) -> List[str]:
        """
        Apply random augmentation techniques

        Args:
            text: Input text
            num_aug: Number of augmented versions to generate
            techniques: List of techniques to use. If None, use all.

        Returns:
            List of augmented texts
        """
        if techniques is None:
            techniques = ['sr', 'ri', 'rs', 'rd']

        augmented_texts = []
        technique_map = {
            'sr': self.synonym_replacement,
            'ri': self.random_insertion,
            'rs': self.random_swap,
            'rd': self.random_deletion
        }

        for _ in range(num_aug):
            # Randomly choose technique
            technique = random.choice(techniques)
            if technique in technique_map:
                aug_text = technique_map[technique](text)
                augmented_texts.append(aug_text)
            else:
                augmented_texts.append(text)

        return augmented_texts


def oversample_minority_class(
    texts: List[str],
    labels: List[int],
    target_ratio: float = 0.5,
    augmenter: TextAugmenter = None
) -> tuple:
    """
    Oversample minority class using augmentation

    Args:
        texts: List of texts
        labels: List of labels
        target_ratio: Target ratio for minority class
        augmenter: TextAugmenter instance

    Returns:
        Tuple of (augmented_texts, augmented_labels)
    """
    if augmenter is None:
        augmenter = TextAugmenter()

    texts = list(texts)
    labels = list(labels)

    # Find minority and majority classes
    unique, counts = np.unique(labels, return_counts=True)
    class_counts = dict(zip(unique, counts))

    minority_class = min(class_counts, key=class_counts.get)
    majority_class = max(class_counts, key=class_counts.get)

    print(f"\n📊 Original class distribution: {class_counts}")
    print(f"   Minority class: {minority_class} ({class_counts[minority_class]} samples)")
    print(f"   Majority class: {majority_class} ({class_counts[majority_class]} samples)")

    # Calculate how many samples we need
    majority_count = class_counts[majority_class]
    target_minority_count = int(majority_count * target_ratio / (1 - target_ratio))
    samples_needed = target_minority_count - class_counts[minority_class]

    if samples_needed <= 0:
        print("✓ Dataset already balanced!")
        return texts, labels

    print(f"\n🔄 Augmenting {samples_needed} samples for minority class {minority_class}...")

    # Get minority class samples
    minority_indices = [i for i, label in enumerate(labels) if label == minority_class]

    # Augment
    augmented_texts = []
    augmented_labels = []

    # Use multiple augmentation techniques
    techniques_pool = ['sr', 'ri', 'rs', 'rd']

    while len(augmented_texts) < samples_needed:
        # Randomly select a minority sample
        idx = np.random.choice(minority_indices)
        original_text = texts[idx]

        # Apply 2-3 different augmentation techniques
        num_techniques = random.choice([2, 3])
        techniques = random.sample(techniques_pool, num_techniques)

        # Generate augmented versions
        aug_versions = augmenter.augment(original_text, num_aug=1, techniques=techniques)
        augmented_texts.extend(aug_versions)
        augmented_labels.extend([minority_class] * len(aug_versions))

    # Trim to exact number needed
    augmented_texts = augmented_texts[:samples_needed]
    augmented_labels = augmented_labels[:samples_needed]

    # Combine
    balanced_texts = texts + augmented_texts
    balanced_labels = labels + augmented_labels

    # Shuffle
    combined = list(zip(balanced_texts, balanced_labels))
    np.random.shuffle(combined)
    balanced_texts, balanced_labels = zip(*combined)

    final_counts = dict(zip(*np.unique(balanced_labels, return_counts=True)))
    print(f"\n✓ Balanced class distribution: {final_counts}")
    print(f"   Ratio: {final_counts[minority_class]}/{final_counts[majority_class]} = {final_counts[minority_class]/final_counts[majority_class]:.2f}")

    return list(balanced_texts), list(balanced_labels)
