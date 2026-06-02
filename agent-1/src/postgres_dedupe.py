# agent-1/src/postgres_dedupe.py

from src.postgres_storage import get_existing_addresses
from src.property_records import normalize_address

def remove_existing_postgres_leads(rows):
    existing = {normalize_address(addr) for addr in get_existing_addresses()}
    filtered = []

    for row in rows:
        addr = normalize_address(row.get("address", ""))
        if addr not in existing:
            filtered.append(row)

    return filtered