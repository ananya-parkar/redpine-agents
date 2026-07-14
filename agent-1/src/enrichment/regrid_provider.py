# agent-1/src/enrichment/regrid_provider.py
import json
import requests
from src.core.config import REGRID_API_KEY
from src.collectors.property_records import normalize_address, address_similarity, extract_street
from math import radians, sin, cos, sqrt, atan2

ADDRESS_SEARCH_URL = "https://app.regrid.com/api/v2/parcels/address"


def lookup_property(address, latitude=None, longitude=None):

    headers = {
        "accept": "application/json"
    }

    query = (
        address
        .replace(", USA", "")
        .strip()
    )
    print("QUERYING REGRID FOR ADDRESS:", query)

    params = {
        "query": query,
        "token": REGRID_API_KEY
    }
        
    response = requests.get(
        ADDRESS_SEARCH_URL,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()
    print("REQUEST URL:", response.url)

    data = response.json()

    # SAVE RAW RESPONSE
    with open("regrid_response.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("Saved Regrid response to regrid_response.json")

    print("Top level keys:", data.keys())

    parcels = data.get("parcels")
    print("Parcels type:", type(parcels))

    if isinstance(parcels, dict):
        print("Parcel keys:", parcels.keys())

    features = data.get("parcels", {}).get("features", [])

    print("Feature count:", len(features))

    if not features:
        return None

    # If only one parcel, return it
    if len(features) == 1:
        return features[0]

    requested = extract_street(address)

    print("\nMatching returned parcels...\n")

    for feature in features:
        fields = feature.get("properties", {}).get("fields", {})

        returned = extract_street(
            fields.get("address")
            or fields.get("original_address")
            or ""
        )

        if returned == requested:
            print("✓ Exact street match found")
            return feature

    # Fallback: street number + street name match
    best_feature = None
    best_score = 0

    for feature in features:
        fields = feature.get("properties", {}).get("fields", {})
        returned = extract_street(
            fields.get("address")
            or fields.get("original_address")
            or ""
        )

        similarity = address_similarity(requested, returned)

        print(
            f"[ADDRESS MATCH] {requested} <-> {returned} = {similarity}%"
        )

        if similarity > best_score:
            best_score = similarity
            best_feature = feature

    if best_score >= 80:
        print(f"✓ Best address match ({best_score}%)")
        return best_feature

    print("⚠ No sufficiently similar address found.")
    return None
    
def haversine(lat1, lon1, lat2, lon2):

    R = 6371000

    lat1 = radians(float(lat1))
    lon1 = radians(float(lon1))
    lat2 = radians(float(lat2))
    lon2 = radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c