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
            "Seller Readiness Score": score.get("seller_readiness_score")
        })
    
    output_df = pd.DataFrame(scored_rows)
    output_df.to_csv(OUTPUT_FOLDER / "agent3_scored_candidates.csv", index=False)
    print(f"\nSaved {len(output_df)} scored companies")

if __name__ == "__main__":
    main()