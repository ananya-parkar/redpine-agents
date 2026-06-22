# agent-3/main.py

from discovery.universe_builder import (
    load_geography, 
    generate_search_queries, 
    search_query, 
    save_candidate_universe
)
from discovery.company_extractor import (extract_companies_with_llm)
from discovery.universe_filter import load_filtered_universe, classify_company
import pandas as pd
from config import INPUT_FOLDER, DATA_FOLDER, OUTPUT_FOLDER
from collection.signal_collection import collect_signals
from extraction.signal_extractor import extract_signals
from scoring.seller_readiness import calculate_seller_readiness
from deduplication.dedupe import run_deduplication
from reasoning.llm_reasoning import run_reasoning
from mail.email import send_daily_digest
from db.db import save_candidates_to_db, record_pipeline_run_snapshot
from db.feedback_sync import sync_feedback_from_dashboard
from db.pii_retention import apply_pii_retention


from dashboard.dashboard import generate_dashboard
def main():
    geography = load_geography(INPUT_FOLDER / "geography.json")

    print("\nRunning Agent 3\n")
    print("Target Geography:")
    print(geography)

    queries = generate_search_queries(geography["geography_type"], geography["geography_value"])

    print("\nGenerated Queries:\n")
    for query in queries:
        print(query)

    print("\nTesting Tavily Query:\n")
    print(queries[0])

    tavily_response = search_query(
        queries[0]
    )

    all_companies = []
    for item in tavily_response["results"]:
        print()
        print(item["title"])
        companies = extract_companies_with_llm(
            item.get("content", "")
        )
        print(companies)
        all_companies.extend(companies)

    company_names = []
    for company in all_companies:
        if "company_name" in company:
            company_names.append(
                company["company_name"]
            )

    company_names = sorted(list(set(company_names)))

    # # TEMP TEST
    # company_names = company_names[:20]
    
    raw_df = pd.DataFrame({"Company Name": company_names})
    save_candidate_universe(raw_df, DATA_FOLDER / "candidate_universe.csv")

    filtered_rows = []
    for company in company_names:
        result = classify_company(company)
        print(company, result["decision"])
        if result["decision"] == "KEEP":
            filtered_rows.append({
                "Company Name": company,
                "Universe Status": result["decision"],
                "Reason": result["reason"]
            })

    df = pd.DataFrame(filtered_rows)
    print(df.head())

    print("\nTavily Response:\n")
    save_candidate_universe(df, DATA_FOLDER / "filtered_candidate_universe.csv")
    
    print("\nStarting Signal Collection + Scoring...\n")
    companies_df = load_filtered_universe(DATA_FOLDER / "filtered_candidate_universe.csv")
    scored_rows = []

    for _, row in companies_df.head(5).iterrows():
        company_name = row["Company Name"]
        print(f"\nProcessing: {company_name}")
        
        signals = collect_signals(company_name, geography["geography_value"])
        extracted = extract_signals(signals["raw_content"])
        score = calculate_seller_readiness(extracted)
        print(extracted)
        print(score)

        scored_rows.append({
            "Company Name": company_name,
            "Industry": extracted.get("industry"),
            "State": extracted.get("state"),
            "Company Type":extracted.get("company_type"),
            "Founded Year": extracted.get("founded_year"),
            "Years in Business": score.get("years_in_business"),
            "Founder Name": extracted.get("founder_name"),
            "Founder Led": extracted.get("founder_led"),
            "Family Owned": extracted.get("family_owned"),
            "Founder Age Estimate": extracted.get("founder_age_estimate"),
            "Seller Readiness Score": score.get("seller_readiness_score"),
            "Evidence Summary": " | ".join(extracted.get("evidence_summary", []))
        })
    
    output_df = pd.DataFrame(scored_rows)
    output_df.to_csv(OUTPUT_FOLDER / "agent3_scored_candidates.csv", index=False)
    print(f"\nSaved {len(output_df)} scored companies")
    
    # Anshika Code
    output_df.to_csv(OUTPUT_FOLDER / "agent3_scored_candidates.csv", index=False)
    print(f"\nSaved {len(output_df)} scored companies")

    print("\nStarting Deduplication Layer...\n")
    deduped_df = run_deduplication(
        scored_df=output_df,
        output_file=OUTPUT_FOLDER / "deduplicated_candidates.csv"
    )
    print(f"\n{len(deduped_df)} new, deduplicated candidates ready for ranking")
    print("\nStarting LLM Reasoning Layer...\n")
    final_df = run_reasoning(
        deduped_file=OUTPUT_FOLDER / "deduplicated_candidates.csv",
        output_file=OUTPUT_FOLDER / "candidates_with_rationale.csv"
    )
    print(f"\nFinal output: {len(final_df)} candidates with rationale ready for dashboard")

    print("\nSaving to Postgres...\n")
    save_candidates_to_db(final_df)
    print("\nRecording run snapshot...\n")
    record_pipeline_run_snapshot()
    print("\nSyncing feedback from previous run...\n")
    sync_feedback_from_dashboard(OUTPUT_FOLDER / "agent3_dashboard.xlsx")

    print("\nGenerating Excel dashboard...\n")
    generate_dashboard(OUTPUT_FOLDER / "agent3_dashboard.xlsx")
    print("\nSending daily email digest...\n")
    send_daily_digest(
    new_candidates_df=final_df,
    dashboard_file_path=OUTPUT_FOLDER / "agent3_dashboard.xlsx")
    print("\nChecking PII retention policy...\n")
    apply_pii_retention(dry_run=False)

    

if __name__ == "__main__":
    main()