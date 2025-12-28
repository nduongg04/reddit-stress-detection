#!/usr/bin/env python3
"""
Find the correct forum IDs by testing ID numbers directly
"""
import cloudscraper
from bs4 import BeautifulSoup
import time

def find_forums():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    
    # Test these IDs directly
    test_ids = [3, 5, 14, 17, 21, 22, 33]
    
    print("\n=== TESTING FORUM IDs DIRECTLY ===\n")
    
    for forum_id in test_ids:
        print(f"Testing ID {forum_id}...", end=" ")
        try:
            url = f"https://voz.vn/f/test.{forum_id}/"
            response = scraper.get(url, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title_elem = soup.find('h1', class_='p-title-value')
                
                if title_elem:
                    actual_title = title_elem.text.strip()
                    actual_url = response.url
                    
                    # Extract actual forum slug from URL
                    if '/f/' in actual_url:
                        forum_slug = actual_url.split('/f/')[1].rstrip('/')
                    else:
                        forum_slug = "unknown"
                    
                    # Count threads
                    thread_items = soup.find_all('div', class_='structItem--thread')
                    thread_count = len(thread_items)
                    
                    print(f"✓ {actual_title}")
                    print(f"       URL: {actual_url}")
                    print(f"       Slug: {forum_slug}")
                    print(f"       Threads on page 1: {thread_count}")
                else:
                    print("✗ No title found")
            else:
                print(f"✗ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"✗ Error: {str(e)}")
        
        time.sleep(0.5)
    
    print("\n" + "="*60)

if __name__ == "__main__":
    find_forums()
