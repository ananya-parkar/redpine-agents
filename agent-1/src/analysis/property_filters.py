# agent-1/src/analysis/property_filters.py

def passes_filters(row, search_config):
    # Year Built
    year_filter = search_config.get("year_built_range")
    if year_filter:
        if not row.get("attom_year_built"):
            return False
        start_year, end_year = [int(x.strip()) for x in year_filter.split("-")]
        year_built = int(row["attom_year_built"])
        if year_built < start_year:
            return False
        if year_built > end_year:
            return False
    
    # Minimum Room Count
    min_rooms = search_config.get("min_rooms")
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
    
    # Price Tier
    requested_price_tier = search_config.get("price_tier")
    if requested_price_tier:
        if (
            row.get("price_tier")
            and row["price_tier"] != requested_price_tier
        ):
            return False
        
    return True