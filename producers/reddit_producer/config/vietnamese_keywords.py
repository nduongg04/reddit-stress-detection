"""
Vietnamese Keywords for Stress Detection

Stress-related and non-stress keywords for collecting Vietnamese Reddit posts.
"""

# Stress-related keywords (target: ~2,500 posts)
STRESS_KEYWORDS_VI = [
    # Core emotional states
    "căng thẳng",      # stress, tension
    "trầm cảm",        # depression
    "lo âu",           # anxiety
    "thất bại",        # failure
    "buồn",            # sad
    "chán nản",        # depressed, dispirited
    "tuyệt vọng",      # hopeless
    "thất vọng",       # disappointed
    "mệt mỏi",         # tired, exhausted
    "suy sụp",         # collapsed, broken down
    "choáng ngợp",     # overwhelmed
    "lo lắng",         # worried
    "sợ hãi",          # fearful
    "đau khổ",         # suffering
    "buồn rầu",        # sorrowful
    "phiền muộn",      # troubled
    "áp lực",          # pressure
    "stress",          # stress (English term used in Vietnamese)
    "khủng hoảng",     # crisis
    "cô đơn",          # lonely
    "tự ti",           # inferiority complex
    "hoảng loạn",      # panic
    "trống rỗng",      # empty
    "vô vọng",         # hopeless
]

# Extended stress keywords for r/vozforums (optimized for Vietnamese forums)
VOZFORUMS_STRESS_KEYWORDS = [
    # Core stress (from main list)
    "căng thẳng", "trầm cảm", "lo âu", "thất bại", "mệt mỏi",
    "suy sụp", "áp lực", "stress", "khủng hoảng", "cô đơn",

    # Mental health specific
    "sức khỏe tinh thần", "tâm lý", "tư vấn tâm lý", "trị liệu",
    "kiệt sức", "burnout", "overthinking", "suy nghĩ quá nhiều",
    "mất ngủ", "insomnia", "anxiety", "depression",

    # Work/study stress
    "áp lực công việc", "deadline", "quá tải", "làm việc nhiều",
    "áp lực học tập", "thi cử", "điểm thấp", "sa thải",

    # Relationship stress
    "chia tay", "thất tình", "cãi nhau", "mâu thuẫn", "đau lòng",
    "bị phản bội", "cô độc", "xa cách",

    # Life difficulties
    "khó khăn", "vấn đề", "rắc rối", "tệ hại", "tồi tệ",
    "không may", "xui xẻo", "bất lực", "vô dụng",
]

# Non-stress keywords (target: ~2,500 posts)
NON_STRESS_KEYWORDS_VI = [
    # Travel & Leisure
    "du lịch",         # travel
    "đi chơi",         # go out, hanging out
    "nghỉ dưỡng",      # vacation
    "phượt",           # backpacking

    # Food & Dining
    "ăn uống",         # eating, dining
    "món ăn",          # dishes, food
    "nhà hàng",        # restaurant
    "quán cà phê",     # coffee shop
    "đặc sản",         # specialty food

    # Entertainment
    "giải trí",        # entertainment
    "phim ảnh",        # movies
    "âm nhạc",         # music
    "ca sĩ",           # singer
    "game",            # games
    "vui vẻ",          # happy, cheerful

    # Sports & Hobbies
    "thể thao",        # sports
    "bóng đá",         # football/soccer
    "chạy bộ",         # running
    "yoga",            # yoga
    "sở thích",        # hobby
    "tập gym",         # gym workout

    # Social & Lifestyle
    "bạn bè",          # friends
    "gia đình",        # family
    "sinh nhật",       # birthday
    "cuối tuần",       # weekend
    "mua sắm",         # shopping
    "thời trang",      # fashion
    "làm đẹp",         # beauty care

    # Learning & Success
    "học tập",         # studying (positive context)
    "công việc mới",   # new job (positive)
    "thành công",      # success
    "chiến thắng",     # victory
    "đạt được",        # achieve

    # Positive emotions
    "hạnh phúc",       # happiness
    "vui mừng",        # joyful
    "tốt đẹp",         # beautiful, good
    "tuyệt vời",       # wonderful
]


def get_stress_search_query() -> str:
    """
    Build Reddit search query for stress-related Vietnamese posts.

    Returns:
        OR-joined query string
    """
    return ' OR '.join([f'"{kw}"' for kw in STRESS_KEYWORDS_VI])


def get_non_stress_search_query() -> str:
    """
    Build Reddit search query for non-stress Vietnamese posts.

    Returns:
        OR-joined query string
    """
    return ' OR '.join([f'"{kw}"' for kw in NON_STRESS_KEYWORDS_VI])


def get_vozforums_stress_query() -> str:
    """
    Build Reddit search query for r/vozforums stress posts.

    Returns:
        OR-joined query string optimized for vozforums
    """
    return ' OR '.join([f'"{kw}"' for kw in VOZFORUMS_STRESS_KEYWORDS])


if __name__ == "__main__":
    # Test queries
    print("Stress Keywords Query:")
    print(get_stress_search_query()[:200] + "...")
    print(f"\nTotal stress keywords: {len(STRESS_KEYWORDS_VI)}")

    print("\n" + "="*60)
    print("\nNon-Stress Keywords Query:")
    print(get_non_stress_search_query()[:200] + "...")
    print(f"\nTotal non-stress keywords: {len(NON_STRESS_KEYWORDS_VI)}")
