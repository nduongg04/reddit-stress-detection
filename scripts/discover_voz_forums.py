"""
Script to discover all available forums on voz.vn
"""
import cloudscraper
from bs4 import BeautifulSoup
import json

def discover_forums():
    """Discover all forums on voz.vn homepage"""
    
    print("=" * 80)
    print("VOZ.VN FORUM DISCOVERY")
    print("=" * 80)
    print()
    
    # Initialize scraper
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows'}
    )
    
    # Fetch homepage
    print("Fetching https://voz.vn ...")
    response = scraper.get('https://voz.vn')
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all forum links
    forums = []
    seen_urls = set()
    
    # Method 1: Find by node-title class
    for link in soup.find_all('a', class_='node-title'):
        href = link.get('href')
        title = link.get_text(strip=True)
        
        if href and href not in seen_urls:
            # Extract forum ID from URL
            # Format: /f/forum-name.ID/ or /f/forum-name.ID
            if '/f/' in href:
                forum_id = href.split('/')[-1] if not href.endswith('/') else href.split('/')[-2]
                forums.append({
                    'title': title,
                    'url': href,
                    'forum_id': forum_id
                })
                seen_urls.add(href)
    
    # Method 2: Find all links with /f/ pattern
    for link in soup.find_all('a', href=True):
        href = link.get('href')
        if href and '/f/' in href and href not in seen_urls:
            title = link.get_text(strip=True)
            if title and len(title) > 0:
                forum_id = href.split('/')[-1] if not href.endswith('/') else href.split('/')[-2]
                forums.append({
                    'title': title,
                    'url': href,
                    'forum_id': forum_id
                })
                seen_urls.add(href)
    
    # Print results
    print(f"\n{'='*80}")
    print(f"FOUND {len(forums)} FORUMS")
    print(f"{'='*80}\n")
    
    # Group by category
    stress_related = []
    
    stress_keywords = [
        'tâm sự', 'tình yêu', 'gia đình', 'hôn nhân', 'học đường',
        'công việc', 'sức khỏe', 'tâm lý', 'xã hội', 'pháp luật',
        'giáo dục', 'sinh viên', 'phụ nữ', 'đàn ông', 'tuổi teen',
        'cha mẹ', 'con cái', 'vợ chồng'
    ]
    
    for forum in forums:
        title_lower = forum['title'].lower()
        
        print(f"📁 {forum['title']}")
        print(f"   URL: https://voz.vn{forum['url']}")
        print(f"   ID: {forum['forum_id']}")
        
        # Check if stress-related
        is_stress = any(keyword in title_lower for keyword in stress_keywords)
        if is_stress:
            stress_related.append(forum)
            print(f"   ⭐ STRESS-RELATED")
        
        print()
    
    # Print stress-related summary
    print(f"\n{'='*80}")
    print(f"STRESS-RELATED FORUMS: {len(stress_related)}")
    print(f"{'='*80}\n")
    
    for forum in stress_related:
        print(f"✅ {forum['title']} -> {forum['forum_id']}")
    
    # Save to JSON
    output = {
        'all_forums': forums,
        'stress_related': stress_related,
        'total_forums': len(forums),
        'stress_forums_count': len(stress_related)
    }
    
    with open('data/voz_forums_discovered.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Saved to data/voz_forums_discovered.json")
    
    return stress_related


if __name__ == "__main__":
    discover_forums()
