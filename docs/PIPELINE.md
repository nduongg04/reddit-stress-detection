# 📑 Hướng dẫn hiệu chỉnh Flow Đồ án Big Data

## 1. Ngữ cảnh dự án
Dự án này áp dụng **PhoBERT** để phát hiện và thống kê các bài post trên **voz** liên quan đến tình trạng **stress trong cộng đồng**.  
Mục tiêu chính:
- Thu thập dữ liệu từ voz (~10,000 bài post).
- Loại bỏ LDA vì không đảm bảo kiểm soát chất lượng phân cụm.
- Bổ sung phân tích theo nhiều khía cạnh (giới tính, nghề nghiệp, v.v.).
- Xây dựng pipeline real-time: Crawl → Preprocess → Label → Train → Test → Report → Relabel → Retrain.

---

## 2. Tasks & Pipeline Design

Dự án này áp dụng **PhoBERT** để phát hiện và thống kê các bài viết liên quan đến **stress trong cộng đồng voz.vn**. Mục tiêu chính của dự án bao gồm:

- Thu thập dữ liệu quy mô lớn từ voz.vn (~10,000 bài viết).
- Không sử dụng LDA do hạn chế trong việc kiểm soát chất lượng phân cụm và diễn giải nhãn.
- Phân tích stress theo nhiều khía cạnh (aspect) và các yếu tố nhân khẩu học được suy luận từ nội dung (giới tính, nghề nghiệp, độ tuổi).
- Xây dựng pipeline bán real-time với khả năng tự cải thiện chất lượng nhãn:
  
  **Crawl → Preprocess → Label → Train → Test → Report → Relabel → Retrain**

---

### 2.1. Crawl Data
- Crawl các bài viết từ các forum xã hội chính trên voz.vn.
- Thu thập:
  - Tiêu đề bài viết
  - Nội dung bài viết
  - Thời gian đăng
  - Forum ID
- Lưu dữ liệu thô (raw data) vào storage để phục vụ các bước xử lý tiếp theo.

---

### 2.2. Data Preprocessing
- Làm sạch văn bản:
  - Loại bỏ ký tự đặc biệt, emoji, URL, HTML tag.
- Chuẩn hóa tiếng Việt:
  - Chuẩn dấu
  - Chuẩn hóa các từ viết tắt phổ biến trong hội thoại.
- Chuẩn hóa cấu trúc dữ liệu (text, timestamp, forum).
- Trích xuất metadata suy luận từ nội dung (nếu có):
  - Giới tính
  - Nghề nghiệp
  - Độ tuổi  
  (Các metadata này được gán nhãn `unknown` nếu không xác định được.)

---

### 2.3. Initial Labeling (Weak Labeling)

#### Mục tiêu
Tạo tập dữ liệu có nhãn ban đầu với độ tin cậy cao để huấn luyện mô hình chính.

#### Phương pháp
- Sử dụng **Groq Cloud API** (Llama-3.1-8B-Instant) như một **weak labeling model** để gán nhãn stress và các aspect.
  - Alternative: Ollama local (chậm hơn ~100x, dùng khi offline)
  - Model: Llama-3.1-8B-Instant (miễn phí, 14.4k requests/day)
  - Tốc độ: ~0.5s/post (~40 phút cho 5,000 posts)
- Mỗi bài viết được gán:
  - `stress_label` (stress/non_stress)
  - `aspect_labels` (multi-label: work_pressure, relationship, financial, study, family_social, health)
  - `confidence_score` (0.0-1.0)

#### Phân chia dữ liệu theo độ tin cậy
- **High-confidence set (Lớp 1):**
  - Các bài viết có `confidence_score > 0.7`
  - Được xem là nhãn đáng tin cậy
  - Dùng trực tiếp để huấn luyện mô hình ban đầu
- **Low-confidence set (Uncertain set):**
  - Các bài viết có `confidence_score ≤ 0.7`
  - Chưa đủ độ tin cậy để đưa vào training
  - Được tách riêng để xử lý ở bước relabel

---

