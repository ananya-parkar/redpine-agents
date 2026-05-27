# agent-1/src/master_storage.py

import pandas as pd
from pathlib import Path

MASTER_PATH = Path("data/master_leads.csv")

def append_to_master(rows):
    if not rows:
        return

    df = pd.DataFrame(rows)

    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)

    if MASTER_PATH.exists():
        existing = pd.read_csv(MASTER_PATH)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df

    combined.to_csv(MASTER_PATH, index=False)