# agent-1/src/writers.py
import pandas as pd
from src.config import DISTRESS_SCORE_THRESHOLD

BASE_FIELDNAMES = [
    "rank",
    "final_lead_score",
    "lead_reason",
    "search_location",
    "radius_km",
    "hotel_name",
    "address",
    "source_provenance",
    "rating",
    "user_rating_count",
    "business_status",
    "distress_score",
    "distress_reasons",
    "review_trend_score",
    "review_volume_recent",
    "review_volume_prior",
    "review_volume_change_pct",
    "avg_rating_recent",
    "avg_rating_prior",
    "review_rating_delta",
    "complaint_rate_recent",
    "complaint_rate_prior",
    "review_complaint_delta",
    "year_built",
    "property_age",
    "renovation_signal_rate",
    "renovation_needed",
    "physical_condition_score",
    "google_maps_url",
    "llm_distress_probability",
    "llm_seller_fatigue_probability",
    "llm_opportunity_score",
    "llm_confidence",
    "llm_top_distress_signals",
    "llm_investment_thesis",
    "llm_recommended_action",
    "llm_distress_summary",
    "llm_review_summary",
    "created_at",
]

PRIORITY_EXTRA_FIELDNAMES = [
    "franchise_affiliated",
    "current_brand",
    "former_brand",
    "brand_status",
    "franchise_confidence",
    "franchise_evidence",

    "cmbs_loan_status",
    "cmbs_delinquency_flag",
    "cmbs_watchlist_flag",
    "cmbs_special_servicing_flag",
    "cmbs_confidence",
    "cmbs_evidence",

    "owner_name",
    "owner_company",
    "mailing_address",
    "owner_phone",
    "owner_confidence",
    "owner_evidence",
    "ownership_since",
    "ownership_length_years",
    "attom_year_built",
    "is_older_than_20_years",
]

def write_excel(path, rows, fieldnames):
    df = pd.DataFrame(rows)

    for col in fieldnames:
        if col not in df.columns:
            df[col] = ""
    
    df = df[fieldnames]
    df.to_excel(path, index=False, engine="openpyxl")
    print(f"\n[OUTPUT] Saved Excel: {path}", flush=True)

def save_excel_files(run_dir, all_rows):
    for row in all_rows:
        llm = row.get("llm_analysis", {})
        row["llm_distress_probability"] = llm.get("distress_probability")
        row["llm_seller_fatigue_probability"] = llm.get("seller_fatigue_probability")
        row["llm_opportunity_score"] = llm.get("opportunity_score")
        row["llm_confidence"] = llm.get("confidence")
        row["llm_top_distress_signals"] = " | ".join(llm.get("top_distress_signals", []))
        row["llm_investment_thesis"] = llm.get("investment_thesis")
        row["llm_recommended_action"] = llm.get("recommended_action")
        row["llm_distress_summary"] = llm.get("distress_summary")
        row["llm_review_summary"] = llm.get("review_summary")

    
    # Full Results Excel
    output_excel = run_dir / "hotel_distress_results.xlsx"
    write_excel(output_excel, all_rows, BASE_FIELDNAMES)
    print(f"\n[OUTPUT] Saved Excel: {output_excel}", flush=True)

    # Priority Leads Excel  
    priority_rows = [row for row in all_rows if row.get("final_lead_score", 0) >= 40]
    priority_excel = run_dir/ "hotel_distress_priority.xlsx"
    write_excel(priority_excel, priority_rows, BASE_FIELDNAMES + PRIORITY_EXTRA_FIELDNAMES)
    print(f"[OUTPUT] Saved Excel: {priority_excel}", flush=True)