### 2.4. Training & Evaluation (Student Model)

- Huấn luyện **Student Model**:
  - PhoBERT (phiên bản nhẹ hơn)
  - Chỉ sử dụng **High-confidence set**
- Đánh giá mô hình trên tập validation nội bộ:
  - Accuracy / F1-score
  - Confidence calibration

Mô hình này đóng vai trò là **mô hình chính trong pipeline**.

---

### 2.5. Relabeling bằng Teacher–Student Consensus

#### Mục tiêu
Nâng cao chất lượng nhãn cho các bài viết trong **Low-confidence set**.

#### Các mô hình tham gia
- **Teacher Model:** PhoBERT fine-tuned (mạnh hơn, train kỹ hơn)
- **Student Model:** PhoBERT lightweight (mô hình chính)
- **Weak Label Model:** Groq Cloud API (Llama-3.1-8B-Instant)

#### Cơ chế đồng thuận (Consensus-based Relabeling)
Với mỗi bài viết trong Low-confidence set:
- Chạy suy luận qua cả 3 mô hình
- So sánh kết quả gán nhãn

Một nhãn được chấp nhận nếu:
- Ít nhất **2/3 mô hình đồng thuận về label**
- Confidence trung bình vượt ngưỡng xác định (ví dụ > 0.75)

Các bài viết không đạt đồng thuận:
- Được giữ lại trong tập `unlabeled`
- Không sử dụng để huấn luyện

---

### 2.6. Retraining & Iterative Improvement

- Gộp:
  - High-confidence set ban đầu
  - Tập dữ liệu đã được relabel bằng consensus
- Huấn luyện lại **Student Model**
- Lặp lại quy trình khi có dữ liệu mới:
  
  **Label → Train → Test → Relabel → Retrain**

---

### 2.7. Logging & Monitoring
- Lưu lại toàn bộ:
  - Confidence score ở từng giai đoạn
  - Nguồn nhãn (Ollama / Teacher / Consensus)
- Theo dõi:
  - Tỷ lệ dữ liệu được promote từ low-confidence → training
  - Sự cải thiện confidence qua mỗi vòng lặp

---

## 3. Training & Reporting

### 3.1 Training
- Train mô hình **PhoBERT** với dữ liệu đã được relabel.
- Sử dụng pipeline real-time để cập nhật mô hình liên tục khi có dữ liệu mới.

## 3.2. Reporting & Analysis

Phần này trình bày các kết quả thống kê và phân tích liên quan đến các bài viết có nội dung **stress trong cộng đồng voz.vn**, dựa trên dữ liệu đã được crawl, gán nhãn và relabel bằng pipeline đề xuất.

---

### 3.2.1. Tỷ lệ bài viết liên quan đến stress theo forum

#### Mục tiêu
Đánh giá mức độ phổ biến của các bài viết liên quan đến stress trong từng forum trên voz.vn.

#### Phương pháp
Với mỗi forum \( f \), tỷ lệ bài viết stress được tính như sau:

\[
\text{Stress Ratio}_f =
\frac{\text{Số bài viết được gán nhãn stress trong forum } f}
{\text{Tổng số bài viết crawl được trong forum } f}
\times 100\%
\]

Một bài viết được xem là **stress post** nếu mô hình gán ít nhất một aspect stress với độ tin cậy vượt ngưỡng xác định.

#### Kết quả trình bày
- Bảng thống kê:
  - Tên forum
  - Tổng số bài viết
  - Số bài viết stress
  - Tỷ lệ stress (%)
- Biểu đồ cột (bar chart): Tỷ lệ stress theo từng forum

#### Ý nghĩa
- Xác định forum nào tập trung nhiều nội dung stress nhất
- Cho thấy sự phân bố không đồng đều của stress giữa các forum

---

### 3.2.2. Phân bố các khía cạnh (aspect) gây stress

#### Các aspect được xem xét
1. Stress vì deadline / áp lực công việc  
2. Stress vì chuyện tình cảm / mối quan hệ cá nhân  
3. Stress vì thất nghiệp / khó khăn tài chính  
4. Stress vì học tập / thi cử  
5. Stress vì xung đột gia đình / xã hội  
6. Stress vì sức khỏe / bệnh tật  

