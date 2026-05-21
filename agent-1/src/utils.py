# agent-1/src/utils.py
def extract_hotel_name(hotel_data):
    name = hotel_data.get("displayName", {})
    if isinstance(name, dict):
        return name.get("text", "")
    if isinstance(name, str):
        return name
    return ""


def build_base_row(search_location, radius_km, hotel_name, hotel_details, score, reasons):
    return {
        "search_location": search_location,
        "radius_km": radius_km,
        "hotel_name": hotel_name,
        "address": hotel_details.get("formattedAddress", ""),
        "rating": hotel_details.get("rating", ""),
        "user_rating_count": hotel_details.get("userRatingCount", ""),
        "business_status": hotel_details.get("businessStatus", ""),
        "distress_score": score,
        "distress_reasons": " | ".join(reasons),
        "google_maps_url": hotel_details.get("googleMapsUri", "")
    }