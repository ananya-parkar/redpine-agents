# agent-1/src/enrichment/property_age.py
from datetime import datetime
from typing import Dict

def get_property_age_flags(property_data: Dict) -> Dict:

    try:
        fields = (property_data.get("properties", {}).get("fields", {}))
        year_built = (fields.get("yearbuilt") or fields.get("year_built") or "")

        is_older_than_20_years = ""
        if year_built:
            property_age = (datetime.now().year - int(year_built))
            is_older_than_20_years = ("Yes" if property_age >= 20 else "No")

        return {
            "year_built": year_built,
            "is_older_than_20_years": is_older_than_20_years
        }

    except Exception:
        return {
            "year_built": "",
            "is_older_than_20_years": ""
        }