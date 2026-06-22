# agent-3/main.py
import json, re
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
    raw_signal_repository = []
    scored_rows = []

    for _, row in companies_df.head(25).iterrows():
        company_name = row["Company Name"]
        print(f"\nProcessing: {company_name}")
        
        signals = collect_signals(company_name, geography["geography_value"])
        raw_signal_repository.append({
            "company_name": company_name,
            "raw_content": signals["raw_content"],
            "source_urls": signals["source_urls"]
        })

        extracted = extract_signals(signals["raw_content"])
        score = calculate_seller_readiness(extracted)

        if extracted.get("extraction_confidence") == "Low":
            print(f"Skipping {company_name} due to low confidence")
            continue

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
            "Evidence Summary": " | ".join(extracted.get("evidence_summary", [])),
            "Evidence Sources": ";".join(sorted(set(signals["source_urls"]))),
            "Extraction Confidence": extracted.get("extraction_confidence"),
            "Ownership Status": extracted.get("ownership_status")

        })

    with open(DATA_FOLDER / "raw_signals.json", "w", encoding="utf-8") as f:
        json.dump(raw_signal_repository, f, indent=2)

    output_df = pd.DataFrame(scored_rows)
    output_df.to_csv(OUTPUT_FOLDER / "agent3_scored_candidates.csv", index=False)
    print(f"\nSaved {len(output_df)} scored companies")

if __name__ == "__main__":
    main()