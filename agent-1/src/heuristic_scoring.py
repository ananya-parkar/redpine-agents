# agent-1/src/scoring.py
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from src.config import (
    DISTRESS_KEYWORDS, 
    REVIEW_LOOKBACK_MONTHS,
    RENOVATION_KEYWORDS,
    PROPERTY_AGE_THRESHOLD_YEARS
)

TREND_WINDOW_MONTHS = 6


def parse_review_datetime(review: Dict):
    publish_time = review.get("publishTime")
    if not publish_time:
        return None
    try:
        return datetime.fromisoformat(publish_time.replace("Z", "+00:00"))
    except Exception:
        return None


def extract_review_text(review: Dict) -> str:
    if not isinstance(review, dict):
        return ""
    text_field = review.get("text", "")
    if isinstance(text_field, dict):
        return (text_field.get("text") or "").strip()
    if isinstance(text_field, str):
        return text_field.strip()
    return ""


def extract_review_rating(review: Dict):
    rating = review.get("rating")
    if isinstance(rating, (int, float)):
        return float(rating)
    return None


def filter_recent_reviews(reviews: List[Dict], months: int = REVIEW_LOOKBACK_MONTHS) -> List[Dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
    filtered_reviews = []

    for review in reviews or []:
        review_dt = parse_review_datetime(review)
        if review_dt and review_dt >= cutoff:
            filtered_reviews.append(review)
            
    return filtered_reviews


def split_review_windows(reviews: List[Dict], window_months: int = TREND_WINDOW_MONTHS):
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=30 * window_months)
    prior_cutoff = now - timedelta(days=30 * window_months * 2)

    recent_reviews = []
    prior_reviews = []

    for review in reviews or []:
        review_dt = parse_review_datetime(review)
        if not review_dt:
            continue

        if review_dt >= recent_cutoff:
            recent_reviews.append(review)
        elif prior_cutoff <= review_dt < recent_cutoff:
            prior_reviews.append(review)

    return recent_reviews, prior_reviews


def average_rating(reviews: List[Dict]) -> float:
    ratings = [extract_review_rating(review) for review in reviews]
    ratings = [r for r in ratings if r is not None]
    if not ratings:
        return 0.0
    return round(sum(ratings) / len(ratings), 2)


def count_keyword_hits(reviews: List[Dict], keywords: List[str]) -> int:
    hits = 0
    for review in reviews or []:
        text = extract_review_text(review).lower()
        if not text:
            continue
        if any(word in text for word in keywords):
            hits += 1
        
    return hits


def complaint_rate(reviews: List[Dict]) -> float:
    if not reviews:
        return 0.0
    keywords = DISTRESS_KEYWORDS["negative"] + DISTRESS_KEYWORDS["financial_or_operational"]
    hits = count_keyword_hits(reviews, keywords)
    return round(hits / len(reviews), 2)


def renovation_signal_rate(reviews: List[Dict]) -> float:
    if not reviews:
        return 0.0
    hits = count_keyword_hits(reviews, RENOVATION_KEYWORDS)
    return round(hits / len(reviews), 2)


def pct_change(recent_value: float, prior_value: float) -> float:
    if prior_value == 0:
        if recent_value == 0:
            return 0.0
        return 100.0
    return round(((recent_value - prior_value) / prior_value) * 100, 2)


def extract_year_built(place: Dict) -> int:
    """
    Try to extract year built from Google Places data.
    Google Places doesn't have a dedicated yearBuilt field, so we try:
    - editorialSummary text parsing
    - reviews mentioning "built in YYYY"
    - fallback to None
    """
    # Check editorial summary for year mentions
    editorial = place.get("editorialSummary", {})
    if isinstance(editorial, dict):
        text = editorial.get("text", "")
    elif isinstance(editorial, str):
        text = editorial
    else:
        text = ""
    
    if text:
        import re
        # Look for "built in 1995" or "opened in 1980" patterns
        year_match = re.search(r'\b(built|opened|established|founded)\s+in\s+(\d{4})\b', text.lower())
        if year_match:
            year = int(year_match.group(2))
            if 1800 <= year <= datetime.now().year:
                return year
    
    return None


