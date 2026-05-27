# agent-1/src/main.py
import time
from datetime import datetime

from src.config import INPUT_FILE, RUNS_DIR, GOOGLE_MAPS_API_KEY
from src.io_utils import parse_locations, save_json
from src.pipeline import process_location
from src.writers import save_excel_files
from src.exporters import save_ai_entities
from src.dedupe import remove_existing_leads
from src.master_storage import append_to_master
from src.html_report import generate_html_report

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
        result = process_location(item=item, loc_index=loc_index, total_locations=len(locations))

        geocode_results.extend(result["geocode_results"])
        nearby_results.extend(result["nearby_results"])
        details_results.extend(result["details_results"])
        all_rows.extend(result["rows"])

        print("[WAIT] Sleeping for 1 second before next location...", flush=True)
        time.sleep(1)

    all_rows = remove_existing_leads(all_rows)
    print("\n[SORT] Sorting all hotel rows by distress_score descending", flush=True)
    all_rows.sort(key=lambda x: x.get("final_lead_score", 0), reverse=True)
    for idx, row in enumerate(all_rows, start=1):
        row["rank"] = idx

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

    save_excel_files(run_dir, all_rows)
    print(f"\n[DONE] Saved {len(all_rows)} hotel row(s) to {run_dir}", flush=True)
    
    priority_rows = [
        row for row in all_rows
        if row.get("final_lead_score", 0) >= 40
    ]
    
    append_to_master(priority_rows)
    print("[OUTPUT] Updated master_leads.csv", flush=True)
    
    save_ai_entities(
        run_dir / "priority_hotels_ai.json",
        priority_rows
    )

    print("[OUTPUT] Saved priority_hotels_ai.json", flush=True)

    priority_entities = []

    for row in priority_rows:
        entity = row.get("entity")
        if not entity:
            continue

        entity["final_lead_score"] = row.get("final_lead_score", 0)
        entity["rank"] = row.get("rank", 0)
        entity["lead_reason"] = row.get("lead_reason", "")
        priority_entities.append(entity)

    generate_html_report(
        run_dir / "hotel_acquisition_report.html",
        priority_entities
    )

    print(
        "[OUTPUT] Saved hotel_acquisition_report.html",
        flush=True
    )


if __name__ == "__main__":
    main()