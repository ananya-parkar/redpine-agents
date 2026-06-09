# agent-1/src/analysis/review_intelligence.py
from collections import Counter
import re

THEME_KEYWORDS = {
    "cleanliness": [
        "dirty",
        "filthy",
        "stained",
        "unhygienic",
        "smell",
        "odor",
        "mold",
        "cockroach",
        "bed bug"
    ],

    "staff": [
        "rude",
        "staff",
        "service",
        "manager",
        "employee",
        "front desk"
    ],

    "maintenance": [
        "broken",
        "maintenance",
        "repair",
        "run down",
        "not maintained",
        "outdated",
        "old",
        "renovation"
    ],

    "noise": [
        "noise",
        "loud",
        "music",
        "traffic"
    ],

    "safety": [
        "unsafe",
        "security",
        "crime",
        "dangerous"
    ]
}

def extract_review_themes(reviews):
    counts = Counter()
    for review in reviews:
        text = (review.get("text", {}).get("text", "").lower())
        for theme, keywords in THEME_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    counts[theme] += 1
    total = sum(counts.values())
    if total == 0:
        return {}
    return {
        theme: round((count / total) * 100, 1)
        for theme, count in counts.items()
    }