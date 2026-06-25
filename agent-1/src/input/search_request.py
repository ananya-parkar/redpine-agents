# agent-1/src/input/search_request.py
import pandas as pd

def clean(v):
    if pd.isna(v):
        return None
    return v

def load_search_request(file_path):
    df = pd.read_excel(file_path)
    if df.empty:
        raise ValueError("search_request.xlsx is empty")

    row = df.iloc[0]
    return {
        "location": clean(row.get("Location")),
        "radius_miles": clean(row.get("Radius Miles")),
        "min_rooms": clean(row.get("Min Rooms")),
        "max_rooms": clean(row.get("Max Rooms")),
        "year_built_range": clean(row.get("Year Built Range")),
        "price_tier": clean(row.get("Price Tier"))
    }