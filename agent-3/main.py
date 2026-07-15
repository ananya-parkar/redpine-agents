# agent-3/main.py
from datetime import datetime
import pandas as pd

from discovery.company_discovery import discover_companies
from discovery.search_request import load_search_request

from config import INPUT_FOLDER, OUTPUT_FOLDER, RUNS_FOLDER, US_STATE_MAP

from collection.company_profile import profile_company
from scoring.seller_readiness import calculate_seller_readiness
from deduplication.dedupe import run_deduplication
from reasoning.llm_reasoning import run_reasoning
from mail.email import send_daily_digest

from db.db import save_candidates_to_db, record_pipeline_run_snapshot
from db.search_request_db import get_or_create_search_request
from db.feedback_sync import sync_feedback_from_dashboard
from db.pii_retention import apply_pii_retention

from dashboard.dashboard import generate_dashboard

def main():

    criteria = load_search_request(INPUT_FOLDER / "search_request.xlsx")
    target_geography       = criteria["geography"]
    min_years              = criteria["min_years"]
    revenue_range          = criteria["revenue_range"]
    industry               = criteria["industry"]
    ownership_preference   = criteria["ownership_preference"]
    founder_age_preference = criteria["founder_age"]

    # ------------------------------------------------------------------
    # Register this search. Same params as a previous run -> same id, so
    # dedupe history + client feedback carry over. ANY param changed ->
    # new id -> clean scope, so a Texas run never shows Florida leads.
    # ------------------------------------------------------------------
    search_request_id = get_or_create_search_request(criteria)

    print("\nRunning Agent 3\n")
    print(f"Search request id: {search_request_id}")
    print("Criteria:")
    print(criteria)

    companies = discover_companies(
        geography=target_geography,
        industry=industry,
        ownership_preference=ownership_preference,
        min_years=min_years,
        revenue_range=revenue_range,
        founder_age=founder_age_preference,
    )
    
    scored_rows = []

    for row in companies:
        company_name = row["company_name"]
        
        print(f"\nProcessing: {company_name}")

        profile = profile_company(
            company_name=company_name,
            state=row.get("state",""),
        )

        # Skip public companies completely.
        if profile.get("company_type", "Unknown") == "Public":
            print(f"Skipping {company_name} because it is a public company.")
            continue

        score = calculate_seller_readiness(profile)

        
        founder_age = profile.get("founder_age_estimate", "Unknown")
        if founder_age_preference == "60+":
            if founder_age not in ("", "Unknown", None):
                try:
                    age = int(founder_age.split("-")[0])
                    if age < 60:
                        continue
                except Exception:
                    pass

        confidence = profile.get("extraction_confidence", "Unknown")
        print("Confidence:", confidence)

        years_in_business = score.get("years_in_business", 0)
        try:
            years_in_business = int(years_in_business)
        except (TypeError, ValueError):
            years_in_business = 0

        try:
            min_years = int(min_years)
        except (TypeError, ValueError):
            min_years = 0



        if years_in_business < min_years:
            print(f"Skipping {company_name} because age is only {years_in_business} years")
            continue

        revenue = profile.get("revenue_estimate", "Unknown")
        print(f"Revenue={revenue} | Years={years_in_business}")

        company_state = str(profile.get("state", "")).strip().upper()
        expected = str(target_geography).strip()

        expected_full = expected.upper()
        expected_abbr = US_STATE_MAP.get(expected, expected).upper()

        if company_state not in (
            expected_full,
            expected_abbr,
            "",
            "UNKNOWN",
        ):
            print(f"Skipping {company_name} because state is {company_state}")
            continue
            
        ownership_status = profile.get("ownership_status", "Unknown")
        if ownership_preference != "Any":

            ownership_groups = {
                "Founder Owned": {"Founder Owned", "Family Owned"},
                "Family Owned": {"Founder Owned", "Family Owned"},
            }

            allowed = ownership_groups.get(
                ownership_preference,
                {ownership_preference},
            )

            allowed.add("Unknown")

            if ownership_status not in allowed:
                print(
                    f"Skipping {company_name} because ownership is {ownership_status}"
                )
                continue

        print(profile)
        print(score)

        scored_rows.append({
            "Company Name": company_name,
            "Industry": profile.get("industry"),
            "State": profile.get("state"),
            "Company Type": profile.get("company_type"),
            "Founded Year": profile.get("founded_year"),
            "Revenue Estimate": profile.get("revenue_estimate"),
            "Years in Business": score.get("years_in_business"),
            "Founder Name": profile.get("founder_name"),
            "Founder Led": profile.get("founder_led"),
            "Family Owned": profile.get("family_owned"),
            "Founder Age Estimate": profile.get("founder_age_estimate"),
            "Seller Readiness Score": score.get("seller_readiness_score"),
            "Seller Readiness Breakdown": str(
                score.get("score_breakdown", {})
            ),
            "Evidence Summary": " | ".join(profile.get("evidence_summary", [])),
            "Evidence Sources": ";".join(profile.get("source_urls", [])),
            "Extraction Confidence": profile.get("extraction_confidence"),
            "Ownership Status": profile.get("ownership_status"),
            "Ownership Tenure Years": profile.get("ownership_tenure_years"),
        })

    output_df = pd.DataFrame(scored_rows)
    output_df.to_csv(OUTPUT_FOLDER / "agent3_scored_candidates.csv", index=False)
    print(f"\nSaved {len(output_df)} scored companies")

    if output_df.empty:
        print("\nNo candidates survived filtering.")
        return

    # ------------------------------------------------------------------
    # Dedup is scoped: "have I seen this company FOR THIS SEARCH?"
    # A company already found under a DIFFERENT search is still new here.
    # ------------------------------------------------------------------
    print("\nStarting Deduplication Layer...\n")
    deduped_df = run_deduplication(
        scored_df=output_df,
        output_file=OUTPUT_FOLDER / "deduplicated_candidates.csv",
        search_request_id=search_request_id,
    )
    print(f"\n{len(deduped_df)} new, deduplicated candidates ready for ranking")

    print("\nStarting LLM Reasoning Layer...\n")
    final_df = run_reasoning(
        deduped_file=OUTPUT_FOLDER / "deduplicated_candidates.csv",
        output_file=OUTPUT_FOLDER / "candidates_with_rationale.csv",
    )
    print(f"\nFinal output: {len(final_df)} candidates with rationale")

    print("\nSaving to Postgres...\n")
    save_candidates_to_db(final_df, search_request_id)

    print("\nRecording run snapshot...\n")
    record_pipeline_run_snapshot(search_request_id)

    # ------------------------------------------------------------------
    # Runs folder is scoped per search too. Without this, a Florida run
    # followed by a Texas run would leave the Texas feedback sync
    # globbing the latest file in runs/ - which would be the FLORIDA
    # workbook. Its candidate_ids aren't in the Texas scope so nothing
    # would corrupt, but the Texas run would also never find its OWN
    # previous file, and feedback would silently stop syncing.
    # ------------------------------------------------------------------
    search_runs_folder = RUNS_FOLDER / f"search_{search_request_id}"
    search_runs_folder.mkdir(parents=True, exist_ok=True)

    dashboard_files = sorted(
        search_runs_folder.glob("agent3_dashboard_*.xlsx"),
        reverse=True,
    )

    if dashboard_files:
        print("\nSyncing feedback from previous run...\n")
        try:
            sync_feedback_from_dashboard(dashboard_files[0])
        except Exception as e:
            print(f"  [WARN] Feedback sync failed: {e}")
    else:
        print("\nNo previous dashboard for this search - nothing to sync.\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dashboard_file = search_runs_folder / f"agent3_dashboard_{timestamp}.xlsx"

    print("\nGenerating Excel dashboard...\n")
    generate_dashboard(dashboard_file, search_request_id)

    print("\nSending daily email digest...\n")
    send_daily_digest(
        new_candidates_df=final_df,
        dashboard_file_path=dashboard_file,
        search_request_id=search_request_id,
    )

    print("\nChecking PII retention policy...\n")
    apply_pii_retention(dry_run=False)


if __name__ == "__main__":
    main()