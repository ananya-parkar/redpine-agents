# agent-3/discovery/universe_builder.py
import json
from config import UNIVERSE_SEARCH_QUERIES
import os
import pandas as pd
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(override=True)

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def load_geography(input_file):
    with open(input_file, "r") as f:
        geography = json.load(f)
    return geography

def generate_search_queries(geography, revenue_range, min_years, ownership):
    
    return [
        f"{ownership} companies in {geography}",
        f"family owned companies in {geography}",
        f"founder led companies in {geography}",
        f"private companies in {geography}",
        f"middle market companies in {geography}",
        f"companies in {geography} operating for more than {min_years} years"
    ]

def build_candidate_universe(geography_type, geography_value):
    pass

def save_candidate_universe(df, output_file):
    df.to_csv(output_file, index=False)
    print(f"\nSaved {len(df)} rows to {output_file}")
    
def search_query(query):
    response = tavily_client.search(query=query, search_depth="advanced", max_results=10)
    return response

def extract_candidate_companies(search_results):
    companies = []
    for result in search_results["results"]:
        companies.append({"Title": result["title"], "Source URL": result["url"]})
    return pd.DataFrame(companies)