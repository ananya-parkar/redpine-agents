#agent-1/src/filters/hotel_filter.py
BAD_NAME_KEYWORDS = [
    "llc",
    "llp",
    "inc",
    "corporation",
    "holdings",
    "properties"
]

def is_valid_hotel(place):
    name = place.get("name", "").strip().lower()

    if not name:
        return False

    # remove arabic / garbage names
    if len(name.split()) == 1:
        return False

    # remove company entities
    for keyword in BAD_NAME_KEYWORDS:
        if keyword in name:
            return False

    return True