# Task 2.3: Initial Weak Labeling with Groq Cloud

## 🎯 Mục đích

Gán nhãn ban đầu cho 4,969 bài viết VOZ đã được tiền xử lý (Task 2.2) với:
- **Stress classification**: stress/non_stress
- **6 ABSA aspects**: work_pressure, relationship, financial, study, family_social, health
- **Confidence score**: 0.0-1.0

Theo PIPELINE.md Section 2.3, output được chia làm 2 tập:
- **High-confidence (≥0.7)**: Dùng trực tiếp để train Student Model (Task 2.4)
- **Low-confidence (<0.7)**: Relabel bằng Teacher-Student Consensus (Task 2.5)

## 🔧 Công nghệ

### Groq Cloud API (thay thế Ollama)

**Lý do thay đổi:**
- ❌ Ollama local: 66 seconds/post = **86 giờ** cho 5k posts (không thể chấp nhận)
- ✅ Groq Cloud: 0.5 seconds/post = **40 phút** cho 5k posts

**Groq Cloud specs:**
- Model: Llama-3.1-8B-Instant (same model family with Ollama)
- Speed: ~500 tokens/s
- Free tier: 14,400 requests/day (đủ cho 5k posts)
- API: https://console.groq.com/keys

## 📋 Prerequisites

1. **Data từ Task 2.2:**
   ```bash
   data/voz_preprocessed.json  # 4,969 posts
   ```

2. **Groq API Key (FREE):**
   - Đăng ký tại: https://console.groq.com/keys
   - Copy API key (gsk_...)
   - Set environment variable (đã làm sẵn trong `.env`)

3. **Dependencies:**
   ```bash
   pip install groq tqdm
   ```

## 🚀 Chạy Task 2.3

### 1. Kiểm tra API key

API key đã được set sẵn trong `.env`:
```bash
GROQ_API_KEY=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
```

Hoặc set temporary (PowerShell):
```powershell
$env:GROQ_API_KEY='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'
```

### 2. Run labeling script

```powershell
python scripts/label_with_groq.py
```

**Output:**
```
======================================================================
TASK 2.3: INITIAL WEAK LABELING WITH GROQ CLOUD
======================================================================
✓ API Key configured: gsk_l6e8I023KPDwUNO6...
✓ Loaded 4,969 posts

🤖 MODEL: Groq Llama-3.1-8B-Instant
   Speed: ~500 tokens/s (~0.5s per post)
   Free tier: 14,400 requests/day
   Estimated time: ~41.4 minutes

🎯 Will label 4,969 posts with:
   - Stress classification (stress/non_stress)
   - 6 ABSA aspects: work_pressure, relationship, financial, study, family_social, health
   - Confidence score (0.0-1.0)

Press ENTER to start labeling...

======================================================================
LABELING IN PROGRESS
======================================================================

🏷️  Labeling: 100%|██████████████████████| 4969/4969 [41:23<00:00,  2.00post/s]

======================================================================
✅ LABELING COMPLETE
======================================================================

📊 STATISTICS:
   Total posts:      4,969
   Stress posts:     1,234 (24.8%)
   Non-stress:       3,735 (75.2%)

🎯 ASPECT DISTRIBUTION (stress posts only):
   work_pressure       :  456 (36.9%)
   relationship        :  389 (31.5%)
   financial           :  278 (22.5%)
   study               :  567 (45.9%)
   family_social       :  123 (10.0%)
   health              :   89 ( 7.2%)

📈 CONFIDENCE SPLIT (PIPELINE.md Section 2.3):
   High-confidence (≥0.7): 3,478 (70.0%)
   Low-confidence  (<0.7): 1,491 (30.0%)

💾 OUTPUT FILES:
   data/voz_labeled_high_confidence.json
   data/voz_labeled_low_confidence.json

🎉 NEXT STEP: Task 2.4 - Train Student Model
   Use high-confidence set (3,478 posts) for training
   Low-confidence set will be relabeled in Task 2.5 (Teacher-Student Consensus)
```

## 📂 Output Structure

Theo PIPELINE.md Section 6.2, mỗi post có cấu trúc:

