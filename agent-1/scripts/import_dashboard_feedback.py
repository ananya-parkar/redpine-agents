# agent-1/scripts/import_dashboard_feedback.py
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from src.storage.postgres_storage import update_feedback
from src.storage.lead_key import build_lead_key

dashboard = input(
    "Dashboard xlsx path: "
)

df = pd.read_excel(
    dashboard,
    sheet_name="All Leads"
)

updated = 0

for _, row in df.iterrows():

    status = str(
        row.get("lead_status", "")
    ).strip()

    if not status:
        continue

    lead_key = build_lead_key(
        {
            "hotel_name":
                row["hotel_name"],
            "address":
                row["address"]
        }
    )

    update_feedback(
        lead_key=lead_key,
        status=status.upper(),
        reason=row.get(
            "feedback_reason",
            ""
        ),
        notes=row.get(
            "feedback_notes",
            ""
        )
    )

    updated += 1

print(
    f"Updated {updated} rows"
)