#### Phương pháp
Với mỗi aspect \( A_i \), tỷ lệ phân bố được tính trên **tổng số bài viết**:

\[
\text{Aspect Distribution}_{A_i} =
\frac{\text{Số bài viết được gán aspect } A_i}
{\text{Tổng số bài viết}}
\times 100\%
\]

Lưu ý rằng bài toán được xây dựng theo hướng **multi-label**, do đó một bài viết có thể thuộc nhiều aspect stress khác nhau. Vì vậy, tổng tỷ lệ phần trăm của các aspect có thể vượt quá 100%.

#### Kết quả trình bày
- Bảng thống kê tỷ lệ (%) của từng aspect
- Biểu đồ tròn (pie chart) hoặc biểu đồ cột chồng (stacked bar)

#### Ý nghĩa
- Xác định nguyên nhân gây stress phổ biến nhất trong cộng đồng
- So sánh mức độ ảnh hưởng tương đối giữa các khía cạnh stress

---

### 3.2.3. Phân tích stress theo thời gian (3 năm gần nhất)

#### Dữ liệu
- Dựa trên ngày đăng bài của mỗi post
- Chỉ xét các bài viết trong **3 năm gần nhất** so với thời điểm crawl

#### Phương pháp
- Dữ liệu được chia theo từng năm
- Với mỗi năm, tính tỷ lệ phân bố các aspect stress

\[
\text{Aspect Ratio}_{A_i, Y_j}
\]

#### Kết quả trình bày
- Biểu đồ đường (line chart): xu hướng stress theo thời gian
- Biểu đồ cột chồng: phân bố aspect theo từng năm

#### Ý nghĩa
- Phân tích xu hướng thay đổi của các nguyên nhân stress theo thời gian
- Phát hiện các aspect có xu hướng gia tăng hoặc suy giảm

---

### 3.2.4. Phân tích theo nghề nghiệp (Occupation-aware Analysis)

#### Phương pháp xác định nghề nghiệp
Nghề nghiệp của người viết bài được **suy luận từ nội dung văn bản**, dựa trên:
- Luật (keyword / pattern) như: *sinh viên, dev, công nhân, freelancer, kế toán,...*
- Hoặc mô hình phân loại / NER hỗ trợ (nếu có)

Các trường hợp không xác định được được gán nhãn `unknown`.

#### Phân tích
Với mỗi nhóm nghề nghiệp \( O_k \), xác suất xuất hiện của từng aspect stress được tính như sau:

\[
P(A_i \mid O_k)
\]

#### Kết quả trình bày
- Heatmap: nghề nghiệp × aspect stress
- Bảng thống kê nhóm nghề nghiệp có tỷ lệ stress cao

#### Ý nghĩa
- Xác định mối liên hệ giữa nghề nghiệp và nguyên nhân gây stress
- So sánh sự khác biệt về stress giữa các nhóm nghề nghiệp

---

### 3.2.5. Phân tích theo độ tuổi (Age-aware Analysis)

#### Phương pháp xác định độ tuổi
Độ tuổi được suy luận từ nội dung bài viết bằng các mẫu biểu thức như:
- “em 22 tuổi”
- “mình năm nay 30”
- “ngoài 4x”

Sau đó gom nhóm:
- \< 18
- 18–22
- 23–30
- 31–40
- \> 40

#### Phân tích
Với mỗi nhóm tuổi, tính phân bố các aspect stress:

\[
P(A_i \mid \text{Age Group})
\]

#### Kết quả trình bày
- Biểu đồ cột chồng: nhóm tuổi × aspect
- Bảng thống kê tỷ lệ stress theo độ tuổi

#### Ý nghĩa
- Phân tích sự khác biệt về nguyên nhân stress theo từng giai đoạn tuổi
- Xác định nhóm tuổi dễ bị stress nhất

---

