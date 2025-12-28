"""
Test more forum ID patterns to find active stress-related forums
"""
import cloudscraper
from bs4 import BeautifulSoup
import time

def test_more_forums():
    """Test additional forum patterns"""
    
    print("=" * 80)
    print("TESTING MORE FORUM IDS")
    print("=" * 80)
    print()
    
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows'}
    )
    
    # Test more IDs around known working forums
    # Known working: 17, 18, 19, 82, 87, 95, 96, 97, 307
    test_patterns = []
    
    # Test sequential IDs
    for i in range(1, 110):
        test_patterns.append(f"test.{i}")
    
    # Also test some specific name patterns
    name_patterns = [
        'phu-nu', 'tuoi-teen', 'nguoi-tre', 'tre-em',
        'suc-khoe', 'tam-ly', 'tinh-than', 'suc-khoe-tam-than',
        'benh-tat', 'dieu-tri', 'cham-soc-suc-khoe',
        'giao-duc', 'dao-tao', 'hoc-hanh', 'sinh-vien',
        'nghe-nghiep', 'viec-lam', 'su-nghiep',
        'tai-chinh-ca-nhan', 'tiet-kiem', 'quan-ly-tai-chinh',
        'moi-quan-he', 'tinh-ban', 'dong-nghiep',
        'cuoc-song', 'khung-hoang', 'kho-khan',
        'ky-nang-song', 'phat-trien-ban-than'
    ]
    
    found_forums = []
    tested_count = 0
    
    print("Testing forum IDs...")
    print()
    
    for pattern in test_patterns:
        tested_count += 1
        
        # Construct URL
        url = f"https://voz.vn/f/{pattern}/"
        
        try:
            response = scraper.get(url, timeout=5)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check if it's a valid forum page
                title_elem = soup.find('h1', class_='p-title-value')
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    
                    # Get actual URL after redirect
                    actual_url = response.url
                    
                    # Extract forum ID from actual URL
                    if '/f/' in actual_url:
                        forum_slug = actual_url.split('/f/')[-1].rstrip('/')
                        
                        # Check if forum has threads
                        thread_items = soup.find_all('div', class_='structItem--thread')
                        thread_count = len(thread_items)
                        
                        # Get thread statistics
                        stats_elem = soup.find('div', class_='block-container')
                        
                        forum_info = {
                            'forum_id': forum_slug,
                            'title': title,
                            'url': actual_url,
                            'has_threads': thread_count > 0,
                            'threads_on_page': thread_count,
                            'tested_pattern': pattern
                        }
                        
                        # Check if it's new (not already in our list)
                        known_ids = [
                            'tam-su-cuoc-song.17', 'hoc-duong.82', 
                            'gia-dinh-hon-nhan.95', 'suc-khoe-gioi-tinh.18',
                            'noi-chuyen-cong-viec.307', 'tinh-yeu.87',
                            'xa-hoi-phap-luat.19', 'vo-chong.96', 'cha-me.97'
                        ]
                        
                        if forum_slug not in known_ids and thread_count > 0:
                            found_forums.append(forum_info)
                            print(f"✅ NEW: {title} ({forum_slug})")
                            print(f"   URL: {actual_url}")
                            print(f"   Threads on page 1: {thread_count}")
                            print()
            
            # Rate limiting
            time.sleep(0.3)
            
            # Progress indicator
            if tested_count % 20 == 0:
                print(f"   ... tested {tested_count} patterns")
            
        except Exception as e:
            continue
    
    # Print summary
    print()
    print("=" * 80)
    print(f"FOUND {len(found_forums)} NEW ACTIVE FORUMS")
    print("=" * 80)
    print()
    
    # Filter stress-related
    stress_keywords = [
        'tâm sự', 'tình yêu', 'gia đình', 'hôn nhân', 'học',
        'công việc', 'sức khỏe', 'tâm lý', 'xã hội', 'pháp luật',
        'giáo dục', 'sinh viên', 'phụ nữ', 'tuổi', 'cha', 'mẹ',
        'con', 'vợ', 'chồng', 'trẻ', 'người', 'cuộc sống', 'bạn bè',
        'mối quan hệ', 'cảm xúc', 'stress', 'áp lực'
    ]
    
    stress_forums = []
    other_forums = []
    
    for forum in found_forums:
        title_lower = forum['title'].lower()
        is_stress = any(kw in title_lower for kw in stress_keywords)
        
        if is_stress:
            stress_forums.append(forum)
        else:
            other_forums.append(forum)
    
    print("STRESS-RELATED FORUMS:")
    print("-" * 80)
    for forum in stress_forums:
        print(f"⭐ {forum['title']}")
        print(f"   ID: {forum['forum_id']}")
        print(f"   Threads: {forum['threads_on_page']}")
        print()
    
    print("\nOTHER FORUMS:")
    print("-" * 80)
    for forum in other_forums:
        print(f"📁 {forum['title']}")
        print(f"   ID: {forum['forum_id']}")
        print(f"   Threads: {forum['threads_on_page']}")
        print()
    
    # Save results
    import json
    output = {
        'stress_related': stress_forums,
        'other_forums': other_forums,
        'total_new_forums': len(found_forums),
        'stress_count': len(stress_forums),
        'other_count': len(other_forums)
    }
    
    with open('data/voz_new_forums_found.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Saved to data/voz_new_forums_found.json")
    
    return stress_forums


if __name__ == "__main__":
    test_more_forums()
