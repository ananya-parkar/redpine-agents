# agent-1/main.py
import time
from datetime import datetime

from src.core.config import INPUT_FILE, RUNS_DIR, GOOGLE_MAPS_API_KEY
from src.utils.io_utils import parse_locations, save_json
from src.core.pipeline import process_location
from src.utils.writers import save_excel_files
from src.utils.exporters import save_ai_entities
# from src.dedupe import remove_existing_leads
from src.storage.postgres_dedupe import remove_existing_postgres_leads
# from src.master_storage import append_to_master
from src.reporting.html.html_report import generate_html_report
from src.storage.postgres_storage import insert_priority_leads
from src.reporting.dashboard.dashboard_export import export_dashboard
from src.reporting.email.email_digest import send_run_digest
from src.storage.postgres_storage import get_feedback_patterns
from src.analysis.feedback_learning import apply_feedback_penalties, build_feedback_rules
from src.feedback.dashboard_sync import sync_dashboard_feedback
from src.storage.feedback_actions import create_feedback_action, action_already_exists

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
            if not action_already_exists(reason):

                create_feedback_action(
                    reason=reason,
                    count=count,
                    action=f"Applied scoring rule for {reason}"
                )

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
    dashboard_file = export_dashboard(reports_dir)
    print(f"[OUTPUT] Dashboard exported to: {dashboard_file}", flush=True)

    for row in priority_rows:
        print(
            row.get("hotel_name"),
            "suppress_digest=", row.get("suppress_digest"),
            "is_pursuing=", row.get("is_pursuing"),
            "score_change=", row.get("score_change")
        )
    send_run_digest(
        priority_rows=priority_rows,
        dashboard_file=dashboard_file,
        html_report=run_dir / "hotel_acquisition_report.html"
    )

    
if __name__ == "__main__":
    main()