### 3.2.6. Phân tích theo giới tính (Gender-aware Analysis)

#### Phương pháp xác định giới tính
Giới tính được suy luận từ nội dung văn bản thông qua:
- Từ khóa trực tiếp (ví dụ: “em là nữ”, “mình là đàn ông”)
- Đại từ xưng hô (anh, chị, em)

Các trường hợp không xác định được được gán nhãn `unknown`.

#### Phân tích
\[
P(A_i \mid \text{Gender})
\]

#### Kết quả trình bày
- Biểu đồ cột: giới tính × aspect stress
- Bảng thống kê tỷ lệ stress theo giới tính

#### Ý nghĩa
- So sánh sự khác biệt về nguyên nhân stress giữa các giới
- Đánh giá mức độ bao phủ và tỷ lệ `unknown`

---

### 3.2.7. Phân bố độ tin cậy của mô hình (Confidence Distribution)

#### Phương pháp
- Sử dụng `confidence_score` của nhãn cuối cùng sau bước relabel
- Chia thành các khoảng:
  - 0.7 – 0.8
  - 0.8 – 0.9
  - 0.9 – 1.0

#### Kết quả trình bày
- Histogram phân bố confidence
- Boxplot confidence theo từng aspect stress

#### Ý nghĩa
- Đánh giá độ tin cậy của pipeline gán nhãn
- Chứng minh hiệu quả của bước relabel trong việc nâng cao chất lượng nhãn

---

### Ghi chú
Các thông tin về nghề nghiệp, độ tuổi và giới tính trong nghiên cứu này **được suy luận từ nội dung bài viết**, không phải dữ liệu nhân khẩu học gốc. Do đó, kết quả phân tích mang tính thống kê và có thể tồn tại nhiễu, đặc biệt với các trường hợp không xác định được (unknown).

### 3.3 Output
- Báo cáo tổng hợp theo từng nguyên nhân gây stress.
- Visualization: biểu đồ phân bố stress theo từng khía cạnh tâm lý.
- Insight: xác định nguyên nhân phổ biến nhất và nhóm đối tượng dễ bị stress.

---

## 4. Monitoring
- Thiết lập pipeline real-time:
  - Crawl → Preprocess → Label → Train → Test → Report → Relabel → Retrain.
- Log toàn bộ quá trình để kiểm soát chất lượng.

---

## 5. Problem Definition & Learning Setup

### 5.1. Problem Definition

Bài toán trong nghiên cứu này được mô hình hóa như một bài toán **phân loại văn bản đa nhãn (multi-label text classification)** với giám sát yếu (weak supervision).

Cho tập bài viết \( P = \{p_1, p_2, ..., p_n\} \), với mỗi bài viết \( p_i \):

- Mục tiêu 1: Xác định xem bài viết có liên quan đến **stress** hay không  
  \[
  y_i \in \{0, 1\}
  \]

- Mục tiêu 2: Nếu bài viết thuộc lớp stress, xác định các **khía cạnh (aspect)** gây stress:
  \[
  A_i \subseteq \{A_1, A_2, ..., A_k\}
  \]

Trong đó các aspect bao gồm:
- Áp lực công việc / deadline
- Tình cảm / mối quan hệ cá nhân
- Thất nghiệp / khó khăn tài chính
- Học tập / thi cử
- Gia đình / xung đột xã hội
- Sức khỏe / bệnh tật

Một bài viết có thể đồng thời thuộc nhiều aspect khác nhau.

---

## 6. Label Schema & Dataset Structure

### 6.1. Label Schema

#### Stress Label
- `stress`
- `non_stress`

#### Aspect Labels (Multi-label)
- `work_pressure`
- `relationship`
- `financial`
- `study`
- `family_social`
- `health`

Các nhãn aspect chỉ được gán khi bài viết được xác định là `stress`.

---

### 6.2. Dataset Structure

Mỗi bài viết sau khi xử lý được lưu với cấu trúc dữ liệu như sau:

