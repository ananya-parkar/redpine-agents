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

    return True