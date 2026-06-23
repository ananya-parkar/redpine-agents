# agent-3/main.py
import json, re
from discovery.universe_builder import (
    load_geography, 
    generate_search_queries, 
    search_query, 
    save_candidate_universe
)
from discovery.company_extractor import (extract_companies_with_llm)
from discovery.search_request import load_search_request
from discovery.universe_filter import load_filtered_universe, classify_company
import pandas as pd
from config import INPUT_FOLDER, DATA_FOLDER, OUTPUT_FOLDER, US_STATE_MAP
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
DEV_MODE = True
def main():

    criteria = load_search_request(INPUT_FOLDER / "search_request.xlsx")
    target_geography = criteria["geography"]
    min_years = criteria["min_years"]
    revenue_range = criteria["revenue_range"]
    industry = criteria["industry"]
    ownership_preference = criteria["ownership_preference"]
    founder_age_preference = criteria["founder_age"]

    print("\nRunning Agent 3\n")
    print("Target Geography:")
    print(criteria)

    queries = generate_search_queries(
        geography=target_geography,
        revenue_range=revenue_range,
        min_years=min_years,
        ownership=ownership_preference,
    )

    print("\nGenerated Queries:\n")
    for query in queries:
        print(query)

    print("\nTesting Tavily Query:\n")
    print(queries)

    all_results = []

    for query in queries:
        print(f"\nRunning Query: {query}")

        response = search_query(query)

        all_results.extend(
            response.get("results", [])
        )

    all_companies = []

    for item in all_results:
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
    
    def normalize_company_name(name):
        suffixes = [
            " inc",
            " inc.",
            " llc",
            " ltd",
            " ltd.",
            " corp",
            " corp.",
            " corporation",
            " co",
            " co.",
            " company",
            " holdings",
            " holding"
        ]
        normalized = name.lower()
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        return normalized.strip()

    unique_companies = {}
    for company in company_names:
        normalized = normalize_company_name(company)
        if normalized not in unique_companies:
            unique_companies[normalized] = company

    company_names = sorted(unique_companies.values())
    if DEV_MODE:
        company_names = company_names[:20]

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
    raw_signal_repository = []
    scored_rows = []

   # for end to end testing remove later.
    if DEV_MODE:
        companies_df = companies_df.head(10)

    for _, row in companies_df.iterrows():
        company_name = row["Company Name"]
        print(f"\nProcessing: {company_name}")
        
        signals = collect_signals(company_name, target_geography)
        raw_signal_repository.append({
            "company_name": company_name,
            "raw_content": signals["raw_content"],
            "source_urls": signals["source_urls"]
        })

        extracted = extract_signals(signals["raw_content"])
        score = calculate_seller_readiness(extracted)
        founder_age = extracted.get(
            "founder_age_estimate",
            "Unknown"
        )

        if (
            founder_age_preference == "60+"
            and founder_age != "Unknown"
        ):
            try:
                age = int(founder_age.split("-")[0])

                if age < 60:
                    continue

            except:
                pass

        if extracted.get("extraction_confidence") == "Low":
            print(f"Skipping {company_name} due to low confidence")
            continue

        years_in_business = score.get("years_in_business", 0)
        if years_in_business < min_years:
            print(
                f"Skipping {company_name} "
                f"because age is only "
                f"{years_in_business} years"
            )
            continue

        revenue = extracted.get("revenue_estimate","Unknown")
        # For the time being
        # if revenue != revenue_range:
        #     print(
        #         f"Skipping {company_name} "
        #         f"because revenue band is "
        #         f"{revenue}"
        #     )
        #     continue

        print(
            f"Revenue={revenue} | "
            f"Years={years_in_business}"
        )
        if revenue not in [revenue_range, "Unknown"]:
            continue

        company_state = extracted.get("state", "Unknown")
        target_state = target_geography
        expected_state = US_STATE_MAP.get(target_state, target_state)

        if company_state not in [expected_state, "Unknown"]:
            print(
                f"Skipping {company_name} "
                f"because state is {company_state}"
            )
            continue

        ownership_status = extracted.get(
            "ownership_status",
            "Unknown"
        )

        if (
            ownership_preference != "Any"
            and ownership_status not in [
                ownership_preference,
                "Unknown"
            ]
        ):
            print(
                f"Skipping {company_name} "
                f"because ownership is {ownership_status}"
            )
            continue

        print(extracted)
        print(score)

        if (
            extracted.get("founder_name") == "Unknown"
            and extracted.get("family_owned") != "Yes"
            and extracted.get("founder_led") != "Yes"
        ):
            print(
                f"Skipping {company_name} "
                "because no founder/family signal found"
            )
            continue

        scored_rows.append({
            "Company Name": company_name,
            "Industry": extracted.get("industry"),
            "State": extracted.get("state"),
            "Company Type":extracted.get("company_type"),
            "Founded Year": extracted.get("founded_year"),
            "Revenue Estimate": extracted.get("revenue_estimate"),
            "Years in Business": score.get("years_in_business"),
            "Founder Name": extracted.get("founder_name"),
            "Founder Led": extracted.get("founder_led"),
            "Family Owned": extracted.get("family_owned"),
            "Founder Age Estimate": extracted.get("founder_age_estimate"),
            "Seller Readiness Score": score.get("seller_readiness_score"),
            "Evidence Summary": " | ".join(extracted.get("evidence_summary", [])),
            "Evidence Sources": ";".join(sorted(set(signals["source_urls"]))),
            "Extraction Confidence": extracted.get("extraction_confidence"),
            "Ownership Status": extracted.get("ownership_status"),
            "Ownership Tenure Years": extracted.get("ownership_tenure_years"),

        })

    with open(DATA_FOLDER / "raw_signals.json", "w", encoding="utf-8") as f:
        json.dump(raw_signal_repository, f, indent=2)

    output_df = pd.DataFrame(scored_rows)
    output_df.to_csv(OUTPUT_FOLDER / "agent3_scored_candidates.csv", index=False)
    
    print(f"\nSaved {len(output_df)} scored companies")
    if output_df.empty:
        print("\nNo candidates survived filtering.")
        return
            
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