#!/usr/bin/env python3
"""
Test if the user-requested forums exist on voz.vn
"""
import cloudscraper
from bs4 import BeautifulSoup

def test_forums():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    
    # Forums requested by user
    forums_to_test = [
        ("chuyen-tro-linh-tinh.17", "F17 - Chuyện trò linh tinh"),
        ("tam-su-tuoi-hong.33", "F33 - Tâm sự tuổi hồng / Tâm sự cuộc sống"),
        ("hoc-tap-giao-duc.14", "F14 - Học tập - Giáo dục"),
        ("cong-viec-nghe-nghiep.22", "F22 - Công việc - Nghề nghiệp"),
        ("chuyen-tien-nong.21", "F21 - Chuyện tiền nong / Tài chính"),
        ("suc-khoe.5", "F5 - Sức khỏe"),
        ("cong-nghe.3", "F3 - IT / Công nghệ"),
    ]
    
    # Already crawled forums
    already_crawled = [
        "tam-su-cuoc-song.17",  # Tâm sự cuộc sống
        "hoc-duong.82",         # Học đường
        "gia-dinh-hon-nhan.95", # Gia đình
        "tinh-yeu.87",          # Tình yêu
    ]
    
    print("\n=== TESTING NEW FORUMS ===\n")
    
    found_forums = []
    missing_forums = []
    
    for forum_id, name in forums_to_test:
        print(f"Testing {name}...", end=" ")
        try:
            url = f"https://voz.vn/f/{forum_id}/"
            response = scraper.get(url, timeout=10)
            
            if response.status_code == 200:
                # Check if it's a valid forum page
                soup = BeautifulSoup(response.text, 'html.parser')
                title_elem = soup.find('h1', class_='p-title-value')
                
                if title_elem:
                    actual_title = title_elem.text.strip()
                    
                    # Count threads on first page
                    thread_items = soup.find_all('div', class_='structItem--thread')
                    thread_count = len(thread_items)
                    
                    # Check if already crawled
                    if forum_id in already_crawled:
                        print(f"✓ EXISTS (Already crawled) - {actual_title} ({thread_count} threads on page 1)")
                    else:
                        print(f"✓ EXISTS (NEW!) - {actual_title} ({thread_count} threads on page 1)")
                        found_forums.append((forum_id, actual_title, thread_count))
                else:
                    print("✗ Not a valid forum page")
                    missing_forums.append(forum_id)
            else:
                print(f"✗ HTTP {response.status_code}")
                missing_forums.append(forum_id)
                
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            missing_forums.append(forum_id)
    
    print("\n" + "="*60)
    print("\n=== SUMMARY ===\n")
    
    if found_forums:
        print(f"NEW FORUMS TO CRAWL ({len(found_forums)}):\n")
        for forum_id, title, thread_count in found_forums:
            print(f"  • {forum_id}: {title} ({thread_count} threads on page 1)")
    else:
        print("No new forums found (all requested forums already crawled or don't exist)")
    
    if missing_forums:
        print(f"\nMISSING/INVALID FORUMS ({len(missing_forums)}):\n")
        for forum_id in missing_forums:
            print(f"  • {forum_id}")
    
    return found_forums

if __name__ == "__main__":
    test_forums()
