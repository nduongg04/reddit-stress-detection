#!/usr/bin/env python3
"""
Task 2.2: Data Preprocessing
Theo PIPELINE.md, thực hiện:
1. Làm sạch văn bản (ký tự đặc biệt, emoji, URL, HTML)
2. Chuẩn hóa tiếng Việt (dấu, viết tắt)
3. Trích xuất metadata (giới tính, nghề nghiệp, độ tuổi)
"""

import json
import re
import html
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import unicodedata

class VietnamesePreprocessor:
    def __init__(self):
        # Từ viết tắt phổ biến
        self.abbreviations = {
            'k': 'không',
            'ko': 'không',
            'kg': 'không',
            'dc': 'được',
            'đc': 'được',
            'vs': 'với',
            'nc': 'nói chuyện',
            'ny': 'người yêu',
            'cx': 'cũng',
            'mn': 'mọi người',
            'mk': 'mình',
            'mik': 'mình',
            'ck': 'chồng',
            'vk': 'vợ',
            'b': 'bạn',
            'r': 'rồi',
            'j': 'gì',
            'bik': 'biết',
            'nhìu': 'nhiều',
            'nhiu': 'nhiều',
            'trc': 'trước',
            'lun': 'luôn',
            'ak': 'à',
            'uk': 'ừ',
            'uh': 'ừ',
            'uh': 'ừ',
        }
        
        # Từ khóa giới tính
        self.gender_keywords = {
            'male': ['anh', 'đàn ông', 'nam', 'con trai', 'thằng', 'bồ tôi là con trai', 
                    'boyfriend', 'bạn trai', 'chồng', 'ông xã', 'thím'],
            'female': ['chị', 'em gái', 'nữ', 'con gái', 'đàn bà', 'phụ nữ', 'bồ tôi là con gái',
                      'girlfriend', 'bạn gái', 'vợ', 'bà xã']
        }
        
        # Từ khóa nghề nghiệp
        self.occupation_keywords = {
            'student': ['sinh viên', 'học sinh', 'đại học', 'trường', 'lớp', 'thi', 'học', 
                       'điểm', 'thầy cô', 'giáo viên'],
            'developer': ['dev', 'lập trình', 'code', 'programmer', 'software', 'IT', 
                         'developer', 'coder'],
            'teacher': ['giáo viên', 'thầy', 'cô', 'dạy học', 'giảng viên'],
            'office_worker': ['văn phòng', 'nhân viên', 'công ty', 'làm việc', 'sếp', 'đồng nghiệp'],
            'freelancer': ['freelance', 'tự do', 'làm tự do'],
            'business': ['kinh doanh', 'buôn bán', 'doanh nhân', 'chủ shop'],
            'worker': ['công nhân', 'nhà máy', 'xưởng', 'ca làm'],
            'medical': ['bác sĩ', 'y tá', 'điều dưỡng', 'bệnh viện'],
            'unemployed': ['thất nghiệp', 'không có việc', 'mất việc', 'bị sa thải']
        }
        
    def clean_text(self, text: str) -> str:
        """Làm sạch văn bản"""
        if not text:
            return ""
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Loại bỏ URL
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Loại bỏ HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Loại bỏ emoji (Unicode emoji ranges)
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub('', text)
        
        # Loại bỏ ký tự đặc biệt nhưng giữ dấu câu tiếng Việt
        text = re.sub(r'[^\w\s.,!?;:()\-\'"àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđĐÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸ]', ' ', text)
        
        # Chuẩn hóa khoảng trắng
        text = ' '.join(text.split())
        
        return text.strip()
    
    def normalize_vietnamese(self, text: str) -> str:
        """Chuẩn hóa tiếng Việt"""
        # Chuẩn hóa Unicode (NFC normalization)
        text = unicodedata.normalize('NFC', text)
        
        # Expand abbreviations
        words = text.split()
        normalized_words = []
        for word in words:
            word_lower = word.lower()
            if word_lower in self.abbreviations:
                normalized_words.append(self.abbreviations[word_lower])
            else:
                normalized_words.append(word)
        
        return ' '.join(normalized_words)
    
    def extract_gender(self, text: str) -> str:
        """Trích xuất giới tính từ văn bản"""
        text_lower = text.lower()
        
        # Tìm các câu tự giới thiệu
        patterns = [
            r'(?:em|mình|tôi|t)\s+(?:là|)\s*(?:nam|nữ|con trai|con gái|đàn ông|đàn bà)',
            r'(?:em|mình|tôi|t)\s+\d+\s*tuổi\s+(?:nam|nữ)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                matched_text = match.group()
                if any(kw in matched_text for kw in ['nam', 'con trai', 'đàn ông']):
                    return 'male'
                elif any(kw in matched_text for kw in ['nữ', 'con gái', 'đàn bà']):
                    return 'female'
        
        # Đếm từ khóa giới tính
        male_count = sum(1 for kw in self.gender_keywords['male'] if kw in text_lower)
        female_count = sum(1 for kw in self.gender_keywords['female'] if kw in text_lower)
        
        if male_count > female_count and male_count >= 2:
            return 'male'
        elif female_count > male_count and female_count >= 2:
            return 'female'
        
        return 'unknown'
    
    def extract_age(self, text: str) -> str:
        """Trích xuất độ tuổi từ văn bản"""
        # Patterns tìm tuổi
        patterns = [
            r'(?:em|mình|tôi|t)\s+(?:năm nay|)\s*(\d+)\s*tuổi',
            r'(?:em|mình|tôi|t)\s+(\d+)\s*tuổi',
            r'ngoài\s+(\d+)',
            r'u(\d+)',  # u30, u25
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                age = int(match.group(1))
                if age < 18:
                    return '<18'
                elif 18 <= age <= 22:
                    return '18-22'
                elif 23 <= age <= 30:
                    return '23-30'
                elif 31 <= age <= 40:
                    return '31-40'
                else:
                    return '>40'
        
        return 'unknown'
    
    def extract_occupation(self, text: str) -> str:
        """Trích xuất nghề nghiệp từ văn bản"""
        text_lower = text.lower()
        
        occupation_scores = {}
        for occupation, keywords in self.occupation_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                occupation_scores[occupation] = score
        
        if not occupation_scores:
            return 'unknown'
        
        # Trả về nghề nghiệp có nhiều từ khóa nhất
        return max(occupation_scores, key=occupation_scores.get)
    
    def preprocess_post(self, post: Dict) -> Dict:
        """Xử lý một bài post"""
        # Kết hợp title và selftext
        full_text = f"{post.get('title', '')} {post.get('selftext', '')}"
        
        # Clean text
        clean_text = self.clean_text(full_text)
        
        # Normalize Vietnamese
        normalized_text = self.normalize_vietnamese(clean_text)
        
        # Extract metadata
        gender = self.extract_gender(full_text)
        age_group = self.extract_age(full_text)
        occupation = self.extract_occupation(full_text)
        
        # Tạo post mới với dữ liệu đã xử lý
        processed_post = {
            'post_id': post.get('post_id'),
            'forum': post.get('forum'),
            'timestamp': post.get('created_utc'),
            'raw_text': full_text[:500],  # Giữ 500 ký tự đầu của raw text
            'clean_text': normalized_text,
            'url': post.get('url'),
            'author': post.get('author'),
            'gender': gender,
            'age_group': age_group,
            'occupation': occupation,
            'collected_at': post.get('collected_at')
        }
        
        return processed_post

def main():
    print("=== TASK 2.2: DATA PREPROCESSING ===\n")
    
    # Load data
    print("Loading data from voz_deduplicated.json...")
    with open('data/voz_deduplicated.json', 'r', encoding='utf-8') as f:
        posts = json.load(f)
    
    print(f"Loaded {len(posts)} posts\n")
    
    # Initialize preprocessor
    preprocessor = VietnamesePreprocessor()
    
    # Process all posts
    print("Processing posts...")
    processed_posts = []
    
    for i, post in enumerate(posts):
        if i % 500 == 0:
            print(f"Processed {i}/{len(posts)} posts...")
        
        processed_post = preprocessor.preprocess_post(post)
        processed_posts.append(processed_post)
    
    print(f"Processed {len(processed_posts)} posts\n")
    
    # Statistics
    print("=== STATISTICS ===")
    print(f"Total posts: {len(processed_posts)}")
    
    # Gender distribution
    gender_dist = {}
    for post in processed_posts:
        gender = post['gender']
        gender_dist[gender] = gender_dist.get(gender, 0) + 1
    
    print("\nGender distribution:")
    for gender, count in sorted(gender_dist.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(processed_posts)) * 100
        print(f"  {gender}: {count} ({percentage:.1f}%)")
    
    # Age distribution
    age_dist = {}
    for post in processed_posts:
        age = post['age_group']
        age_dist[age] = age_dist.get(age, 0) + 1
    
    print("\nAge distribution:")
    for age, count in sorted(age_dist.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(processed_posts)) * 100
        print(f"  {age}: {count} ({percentage:.1f}%)")
    
    # Occupation distribution
    occupation_dist = {}
    for post in processed_posts:
        occ = post['occupation']
        occupation_dist[occ] = occupation_dist.get(occ, 0) + 1
    
    print("\nOccupation distribution:")
    for occ, count in sorted(occupation_dist.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(processed_posts)) * 100
        print(f"  {occ}: {count} ({percentage:.1f}%)")
    
    # Save processed data
    output_file = 'data/voz_preprocessed.json'
    print(f"\nSaving preprocessed data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_posts, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved {len(processed_posts)} processed posts")
    
    # Save sample for inspection
    sample_file = 'data/voz_preprocessed_sample.json'
    print(f"\nSaving sample (first 10 posts) to {sample_file}...")
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump(processed_posts[:10], f, ensure_ascii=False, indent=2)
    
    print("\n=== PREPROCESSING COMPLETE ===")
    print(f"Output: {output_file}")
    print(f"Sample: {sample_file}")

if __name__ == "__main__":
    main()
