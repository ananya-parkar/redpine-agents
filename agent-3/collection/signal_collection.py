# agent-3/collection/signal_collection.py
import pandas as pd
import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv(override=True)
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def load_candidate_universe(input_file):
    return pd.read_csv(input_file)

def search_company(company_name, state):
    query = f"{company_name} headquartered in {state}"
    return tavily_client.search(query=query, search_depth="advanced", max_results=5)

def collect_signals(company_name, state):
    search_results = search_company(company_name, state)
    content =[]
    source_urls =[]

    for result in search_results.get("results", []):
        content.append(result.get("content", ""))
        source_urls.append(result.get("url", ""))
    
    print("\nCONTENT LENGTH:")
    print(len("\n".join(content)))

    print("\nSOURCES:")
    print(source_urls)

    return {
        "company_name": company_name,
        "raw_content": "\n".join(content),
        "source_urls": source_urls
    }

