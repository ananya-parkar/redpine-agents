# agent-1/src/storage/lead_key.py
from src.collectors.property_records import normalize_address

def build_lead_key(row):

    hotel = normalize_address(
        row.get("hotel_name", "")
    )

    address = normalize_address(
        row.get("address", "")
    )

    return f"{hotel}|{address}"