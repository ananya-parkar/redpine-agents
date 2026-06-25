# agent-1/src/analysis/property_filters.py
import pandas as pd

def passes_filters(row, search_config):
    # Year Built
    year_filter = search_config.get("year_built_range")
    if pd.isna(year_filter) or not str(year_filter).strip():
        year_filter = None
    if year_filter:
        start_year, end_year = [int(x.strip()) for x in str(year_filter).split("-")]
        year_built = int(row["attom_year_built"])
        if year_built < start_year:
            return False

        if year_built > end_year:
            return False 
        
    # Minimum Room Count
    min_rooms = search_config.get("min_rooms")
    if pd.isna(min_rooms) or not str(min_rooms).strip():
        min_rooms = None
    print(
        "[ROOM FILTER]",
        row.get("hotel_name"),
        "rooms=",
        row.get("room_count"),
        "required=",
        min_rooms
    )
    if min_rooms:
        room_count = row.get("room_count")
        if not room_count:
            return False
        try:
            room_count = int(room_count)
            if room_count < int(min_rooms):
                return False

        except Exception:
            return False

    # Maximum Room Count     

    max_rooms = search_config.get("max_rooms")
    if pd.isna(max_rooms) or not str(max_rooms).strip():
        max_rooms = None

    if max_rooms:
        room_count = row.get("room_count")

        if not room_count:
            return False

        try:
            room_count = int(room_count)

            if room_count > int(max_rooms):
                return False

        except Exception:
            return False
    
    # Price Tier
    requested_price_tier = search_config.get("price_tier")
    if pd.isna(requested_price_tier) or not str(requested_price_tier).strip():
        requested_price_tier = None

    if requested_price_tier:
        hotel_price_tier = row.get("price_tier")

        if not hotel_price_tier:
            return False

        if hotel_price_tier.lower().strip() != requested_price_tier.lower().strip():
            return False
        
    return True