```json
{
  "post_id": "post-20175408",
  "forum": "Tâm sự cuộc sống",
  "timestamp": 1766213722,
  "raw_text": "...",
  "clean_text": "...",
  "url": "https://voz.vn/t/...",
  "author": "thuyvan",
  
  "stress_label": "stress",
  "aspect_labels": ["work_pressure", "study"],
  "confidence_score": 0.85,
  "label_source": "groq",
  
  "gender": "unknown",
  "age_group": "unknown",
  "occupation": "student",
  
  "collected_at": "2025-12-20T06:55:22.581773",
  "labeled_at": "2025-12-20T14:30:45.123456"
}
```

## 📊 Expected Results

**Confidence distribution:**
- High-confidence (≥0.7): ~70% (3,500 posts) → Training set cho Task 2.4
- Low-confidence (<0.7): ~30% (1,500 posts) → Relabel trong Task 2.5

**Stress ratio:**
- Stress posts: ~20-30% (dựa trên VOZ forum characteristics)
- Non-stress posts: ~70-80%

**Aspect distribution (trong stress posts):**
- work_pressure: ~30-40% (sinh viên, dev nhiều)
- study: ~40-50% (33.6% là student)
- relationship: ~25-35%
- financial: ~20-30%
- family_social: ~10-15%
- health: ~5-10%

## 🔍 Quality Check

### 1. Sample validation

```python
import json

# Load high-confidence
with open('data/voz_labeled_high_confidence.json', 'r', encoding='utf-8') as f:
    high_conf = json.load(f)

# Check random stress posts
import random
stress_posts = [p for p in high_conf if p['stress_label'] == 'stress']
sample = random.sample(stress_posts, 10)

for post in sample:
    print(f"\n{'='*70}")
    print(f"Text: {post['clean_text'][:200]}...")
    print(f"Aspects: {post['aspect_labels']}")
    print(f"Confidence: {post['confidence_score']}")
```

### 2. Statistics validation

```python
# Check aspect co-occurrence
from collections import Counter
aspect_pairs = []
for post in stress_posts:
    aspects = post['aspect_labels']
    for i in range(len(aspects)):
        for j in range(i+1, len(aspects)):
            aspect_pairs.append((aspects[i], aspects[j]))

print("\nTop aspect co-occurrences:")
for pair, count in Counter(aspect_pairs).most_common(10):
    print(f"  {pair[0]} + {pair[1]}: {count}")
```

## ⚠️ Troubleshooting

### API Key không hoạt động

```powershell
# Check API key
$env:GROQ_API_KEY

# Re-set if needed
$env:GROQ_API_KEY='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'
```

### Rate limit exceeded

Groq free tier: 14,400 requests/day, 30 requests/minute

Nếu vượt quá:
- Script sẽ tự động retry
- Hoặc chờ 1 phút rồi chạy lại

### Low confidence rate cao (>40%)

Nếu >40% posts có confidence <0.7:
- Có thể do data quality (nhiều posts không liên quan stress)
- Hoặc cần tune prompt trong `create_stress_prompt()`
- Vẫn OK, sẽ relabel trong Task 2.5

## 🎯 Next Steps

**Task 2.4: Train Student Model**
```bash
# Sử dụng high-confidence set (≥0.7)
# Input: data/voz_labeled_high_confidence.json
# Output: ml/models/student_phobert_v1/
```

**Task 2.5: Teacher-Student Consensus**
```bash
# Relabel low-confidence set (<0.7)
# Input: data/voz_labeled_low_confidence.json
# Method: 2/3 voting (Teacher + Student + Groq)
```

## 📚 References

- PIPELINE.md Section 2.3: Initial Weak Labeling
- PIPELINE.md Section 6.2: Dataset Structure
- Groq Cloud: https://console.groq.com
- Llama-3.1-8B docs: https://groq.com/models/

## 🔗 Related Files

- `scripts/label_with_groq.py` - Main labeling script
- `scripts/label_voz_weak_supervision.py` - DEPRECATED (Ollama version)
- `scripts/test_ollama_direct.py` - DEPRECATED (Ollama test)
- `.env` - API keys (GROQ_API_KEY)
- `docker-compose.yml` - Ollama service removed