- `post_id`
- `forum_id`
- `timestamp`
- `raw_text`
- `clean_text`
- `stress_label`
- `aspect_labels` (list)
- `confidence_score`
- `label_source`  
  (`groq`, `teacher_model`, `consensus`, `ollama` for legacy)
- `gender` (`male`, `female`, `unknown`)
- `age_group` (`<18`, `18-22`, `23-30`, `31-40`, `>40`, `unknown`)
- `occupation` (`student`, `developer`, `worker`, ..., `unknown`)

Cấu trúc này cho phép:
- Phân tích linh hoạt theo forum, thời gian và nhân khẩu học
- Truy vết nguồn gốc nhãn phục vụ monitoring và đánh giá chất lượng

---

## 7. Baseline & Evaluation Strategy

### 7.1. Baseline Models

Để đánh giá hiệu quả của pipeline đề xuất, các baseline sau được sử dụng để so sánh:

- **Weak-label baseline**:
  - Sử dụng trực tiếp nhãn từ Groq API (Llama-3.1-8B)
  - Không qua bước relabel

- **Student-only baseline**:
  - PhoBERT lightweight
  - Huấn luyện trực tiếp trên toàn bộ dữ liệu weak-label

- **Majority baseline**:
  - Gán nhãn theo phân bố phổ biến nhất của tập training

Các baseline này giúp đánh giá mức độ cải thiện của phương pháp teacher–student consensus.

---

### 7.2. Evaluation Metrics

Các chỉ số đánh giá chính bao gồm:
- Precision / Recall / F1-score cho stress classification
- Micro-F1 và Macro-F1 cho bài toán multi-label aspect
- Confidence calibration (phân bố confidence theo nhãn)

Do không có ground truth hoàn chỉnh, kết quả được đánh giá chủ yếu dựa trên:
- So sánh tương đối giữa các mô hình
- Độ ổn định của nhãn qua các vòng lặp huấn luyện

---

## 8. Monitoring & Quality Control

### 8.1. Label Stability Monitoring

Theo dõi sự thay đổi nhãn của cùng một bài viết qua các vòng lặp:

- Tỷ lệ nhãn không đổi
- Tỷ lệ nhãn được nâng confidence
- Tỷ lệ nhãn bị loại bỏ do không đạt đồng thuận

---

### 8.2. Promotion Rate Analysis

Định nghĩa **promotion rate** là tỷ lệ bài viết được chuyển từ tập low-confidence sang tập training sau bước relabel:

\[
\text{Promotion Rate} =
\frac{\text{Số bài viết được relabel thành công}}
{\text{Tổng số bài viết low-confidence}}
\]

Chỉ số này phản ánh hiệu quả của cơ chế teacher–student consensus.

---

### 8.3. Confidence Gain Tracking

Theo dõi mức cải thiện confidence trung bình sau mỗi vòng lặp:

\[
\Delta C = C_{\text{after relabel}} - C_{\text{before relabel}}
\]

Giá trị \( \Delta C > 0 \) cho thấy pipeline giúp nâng cao chất lượng nhãn.

---

## 9. Limitations & Assumptions

- Các thông tin nhân khẩu học (giới tính, độ tuổi, nghề nghiệp) được **suy luận từ nội dung bài viết**, không phải dữ liệu gốc.
- Dữ liệu có thể chứa nhiễu, slang, irony và các biểu đạt cảm xúc gián tiếp.
- Kết quả phân tích mang tính thống kê, không đại diện cho toàn bộ cộng đồng.

Các hạn chế này được xem xét trong quá trình diễn giải kết quả và rút ra insight.

---

## 10. Summary

Pipeline đề xuất kết hợp **weak supervision**, **teacher–student learning** và **consensus-based relabeling** nhằm:
- Giảm nhiễu nhãn
- Nâng cao độ tin cậy của mô hình
- Tạo ra các insight có ý nghĩa từ dữ liệu thực tế quy mô lớn

Cách tiếp cận này phù hợp với các bài toán NLP trong môi trường thiếu dữ liệu gán nhãn chất lượng cao và có thể mở rộng cho các nghiên cứu tương tự trong tương lai.
