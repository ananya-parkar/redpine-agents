# agent-1/src/dedupe.py
import pandas as pd
from pathlib import Path
from pandas.errors import EmptyDataError

from src.property_records import normalize_address

MASTER_PATH = Path("data/master_leads.csv")


def remove_existing_leads(rows):
    if not MASTER_PATH.exists():
        return rows

    try:
        master = pd.read_csv(MASTER_PATH)
    except EmptyDataError:
        return rows

    if "address" not in master.columns:
        return rows

    existing = set(
        master["address"]
        .fillna("")
        .apply(normalize_address)
    )

    filtered = []

    for row in rows:
        addr = normalize_address(
            row.get("address", "")
        )

        if addr not in existing:
            filtered.append(row)

    return filtered