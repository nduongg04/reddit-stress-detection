"""
Script to deduplicate Voz posts and merge into single file
"""
import json
from pathlib import Path
from collections import defaultdict

def deduplicate_posts(input_files, output_file):
    """Merge multiple JSON files and remove duplicates by URL"""
    
    print("=" * 80)
    print("VOZ POSTS DEDUPLICATION")
    print("=" * 80)
    
    all_posts = []
    url_to_post = {}  # Track unique posts by URL
    stats = defaultdict(int)
    
    # Load all files
    for filepath in input_files:
        filepath = Path(filepath)
        if not filepath.exists():
            print(f"⚠️  File not found: {filepath}")
            continue
        
        print(f"\n📂 Loading {filepath.name}...")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                posts = json.load(f)
            
            file_unique = 0
            file_duplicates = 0
            
            for post in posts:
                url = post.get('url')
                if not url:
                    print(f"  ⚠️  Post without URL: {post.get('post_id', 'unknown')}")
                    continue
                
                # Check if URL already exists
                if url in url_to_post:
                    file_duplicates += 1
                    stats['total_duplicates'] += 1
                else:
                    url_to_post[url] = post
                    file_unique += 1
                    stats['total_unique'] += 1
            
            print(f"   ✓ Loaded {len(posts)} posts")
            print(f"   ✓ Unique: {file_unique}")
            print(f"   ✓ Duplicates: {file_duplicates}")
            
        except Exception as e:
            print(f"   ✗ Error loading {filepath}: {e}")
    
    # Convert to list
    unique_posts = list(url_to_post.values())
    
    # Forum distribution
    print(f"\n📊 Forum Distribution:")
    forum_counts = defaultdict(int)
    for post in unique_posts:
        forum = post.get('forum', 'Unknown')
        forum_counts[forum] += 1
    
    for forum, count in sorted(forum_counts.items(), key=lambda x: -x[1]):
        print(f"   {forum}: {count} posts")
    
    # Save deduplicated posts
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Saving {len(unique_posts)} unique posts to {output_path.name}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total unique posts: {stats['total_unique']}")
    print(f"Total duplicates removed: {stats['total_duplicates']}")
    print(f"Deduplication rate: {(stats['total_duplicates']/(stats['total_unique']+stats['total_duplicates'])*100):.1f}%")
    print(f"Output file: {output_path}")
    print("=" * 80)
    
    return unique_posts


if __name__ == "__main__":
    # Input files
    input_files = [
        "data/voz_10k_posts.json",
        "data/voz_10k_posts_continue.json",
        "data/voz_10k_posts_final.json"
    ]
    
    # Output file
    output_file = "data/voz_deduplicated.json"
    
    # Run deduplication
    unique_posts = deduplicate_posts(input_files, output_file)
    
    print(f"\n✅ Deduplication complete! {len(unique_posts)} unique posts saved.")
