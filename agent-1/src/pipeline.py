from src.google_maps import geocode_location, nearby_hotels, place_details
from src.scoring import distress_score
from src.enrichment import enrich_priority_hotel
from src.utils import extract_hotel_name, build_base_row


def process_location(item, loc_index, total_locations):
    print(
        f"\n[LOCATION {loc_index}/{total_locations}] Processing: "
        f"{item['location']} | radius_km={item['radius_km']}",
        flush=True
    )

    lat, lng = geocode_location(item["location"])
    print(f"\n[GEOCODE] {item['location']} -> latitude={lat}, longitude={lng}", flush=True)

    geocode_results = [{
        "location": item["location"],
        "radius_km": item["radius_km"],
        "latitude": lat,
        "longitude": lng
    }]

    hotels = nearby_hotels(lat, lng, item["radius_km"])
    print(f"\n[NEARBY SEARCH] Found {len(hotels)} hotel(s)", flush=True)

    nearby_results = [{
        "search_location": item["location"],
        "radius_km": item["radius_km"],
        "hotel_count": len(hotels),
        "hotels": hotels
    }]

    details_results = []
    rows = []

    for hotel_index, hotel in enumerate(hotels, start=1):
        row, hotel_details = process_hotel(item, hotel, hotel_index, len(hotels))
        rows.append(row)
        if hotel_details:
            details_results.append(hotel_details)

    return {
        "geocode_results": geocode_results,
        "nearby_results": nearby_results,
        "details_results": details_results,
        "rows": rows,
    }


def process_hotel(item, hotel, hotel_index, total_hotels):
    raw_hotel_name = extract_hotel_name(hotel)
    place_id = hotel.get("id")

    print(
        f"\n  [HOTEL {hotel_index}/{total_hotels}] {raw_hotel_name or 'Unnamed Hotel'}",
        flush=True
    )
    print(f"    [PLACE ID] {place_id}", flush=True)

    hotel_details = fetch_hotel_details(hotel, place_id)
    score_data = distress_score(hotel_details)
    score = score_data["distress_score"]
    reasons = score_data["distress_reasons"]
    hotel_name = extract_hotel_name(hotel_details)

    print(
        f"    [SCORING] score={score} | "
        f"trend_score={score_data['review_trend_score']} | "
        f"reasons={reasons[:3] if reasons else ['No distress signals found']}",
        flush=True
    )

    row = build_base_row(
        search_location=item["location"],
        radius_km=item["radius_km"],
        hotel_name=hotel_name,
        hotel_details=hotel_details,
        score_data=score_data,
    )

    if score >= 7:
        enrichment = enrich_priority_hotel(
            hotel_name=hotel_name or raw_hotel_name,
            address=hotel_details.get("formattedAddress", "")
        )
        row.update(enrichment)

    return row, hotel_details


def fetch_hotel_details(hotel, place_id):
    hotel_details = hotel

    if not place_id:
        print("    [DETAILS] Skipped: no place_id found", flush=True)
        return hotel_details

    try:
        print("    [DETAILS] Fetching place details...", flush=True)
        hotel_details = place_details(place_id)
        print("    [DETAILS] Success", flush=True)
        return hotel_details
    except Exception as e:
        print(f"    [DETAILS] Failed: {e}", flush=True)
        return hotel | {"details_error": str(e)}