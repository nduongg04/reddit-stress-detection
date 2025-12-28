"""
Test additional forum IDs to find more stress-related forums
"""
import cloudscraper
from bs4 import BeautifulSoup
import time

def test_forum_ids():
    """Test potential forum IDs to find active stress-related forums"""
    
    print("=" * 80)
    print("TESTING POTENTIAL FORUM IDS")
    print("=" * 80)
    print()
    
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows'}
    )
    
    # Currently known working forums
    known_forums = [
        ("tam-su-cuoc-song.17", "Tâm sự cuộc sống"),
        ("hoc-duong.82", "Học đường"),
        ("gia-dinh-hon-nhan.95", "Gia đình hôn nhân"),
        ("suc-khoe-gioi-tinh.18", "Sức khỏe giới tính"),
        ("noi-chuyen-cong-viec.307", "Nơi chuyện công việc"),
        ("tinh-yeu.87", "Tình yêu"),
        ("xa-hoi-phap-luat.19", "Xã hội pháp luật"),
    ]
    
    # Additional potential forum IDs based on pattern
    # ID ranges to test: 1-100
    potential_ids = list(range(1, 101))
    
    # Also test specific patterns
    forum_name_patterns = [
        'tam-ly', 'suc-khoe', 'benh-tat', 'cham-soc-ban-than',
        'phu-nu', 'dan-ong', 'tuoi-teen', 'nguoi-lon-tuoi',
        'cha-me', 'con-cai', 'vo-chong', 'ban-be',
        'cong-viec', 'hoc-tap', 'sinh-vien', 'nghe-nghiep',
        'tai-chinh', 'tiet-kiem', 'dau-tu',
        'giao-duc', 'dao-tao', 'ky-nang-song',
        'stress', 'depression', 'anxiety', 'mental-health'
    ]
    
    found_forums = []
    
    print("Testing ID ranges...")
    for forum_id in potential_ids:
        # Test format: something.ID
        test_url = f"https://voz.vn/f/test.{forum_id}/"
        
        try:
            response = scraper.get(test_url, timeout=5)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check if it's a valid forum page
                title_elem = soup.find('h1', class_='p-title-value')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    
                    # Get actual forum slug from URL
                    actual_url = response.url
                    if '/f/' in actual_url:
                        forum_slug = actual_url.split('/f/')[-1].rstrip('/')
                        
                        forum_info = {
                            'forum_id': forum_slug,
                            'title': title,
                            'url': actual_url,
                            'tested_id': forum_id
                        }
                        
                        found_forums.append(forum_info)
                        print(f"✅ Found: {title} -> {forum_slug}")
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            if forum_id % 10 == 0:
                print(f"   Tested up to ID {forum_id}...")
            continue
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"FOUND {len(found_forums)} ACTIVE FORUMS")
    print(f"{'='*80}\n")
    
    # Compare with known forums
    new_forums = []
    known_ids = {f[0] for f in known_forums}
    
    for forum in found_forums:
        if forum['forum_id'] not in known_ids:
            new_forums.append(forum)
    
    print(f"NEW FORUMS (not in current list): {len(new_forums)}\n")
    
    for forum in new_forums:
        print(f"🆕 {forum['title']}")
        print(f"   ID: {forum['forum_id']}")
        print(f"   URL: {forum['url']}")
        print()
    
    return new_forums


if __name__ == "__main__":
    test_forum_ids()
