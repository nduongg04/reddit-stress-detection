#!/usr/bin/env python3
"""
Interpret LDA Topics as ABSA Mental Health Aspects
Converts LDA word clusters into meaningful mental health dimensions
"""

import json
from pathlib import Path

# Manual interpretation of LDA topics based on Vietnamese keywords
ABSA_INTERPRETATIONS = {
    0: {
        "aspect_name": "work_activity",
        "vietnamese": "công_việc_hoạt_động",
        "description": "Work, effort, activity, capability (công, lực, động, năng lực)",
        "keywords": ["công", "lực", "động", "năng", "hoạt động"],
        "mental_health_relevance": "Work-related stress, effort, burnout"
    },
    1: {
        "aspect_name": "sleep_medication",
        "vietnamese": "giấc_ngủ_thuốc",
        "description": "Sleep problems, medication, daily routine (ngủ, thuốc, ngày)",
        "keywords": ["ngủ", "thuốc", "ngày", "đầu", "thường"],
        "mental_health_relevance": "Insomnia, medication dependence, daily functioning"
    },
    2: {
        "aspect_name": "interpersonal_communication",
        "vietnamese": "giao_tiếp_cá_nhân",
        "description": "Personal communication, interactions (tui, anh, ông, con)",
        "keywords": ["tui", "anh", "ông", "con", "nhà"],
        "mental_health_relevance": "Social interactions, communication patterns"
    },
    3: {
        "aspect_name": "energy_deficiency",
        "vietnamese": "thiếu_năng_lượng",
        "description": "Lack of energy, deficiency (thiếu năng lượng)",
        "keywords": ["thiếu", "năng", "lượng", "việt", "nam"],
        "mental_health_relevance": "Low energy, fatigue, depletion"
    },
    4: {
        "aspect_name": "financial_work_stress",
        "vietnamese": "căng_thẳng_tài_chính_công_việc",
        "description": "Financial concerns, work, salary (tiền, công, lương)",
        "keywords": ["tiền", "công", "lương", "tháng", "định"],
        "mental_health_relevance": "Financial stress, job security, income worries"
    },
    5: {
        "aspect_name": "romantic_relationships",
        "vietnamese": "tình_yêu_quan_hệ",
        "description": "Love, relationships, emotional connections (yêu, tình, chuyện)",
        "keywords": ["yêu", "tình", "chuyện", "nhau", "tin"],
        "mental_health_relevance": "Romantic problems, heartbreak, relationship conflicts"
    },
    6: {
        "aspect_name": "self_reflection",
        "vietnamese": "tự_suy_ngẫm",
        "description": "Self-awareness, thinking, introspection (bản thân, nghĩ, tâm)",
        "keywords": ["bản", "thân", "nghĩ", "tâm", "giờ"],
        "mental_health_relevance": "Self-doubt, overthinking, self-awareness"
    },
    7: {
        "aspect_name": "mental_illness_depression",
        "vietnamese": "bệnh_trầm_cảm",
        "description": "Mental illness, depression, medical treatment (bệnh, trầm cảm, khám)",
        "keywords": ["bệnh", "trầm", "cảm", "khám", "bác"],
        "mental_health_relevance": "Depression diagnosis, medical help-seeking"
    },
    8: {
        "aspect_name": "family_living",
        "vietnamese": "gia_đình_cuộc_sống",
        "description": "Family, home life, children (nhà, con, sống, gia đình)",
        "keywords": ["nhà", "con", "sống", "gia", "đình"],
        "mental_health_relevance": "Family stress, parenting, household issues"
    },
    9: {
        "aspect_name": "mental_state_seeking",
        "vietnamese": "tâm_trạng_tìm_kiếm",
        "description": "Mental state, seeking help/solutions (tâm, tìm, hiện)",
        "keywords": ["tâm", "tìm", "hiện", "trạng", "điều"],
        "mental_health_relevance": "Mental health state, help-seeking behavior"
    }
}


def load_lda_topics(filepath="ml/lda/mental_health_topics.json"):
    """Load LDA topics from JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_absa_aspects(lda_data):
    """Convert LDA topics to ABSA aspects with interpretations"""

    aspects = []

    for topic in lda_data['topics']:
        topic_id = topic['topic_id']

        if topic_id not in ABSA_INTERPRETATIONS:
            print(f"Warning: No interpretation for topic {topic_id}")
            continue

        interpretation = ABSA_INTERPRETATIONS[topic_id]

        # Combine LDA keywords with interpretation
        lda_keywords = [kw['word'] for kw in topic['keywords'][:10]]

        aspect = {
            "id": topic_id,
            "aspect_name": interpretation["aspect_name"],
            "vietnamese": interpretation["vietnamese"],
            "description": interpretation["description"],
            "lda_keywords": lda_keywords,
            "interpretation_keywords": interpretation["keywords"],
            "mental_health_relevance": interpretation["mental_health_relevance"],
            "lda_topic_label": topic['topic_label']
        }

        aspects.append(aspect)

    return aspects


def save_absa_aspects(aspects, output_file="ml/lda/absa_mental_health_aspects.json"):
    """Save ABSA aspects to JSON"""

    output = {
        "description": "10 ABSA Mental Health Aspects from LDA Topic Modeling",
        "source": "1095 r/vozforums stress posts",
        "method": "LDA + Manual Interpretation",
        "usage": "Multi-label ABSA classification with PhoBERT",
        "num_aspects": len(aspects),
        "aspects": aspects
    }

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ ABSA aspects saved to {output_file}")


def print_aspect_summary(aspects):
    """Print summary of ABSA aspects"""
    print("\n" + "="*80)
    print("10 ABSA Mental Health Aspects for Multi-Label Classification")
    print("="*80)

    for aspect in aspects:
        print(f"\n{aspect['id']}. {aspect['aspect_name'].upper().replace('_', ' ')}")
        print(f"   Vietnamese: {aspect['vietnamese']}")
        print(f"   Description: {aspect['description']}")
        print(f"   Relevance: {aspect['mental_health_relevance']}")
        print(f"   LDA Keywords: {', '.join(aspect['lda_keywords'][:5])}")


def main():
    print("="*80)
    print("PHASE 2: Interpreting LDA Topics as ABSA Mental Health Aspects")
    print("="*80)

    # Load LDA topics
    print("\nLoading LDA topics from ml/lda/mental_health_topics.json...")
    lda_data = load_lda_topics()
    print(f"✓ Loaded {lda_data['num_topics']} LDA topics from {lda_data['num_documents']} documents")

    # Create ABSA aspects
    print("\nInterpreting LDA topics as mental health aspects...")
    aspects = create_absa_aspects(lda_data)
    print(f"✓ Created {len(aspects)} ABSA aspects")

    # Print summary
    print_aspect_summary(aspects)

    # Save to JSON
    print("\n" + "="*80)
    save_absa_aspects(aspects)

    print("\n" + "="*80)
    print("✓ PHASE 2 COMPLETE: ABSA Aspects Ready for Multi-Label Classification")
    print("="*80)
    print("\nThese 10 aspects will be used as labels for PhoBERT training:")
    print("  • Each post can have MULTIPLE aspects (multi-label)")
    print("  • Model outputs probability for each aspect")
    print("  • Enables fine-grained mental health classification")

    print("\nNext steps:")
    print("  1. Phase 3: Prepare training dataset (200 stress + 200 non-stress)")
    print("  2. Phase 4: Train PhoBERT multi-label ABSA model")


if __name__ == "__main__":
    main()
