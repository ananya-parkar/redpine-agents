# agent-1/src/storage/postgres_dedupe.py

from src.storage.postgres_storage import get_existing_leads
from src.storage.lead_key import build_lead_key


def remove_existing_postgres_leads(rows):

    existing = get_existing_leads()

    filtered = []

    for row in rows:

        place_id = row.get("place_id")
        lead_key = build_lead_key(row)
        existing_row = None

        if place_id and place_id in existing:
            existing_row = existing[place_id]

        elif lead_key in existing:
            existing_row = existing[lead_key]
        
        if not existing_row:
            filtered.append(row)
            continue

        status = (
            existing_row
            .get("status", "NEW")
            .upper()
        )

        # Never show active deals again
        if status == "PURSUING":
            continue

        # Never show rejected deals again
        if status == "PASSED":
            continue

        if status == "BAD_DATA":
            continue

        # Existing lead still gets processed
        filtered.append(row)

    return filtered