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

    queries = [
        f'"{company_name}" headquartered in {state}',
        f'"{company_name}" founder',
        f'"{company_name}" leadership',
        f'"{company_name}" about us'
    ]

    all_results = []

    for query in queries:
        response = tavily_client.search(query=query, search_depth="advanced", max_results=3)
        all_results.extend(response.get("results", []))

    return {"results": all_results}

def collect_signals(company_name, state):
    search_results = search_company(company_name, state)
    content =[]
    source_urls =[]

    for result in search_results.get("results", []):
        url = result.get("url", "")

        LOW_QUALITY_DOMAINS = [
            "prospeo.io",
            "datanyze.com",
            "leadiq.com",
            "mapquest.com",
            "comparably.com",
            "rocketreach.co",
            "cbinsights.com",
            "visualvisitor.com",
            "promptloop.com",
            "leadnear.com",
            "bitscale.ai"
        ]

        if any(domain in url for domain in LOW_QUALITY_DOMAINS):
                continue
        
        content.append(result.get("content", ""))
        if url and url not in source_urls:
            source_urls.append(url)
                        
            
    print("\nCONTENT LENGTH:")
    print(len("\n".join(content)))

    print("\nSOURCES:")
    print(source_urls)

    return {
        "company_name": company_name,
        "raw_content": "\n".join(content),
        "source_urls": source_urls
    }

