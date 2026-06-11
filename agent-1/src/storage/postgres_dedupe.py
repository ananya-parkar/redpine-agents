# agent-1/src/storage/postgres_dedupe.py

from src.storage.postgres_storage import get_existing_leads
from src.storage.lead_key import build_lead_key


def remove_existing_postgres_leads(rows):

    existing = get_existing_leads()

    filtered = []

    for row in rows:

        lead_key = build_lead_key(row)

        if lead_key not in existing:
            filtered.append(row)
            continue

        status = (
            existing[lead_key]
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