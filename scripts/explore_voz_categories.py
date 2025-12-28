"""
Script to explore VOZ category structure and find stress-related forums
"""
import cloudscraper
from bs4 import BeautifulSoup
import json
import time

def explore_categories():
    """Explore all categories and their forums"""
    
    print("=" * 80)
    print("VOZ.VN CATEGORY EXPLORATION")
    print("=" * 80)
    print()
    
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows'}
    )
    
    # Known stress-related category: Sinh hoạt (ID: 7)
    # Let's explore multiple category pages
    categories_to_check = [
        ('https://voz.vn/c/sinh-hoat.7/', 'Sinh hoạt'),
        ('https://voz.vn/c/cong-nghe.5/', 'Công nghệ'),
        ('https://voz.vn/c/giai-tri.12/', 'Giải trí'),
        ('https://voz.vn/c/thi-truong.16/', 'Thị trường'),
        ('https://voz.vn/c/hoc-tap.15/', 'Học tập'),
    ]
    
    all_forums = []
    stress_related = []
    
    stress_keywords = [
        'tâm sự', 'tình yêu', 'gia đình', 'hôn nhân', 'học đường',
        'công việc', 'sức khỏe', 'tâm lý', 'xã hội', 'pháp luật',
        'giáo dục', 'sinh viên', 'phụ nữ', 'đàn ông', 'tuổi teen',
        'cha mẹ', 'con cái', 'vợ chồng', 'giới tính'
    ]
    
    for url, category_name in categories_to_check:
        print(f"\n📂 Exploring category: {category_name}")
        print(f"   URL: {url}")
        
        try:
            response = scraper.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find forum blocks
            forum_blocks = soup.find_all('div', class_='node-body')
            
            for block in forum_blocks:
                # Find forum link
                title_link = block.find('a', class_='node-title')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                if not href or '/f/' not in href:
                    continue
                
                # Extract forum ID
                forum_id = href.split('/')[-1] if not href.endswith('/') else href.split('/')[-2]
                
                # Get description
                description_elem = block.find('div', class_='node-description')
                description = description_elem.get_text(strip=True) if description_elem else ''
                
                # Get thread count
                stats = block.find('dl', class_='pairs--justified')
                thread_count = 0
                if stats:
                    count_dd = stats.find('dd')
                    if count_dd:
                        thread_count = count_dd.get_text(strip=True)
                
                forum_info = {
                    'title': title,
                    'url': href,
                    'forum_id': forum_id,
                    'category': category_name,
                    'description': description,
                    'thread_count': thread_count
                }
                
                all_forums.append(forum_info)
                
                # Check if stress-related
                title_lower = title.lower()
                desc_lower = description.lower()
                
                is_stress = any(
                    keyword in title_lower or keyword in desc_lower
                    for keyword in stress_keywords
                )
                
                if is_stress:
                    stress_related.append(forum_info)
                    print(f"   ⭐ {title} -> {forum_id} ({thread_count} threads)")
                else:
                    print(f"   📁 {title} -> {forum_id} ({thread_count} threads)")
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total forums found: {len(all_forums)}")
    print(f"Stress-related forums: {len(stress_related)}")
    print()
    
    print("STRESS-RELATED FORUMS:")
    print("-" * 80)
    for forum in stress_related:
        print(f"✅ {forum['title']}")
        print(f"   ID: {forum['forum_id']}")
        print(f"   Category: {forum['category']}")
        print(f"   Threads: {forum['thread_count']}")
        print(f"   Description: {forum['description'][:100]}...")
        print()
    
    # Save results
    output = {
        'all_forums': all_forums,
        'stress_related': stress_related,
        'total_forums': len(all_forums),
        'stress_forums_count': len(stress_related)
    }
    
    with open('data/voz_categories_explored.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Saved to data/voz_categories_explored.json")
    
    return stress_related


if __name__ == "__main__":
    explore_categories()
