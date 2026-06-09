# agent-1/src/utils/entity_builder.py
from src.core.models import HotelEntity
from src.utils.utils import extract_hotel_name

def build_hotel_entity(hotel_data, source_location="", radius_km=0):
    return HotelEntity(
        hotel_name=extract_hotel_name(hotel_data),
        address=hotel_data.get("formattedAddress", ""),
        place_id=hotel_data.get("id", ""),
        latitude=hotel_data.get("location", {}).get("latitude"),
        longitude=hotel_data.get("location", {}).get("longitude"),
        rating=hotel_data.get("rating"),
        user_rating_count=hotel_data.get("userRatingCount"),
        business_status=hotel_data.get("businessStatus"),
        google_maps_url=hotel_data.get("googleMapsUri"),
        reviews=hotel_data.get("reviews", []),
        source_location=source_location,
        radius_km=radius_km,
    )