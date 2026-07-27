# agent-1/main.py
import time, pickle
from datetime import datetime
from uuid import uuid4
from src.core.config import INPUT_FILE, INPUT_FOLDER, RUNS_DIR, GOOGLE_MAPS_API_KEY
from src.utils.io_utils import parse_locations, save_json
from src.input.search_request import load_search_request
from src.core.pipeline import process_location
from src.utils.writers import save_excel_files
from src.utils.exporters import save_ai_entities
# from src.dedupe import remove_existing_leads
from src.storage.postgres_dedupe import remove_existing_postgres_leads
# from src.master_storage import append_to_master
from src.reporting.html.html_report import generate_html_report
from src.storage.postgres_storage import insert_priority_leads, insert_agent_run
from src.reporting.dashboard.dashboard_export import export_dashboard
from src.reporting.email.email_digest import send_run_digest
from src.storage.postgres_storage import get_feedback_patterns, get_feedback_examples
from src.analysis.feedback_learning import apply_feedback_penalties, build_feedback_rules
from src.feedback.dashboard_sync import sync_dashboard_feedback
from src.feedback.feedback_recommendation_engine import generate_feedback_recommendation
from src.storage.feedback_actions import create_feedback_action, get_existing_trigger_count
from src.input_validation import validate_inputs

def main():
    run_id = uuid4()
    run_started = datetime.now()
    print("\n[START] Agent 1 run started\n", flush=True)

    if not GOOGLE_MAPS_API_KEY:
        raise ValueError("Please set GOOGLE_MAPS_API_KEY in your environment.")
    
    print(f"[INFO] Reading input file: {INPUT_FILE}", flush=True)
    request = load_search_request(INPUT_FILE)
    location = request["location"]
    radius_miles = request["radius_miles"]
    print(f"[INFO] Loaded search request: {location}", flush=True)

    validate_inputs(request)
    print("[VALIDATION] Input validation passed", flush=True)

    result = process_location(
    item={
            "location": request["location"],
            "radius_miles": request["radius_miles"],
            "min_rooms": request["min_rooms"],
            "max_rooms": request["max_rooms"],
            "year_built_range": request["year_built_range"],
            "price_tier": request["price_tier"]
        },
        loc_index=1,
        total_locations=1
    )

    geocode_results = result["geocode_results"]
    nearby_results = result["nearby_results"]
    details_results = result["details_results"]
    all_rows = result["rows"]

    # all_rows = remove_existing_leads(all_rows)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    print(INPUT_FILE)
    print(RUNS_DIR)

    print(f"[OUTPUT] Created run directory: {run_dir}", flush=True)

    print(
        f"[DEBUG] Before dedupe = {len(all_rows)}",
        flush=True
    )

    all_rows = remove_existing_postgres_leads(all_rows)

    print(
        f"[DEBUG] After dedupe = {len(all_rows)}",
        flush=True
    )
    print("\n[SORT] Sorting all hotel rows by distress_score descending", flush=True)
    rules = build_feedback_rules()

    for row in all_rows:
        apply_feedback_penalties(row, rules)

    all_rows.sort(key=lambda x: x.get("final_lead_score", 0), reverse=True)
    for idx, row in enumerate(all_rows, start=1):
        row["rank"] = idx

    priority_rows = [
        row for row in all_rows
        if row.get("final_lead_score", 0) >= 40
    ]
    
    save_excel_files(run_dir, all_rows)
    print(f"\n[DONE] Saved {len(all_rows)} hotel row(s) to {run_dir}", flush=True)

    print(type(geocode_results[0]))
    print(geocode_results[0])

    save_json(geocode_results, run_dir / "geocode_results.json")
    print("[OUTPUT] Saved geocode_results.json", flush=True)

    save_json(nearby_results, run_dir / "nearby_places.json")
    print("[OUTPUT] Saved nearby_places.json", flush=True)

    save_json(details_results, run_dir / "place_details.json")
    print("[OUTPUT] Saved place_details.json", flush=True)

    # append_to_master(priority_rows)
    # print("[OUTPUT] Updated master_leads.csv", flush=True)

    insert_priority_leads(priority_rows)
    print("[POSTGRES] Priority leads stored", flush=True)

    sync_dashboard_feedback()
    patterns = get_feedback_patterns()

    for reason, count in patterns:
        if count >= 3:
            existing_trigger_count = get_existing_trigger_count(reason)
            if count > existing_trigger_count:
                examples = get_feedback_examples(reason)
                recommendation = (generate_feedback_recommendation(reason, examples))
                create_feedback_action(reason=reason, count=count, action=recommendation["pipeline_fix"], recommendation_json=recommendation)

                print(
                    f"[FEEDBACK ACTION] "
                    f"{reason} flagged "
                    f"{count} times",
                    flush=True
                )

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

    reports_dir = run_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    print("\n===== CURRENT RUN =====")

    print(
        "Priority rows:",
        len(priority_rows)
    )

    for row in priority_rows[:20]:
        print(
            row.get("hotel_name"),
            row.get("final_lead_score"),
            row.get("suppress_digest")
        )
        
    # print("\n===== SAMPLE ROW =====")
    # print(priority_rows[0].keys())

    # print("owner_name =", priority_rows[0].get("owner_name"))
    # print("ownership_length_years =", priority_rows[0].get("ownership_length_years"))
    # print("signals =", priority_rows[0].get("signals"))
    # print("lead_reason =", priority_rows[0].get("lead_reason"))
    # print("llm_top_distress_signals =", priority_rows[0].get("llm_top_distress_signals"))

    # Save complete dashboard source for quick regeneration

    dashboard_source = run_dir / "dashboard_source.pkl"

    with open(dashboard_source, "wb") as f:
        pickle.dump(all_rows, f)

    print(
        f"[OUTPUT] Saved dashboard source: {dashboard_source}",
        flush=True
    )

    dashboard_file = export_dashboard(
        reports_dir,
        all_rows,
        search_area=request["location"]
    )
    print(f"[OUTPUT] Dashboard exported to: {dashboard_file}", flush=True)

    for row in priority_rows:
        print(
            row.get("hotel_name"),
            "suppress_digest=", row.get("suppress_digest"),
            "is_pursuing=", row.get("is_pursuing"),
            "score_change=", row.get("score_change")
        )

    # print("\n===== EMAIL DEBUG =====")

    for row in priority_rows:
        print(
            row.get("hotel_name"),
            "suppress_digest=",
            row.get("suppress_digest")
        )

    print(
        "TOTAL PRIORITY:",
        len(priority_rows)
    )

    print(
        "TOTAL UNSUPPRESSED:",
        len([
            r for r in priority_rows
            if not r.get("suppress_digest")
        ])
    )

    email_sent = True
    
    send_run_digest(
        priority_rows=priority_rows,
        dashboard_file=dashboard_file,
        html_report=run_dir / "hotel_acquisition_report.html"
    )

    run_completed = datetime.now()
    
    print("EMAIL SENT VALUE:", email_sent)
    insert_agent_run(
        run_id=str(run_id),
        started_at=run_started,
        completed_at=run_completed,
        search_area=request["location"],
        email_sent=email_sent,
        locations_processed=1,
        hotels_found=len(result["rows"]),
        hotels_after_dedupe=len(all_rows),
        new_leads=len(priority_rows),
        duplicates=len(result["rows"]) - len(all_rows),
        priority_leads=len(priority_rows),
    )

    
if __name__ == "__main__":
    main()