def calculate_property_age(year_built: int) -> int:
    if not year_built:
        return None
    return datetime.now().year - year_built


def distress_score(place: Dict) -> Dict:
    score = 0
    reasons = []

    rating = place.get("rating")
    rating_count = place.get("userRatingCount", 0)
    business_status = place.get("businessStatus", "")
    reviews = filter_recent_reviews(place.get("reviews", []) or [], months=REVIEW_LOOKBACK_MONTHS)

    # Existing rating-based signals
    if rating is not None and rating < 3.5:
        score += 2
        reasons.append(f"Low rating: {rating}")

    if rating_count and rating_count > 20 and rating is not None and rating < 4.0:
        score += 1
        reasons.append(f"Moderate-to-low rating with enough reviews: {rating_count}")

    if business_status and business_status != "OPERATIONAL":
        score += 3
        reasons.append(f"Business status: {business_status}")

    # Existing keyword scanning
    review_text_blob = []
    for review in reviews:
        text = extract_review_text(review)
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
    
    # Review trend scoring
    recent_reviews, prior_reviews = split_review_windows(reviews, window_months=TREND_WINDOW_MONTHS)
    review_volume_recent = len(recent_reviews)
    review_volume_prior = len(prior_reviews)
    review_volume_change_pct = pct_change(review_volume_recent, review_volume_prior)

    avg_rating_recent = average_rating(recent_reviews)
    avg_rating_prior = average_rating(prior_reviews)
    review_rating_delta = round(avg_rating_recent - avg_rating_prior, 2)

    complaint_rate_recent = complaint_rate(recent_reviews)
    complaint_rate_prior = complaint_rate(prior_reviews)
    review_complaint_delta = round(complaint_rate_recent - complaint_rate_prior, 2)

    review_trend_score = 0

    if review_volume_prior >= 3 and review_volume_change_pct <= -30:
        review_trend_score += 2
        reasons.append(f"Review volume decline: {review_volume_change_pct}%")

    if avg_rating_prior > 0 and review_rating_delta <= -0.3:
        review_trend_score += 2
        reasons.append(f"Rating decline: {review_rating_delta}")

    if review_complaint_delta >= 0.5:
        review_trend_score += 2
        reasons.append(f"Complaint rate increase: {review_complaint_delta}")

    score += review_trend_score

    # NEW: Property age and renovation signal
    year_built = extract_year_built(place)
    property_age = calculate_property_age(year_built)
    
    renovation_rate = renovation_signal_rate(reviews)
    renovation_needed = renovation_rate >= 0.3  # 30% of reviews mention renovation needs
    
    physical_condition_score = 0
    
    # Age signal (20+ years)
    age_20_plus = property_age and property_age >= PROPERTY_AGE_THRESHOLD_YEARS
    
    if age_20_plus:
        physical_condition_score += 1
        reasons.append(f"Property age {property_age} years (20+ threshold)")
    
    # Renovation signal
    if renovation_needed:
        physical_condition_score += 2
        reasons.append(f"Renovation signals in reviews: {renovation_rate:.1%}")
    
    # Combined signal: old property + renovation needed
    if age_20_plus and renovation_needed:
        physical_condition_score += 2
        reasons.append("Old property with visible renovation needs")
    
    score += physical_condition_score

    return {
        "distress_score": score,
        "distress_reasons": reasons[:10],
        "review_trend_score": review_trend_score,
        "review_volume_recent": review_volume_recent,
        "review_volume_prior": review_volume_prior,
        "review_volume_change_pct": review_volume_change_pct,
        "avg_rating_recent": avg_rating_recent,
        "avg_rating_prior": avg_rating_prior,
        "review_rating_delta": review_rating_delta,
        "complaint_rate_recent": complaint_rate_recent,
        "complaint_rate_prior": complaint_rate_prior,
        "review_complaint_delta": review_complaint_delta,
        "year_built": year_built or "",
        "property_age": property_age or "",
        "renovation_signal_rate": renovation_rate,
        "renovation_needed": renovation_needed,
        "physical_condition_score": physical_condition_score,
    }