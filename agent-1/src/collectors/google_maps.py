# agent-1/src/collectors/google_maps.py
import requests
from typing import List, Dict, Tuple
from src.core.config import GOOGLE_MAPS_API_KEY, GEOCODE_URL, NEARBY_URL, PLACE_DETAILS_URL_TEMPLATE

def geocode_location(location: str) -> Tuple[float, float]:
    resp = requests.get(GEOCODE_URL, params={"address": location, "key": GOOGLE_MAPS_API_KEY}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("results"):
        raise ValueError(f"Could not geocode location: {location}")

    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]

def nearby_hotels(lat: float, lng: float, radius_miles: float) -> List[Dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": ",".join([
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.location",
            "places.rating",
            "places.userRatingCount",
            "places.businessStatus",
            "places.googleMapsUri",
            "places.reviews"
        ])
    }

    payload = {
        "includedTypes": ["hotel"],
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": radius_miles * 1609.34
            }
        }
    }

    resp = requests.post(
        NEARBY_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    resp.raise_for_status()
    places = resp.json().get("places", [])
    print(
        f"[GOOGLE] Returned {len(places)} hotels",
        flush=True
    )

    return places

def place_details(place_id: str) -> Dict:
    headers = {
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": ",".join([
            "id",
            "displayName",
            "formattedAddress",
            "rating",
            "userRatingCount",
            "businessStatus",
            "googleMapsUri",
            "reviews"
        ])
    }

    url = PLACE_DETAILS_URL_TEMPLATE.format(place_id=place_id)
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()