#!/usr/bin/env python3
"""
Search for stress-related forums by checking many IDs
"""
import cloudscraper
from bs4 import BeautifulSoup
import time
import json

def search_stress_forums():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    
    # Stress-related keywords
    stress_keywords = [
        "tâm sự", "cuộc sống", "tình yêu", "gia đình", "hôn nhân",
        "học", "đường", "giáo dục", "sinh viên", "học tập",
        "công việc", "nghề nghiệp", "việc làm", "nơi chuyện",
        "tiền", "tài chính", "kinh tế",
        "sức khỏe", "tâm lý", "y tế",
        "chuyện trò", "linh tinh", "tâm sự tuổi"
    ]
    
    # Test range of IDs
    test_range = list(range(1, 150))
    
    print("\n=== SEARCHING FOR STRESS-RELATED FORUMS ===\n")
    print("Testing IDs 1-150...")
    print()
    
    found_forums = []
    
    for forum_id in test_range:
        try:
            url = f"https://voz.vn/f/test.{forum_id}/"
            response = scraper.get(url, timeout=5, allow_redirects=True)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title_elem = soup.find('h1', class_='p-title-value')
                
                if title_elem:
                    actual_title = title_elem.text.strip().lower()
                    actual_url = response.url
                    
                    # Extract actual forum slug
                    if '/f/' in actual_url:
                        forum_slug = actual_url.split('/f/')[1].rstrip('/')
                    else:
                        continue
                    
                    # Check if stress-related
                    is_stress = any(keyword in actual_title for keyword in stress_keywords)
                    
                    if is_stress:
                        # Count threads
                        thread_items = soup.find_all('div', class_='structItem--thread')
                        thread_count = len(thread_items)
                        
                        print(f"✓ ID {forum_id}: {title_elem.text.strip()}")
                        print(f"  Slug: {forum_slug}")
                        print(f"  Threads: {thread_count} on page 1")
                        print()
                        
                        found_forums.append({
                            'id': forum_id,
                            'slug': forum_slug,
                            'title': title_elem.text.strip(),
                            'thread_count': thread_count
                        })
                        
        except Exception as e:
            pass
        
        if forum_id % 10 == 0:
            print(f"Progress: {forum_id}/150...", end="\r")
        
        time.sleep(0.3)
    
    print("\n" + "="*60)
    print(f"\n=== FOUND {len(found_forums)} STRESS-RELATED FORUMS ===\n")
    
    for forum in found_forums:
        print(f"ID {forum['id']}: {forum['title']}")
        print(f"  Slug: {forum['slug']}")
        print(f"  Threads: {forum['thread_count']}")
        print()
    
    # Save to file
    with open('data/stress_forums_found.json', 'w', encoding='utf-8') as f:
        json.dump(found_forums, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to data/stress_forums_found.json")
    
    return found_forums

if __name__ == "__main__":
    search_stress_forums()
