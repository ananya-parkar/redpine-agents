# agent-3/discovery/search_request.py
import pandas as pd

def load_search_request(file_path):
    df = pd.read_excel(file_path)
    if df.empty:
        raise ValueError("search_request.xlsx is empty")

    row = df.iloc[0]
    return {
        "geography": row.get("Geography"),
        "industry": row.get("Industry", "Any"),
        "revenue_range": row.get("Revenue Range"),
        "min_years": int(row.get("Min Years") or 0),
        "ownership_preference": row.get("Ownership Preference", "Any"),
        "founder_age": row.get("Founder Age", "Any")
    }