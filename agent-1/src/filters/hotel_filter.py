#agent-1/src/filters/hotel_filter.py
HOTEL_KEYWORDS = [
    "hotel",
    "inn",
    "motel",
    "resort",
    "suites",
    "lodge"
]

EXCLUDED_KEYWORDS = [
    "consulting",
    "meeting",
    "conference",
    "spa",
    "travel agency",
    "receptive",
]

def is_valid_hotel(name):
    if not name:
        return False
    
    name_lower = name.lower()
    if any(x in name_lower for x in EXCLUDED_KEYWORDS):
        return False

    return any(x in name_lower for x in HOTEL_KEYWORDS)

