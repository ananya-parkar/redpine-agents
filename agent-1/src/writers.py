# agent-1/src/writers.py
import csv

BASE_FIELDNAMES = [
    "search_location",
    "radius_km",
    "hotel_name",
    "address",
    "rating",
    "user_rating_count",
    "business_status",
    "distress_score",
    "distress_reasons",
    "google_maps_url",
]

PRIORITY_EXTRA_FIELDNAMES = [
    "was_franchise",
    "former_brand",
    "franchise_confidence",
    "franchise_evidence",
    "property_match_found",
    "property_match_confidence",
    "property_record_source",
    "property_record_address",
    "property_record_owner_hint",
    "property_record_match_score",
    "property_record_evidence",
]


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def save_csv_files(run_dir, all_rows):
    output_csv = run_dir / "hotel_distress_results.csv"
    write_csv(output_csv, all_rows, BASE_FIELDNAMES)
    print(f"\n[OUTPUT] Saved CSV: {output_csv}", flush=True)

    priority_rows = [row for row in all_rows if row["distress_score"] >= 7]
    priority_csv = run_dir / "hotel_distress_priority.csv"
    write_csv(priority_csv, priority_rows, BASE_FIELDNAMES + PRIORITY_EXTRA_FIELDNAMES)
    print(f"[OUTPUT] Saved filtered CSV: {priority_csv}", flush=True)