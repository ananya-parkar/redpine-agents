import csv
import time
from datetime import datetime

from src.config import INPUT_FILE, RUNS_DIR, GOOGLE_MAPS_API_KEY
from src.io_utils import parse_locations, save_json
from src.google_maps import geocode_location, nearby_hotels, place_details
from src.scoring import distress_score


def main():
    print("\n[START] Agent 1 run started\n", flush=True)

    if not GOOGLE_MAPS_API_KEY:
        raise ValueError("Please set GOOGLE_MAPS_API_KEY in your environment.")

    print(f"[INFO] Reading input file: {INPUT_FILE}", flush=True)
    locations = parse_locations(INPUT_FILE)
    print(f"[INFO] Loaded {len(locations)} location(s) from input", flush=True)

    geocode_results = []
    nearby_results = []
    details_results = []
    all_rows = []

    for loc_index, item in enumerate(locations, start=1):
        print(
            f"\n[LOCATION {loc_index}/{len(locations)}] Processing: "
            f"{item['location']} | radius_km={item['radius_km']}",
            flush=True
        )

        lat, lng = geocode_location(item["location"])
        print(
            f"\n[GEOCODE] {item['location']} -> latitude={lat}, longitude={lng}",
            flush=True
        )

        geocode_results.append({
            "location": item["location"],
            "radius_km": item["radius_km"],
            "latitude": lat,
            "longitude": lng
        })

        hotels = nearby_hotels(lat, lng, item["radius_km"])
        print(f"\n[NEARBY SEARCH] Found {len(hotels)} hotel(s)", flush=True)

        nearby_results.append({
            "search_location": item["location"],
            "radius_km": item["radius_km"],
            "hotel_count": len(hotels),
            "hotels": hotels
        })

        for hotel_index, hotel in enumerate(hotels, start=1):
            raw_hotel_name = hotel.get("displayName", {})
            if isinstance(raw_hotel_name, dict):
                raw_hotel_name = raw_hotel_name.get("text", "")
            elif not isinstance(raw_hotel_name, str):
                raw_hotel_name = ""

            place_id = hotel.get("id")
            print(
                f"\n  [HOTEL {hotel_index}/{len(hotels)}] {raw_hotel_name or 'Unnamed Hotel'}",
                flush=True
            )
            print(f"    [PLACE ID] {place_id}", flush=True)

            hotel_details = hotel

            if place_id:
                try:
                    print("    [DETAILS] Fetching place details...", flush=True)
                    hotel_details = place_details(place_id)
                    details_results.append(hotel_details)
                    print("    [DETAILS] Success", flush=True)
                except Exception as e:
                    hotel_details = hotel | {"details_error": str(e)}
                    print(f"    [DETAILS] Failed: {e}", flush=True)
            else:
                print("    [DETAILS] Skipped: no place_id found", flush=True)

            score, reasons = distress_score(hotel_details)

            hotel_name = hotel_details.get("displayName", {})
            if isinstance(hotel_name, dict):
                hotel_name = hotel_name.get("text", "")
            elif not isinstance(hotel_name, str):
                hotel_name = ""

            print(
                f"    [SCORING] score={score} | reasons={reasons[:3] if reasons else ['No distress signals found']}",
                flush=True
            )

            all_rows.append({
                "search_location": item["location"],
                "radius_km": item["radius_km"],
                "hotel_name": hotel_name,
                "address": hotel_details.get("formattedAddress", ""),
                "rating": hotel_details.get("rating", ""),
                "user_rating_count": hotel_details.get("userRatingCount", ""),
                "business_status": hotel_details.get("businessStatus", ""),
                "distress_score": score,
                "distress_reasons": " | ".join(reasons),
                "google_maps_url": hotel_details.get("googleMapsUri", "")
            })

        print("[WAIT] Sleeping for 1 second before next location...", flush=True)
        time.sleep(1)

    print("\n[SORT] Sorting all hotel rows by distress_score descending", flush=True)
    all_rows.sort(key=lambda x: x["distress_score"], reverse=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OUTPUT] Created run directory: {run_dir}", flush=True)

    save_json(geocode_results, run_dir / "geocode_results.json")
    print("[OUTPUT] Saved geocode_results.json", flush=True)

    save_json(nearby_results, run_dir / "nearby_places.json")
    print("[OUTPUT] Saved nearby_places.json", flush=True)

    save_json(details_results, run_dir / "place_details.json")
    print("[OUTPUT] Saved place_details.json", flush=True)

    output_csv = run_dir / "hotel_distress_results.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(all_rows[0].keys()) if all_rows else [
                "search_location", "radius_km", "hotel_name", "address", "rating",
                "user_rating_count", "business_status", "distress_score",
                "distress_reasons", "google_maps_url"
            ]
        )
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n[OUTPUT] Saved CSV: {output_csv}", flush=True)
    priority_rows = [row for row in all_rows if row["distress_score"] >= 7]
    priority_csv = run_dir / "hotel_distress_priority.csv"
    with priority_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(priority_rows[0].keys()) if priority_rows else [
                "search_location", "radius_km", "hotel_name", "address", "rating",
                "user_rating_count", "business_status", "distress_score",
                "distress_reasons", "google_maps_url"
            ]
        )
        writer.writeheader()
        writer.writerows(priority_rows)

    print(f"[OUTPUT] Saved filtered CSV: {priority_csv}", flush=True)
    print(f"\n[DONE] Saved {len(all_rows)} hotel row(s) to {run_dir}", flush=True)


if __name__ == "__main__":
    main()