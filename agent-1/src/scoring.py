# agent-1/src/scoring.py
from typing import Dict, Tuple, List
from src.config import DISTRESS_KEYWORDS

def distress_score(place: Dict) -> Tuple[int, List[str]]:
    score = 0
    reasons = []

    rating = place.get("rating")
    rating_count = place.get("userRatingCount", 0)
    business_status = place.get("businessStatus", "")
    reviews = place.get("reviews", []) or []

    if rating is not None and rating < 3.5:
        score += 2
        reasons.append(f"Low rating: {rating}")

    if rating_count and rating_count > 20 and rating is not None and rating < 4.0:
        score += 1
        reasons.append(f"Moderate-to-low rating with enough reviews: {rating_count}")

    if business_status and business_status != "OPERATIONAL":
        score += 3
        reasons.append(f"Business status: {business_status}")

    review_text_blob = []
    for review in reviews:
        text = ""
        if isinstance(review, dict):
            text_field = review.get("text", "")
            if isinstance(text_field, dict):
                text = text_field.get("text", "")
            else:
                text = text_field
        if text:
            review_text_blob.append(text.lower())

    joined_reviews = " ".join(review_text_blob)

    for word in DISTRESS_KEYWORDS["negative"]:
        if word in joined_reviews:
            score += 1
            reasons.append(f"Negative review signal: {word}")

    for word in DISTRESS_KEYWORDS["financial_or_operational"]:
        if word in joined_reviews:
            score += 2
            reasons.append(f"Operational distress signal: {word}")

    return score, reasons[:10]