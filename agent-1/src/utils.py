# agent-1/src/utils.py
def extract_hotel_name(hotel_data):
    name = hotel_data.get("displayName", {})
    if isinstance(name, dict):
        return name.get("text", "")
    if isinstance(name, str):
        return name
    return ""


def build_base_row(search_location, radius_km, hotel_name, hotel_details, score_data):
    return {
        "search_location": search_location,
        "radius_km": radius_km,
        "hotel_name": hotel_name,
        "address": hotel_details.get("formattedAddress", ""),
        "rating": hotel_details.get("rating", ""),
        "user_rating_count": hotel_details.get("userRatingCount", ""),
        "business_status": hotel_details.get("businessStatus", ""),
        "distress_score": score_data.get("distress_score", 0),
        "distress_reasons": " | ".join(score_data.get("distress_reasons", [])),
        "review_trend_score": score_data.get("review_trend_score", 0),
        "review_volume_recent": score_data.get("review_volume_recent", 0),
        "review_volume_prior": score_data.get("review_volume_prior", 0),
        "review_volume_change_pct": score_data.get("review_volume_change_pct", 0.0),
        "avg_rating_recent": score_data.get("avg_rating_recent", 0.0),
        "avg_rating_prior": score_data.get("avg_rating_prior", 0.0),
        "review_rating_delta": score_data.get("review_rating_delta", 0.0),
        "complaint_rate_recent": score_data.get("complaint_rate_recent", 0.0),
        "complaint_rate_prior": score_data.get("complaint_rate_prior", 0.0),
        "review_complaint_delta": score_data.get("review_complaint_delta", 0.0),
        "year_built": score_data.get("year_built", ""),
        "property_age": score_data.get("property_age", ""),
        "renovation_signal_rate": score_data.get("renovation_signal_rate", 0.0),
        "renovation_needed": score_data.get("renovation_needed", False),
        "physical_condition_score": score_data.get("physical_condition_score", 0),
        "google_maps_url": hotel_details.get("googleMapsUri", ""),
        "source_provenance": "Google Places | ATTOM | Tavily | SEC EDGAR",
    }