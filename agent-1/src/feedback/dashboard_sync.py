# agent-1/src/feedback/dashboard_sync.py
from pathlib import Path
import pandas as pd
from src.storage.postgres_storage import update_feedback
from src.storage.lead_key import build_lead_key
from src.core.config import RUNS_DIR

def sync_dashboard_feedback():

    dashboard_dir = RUNS_DIR
    dashboards = list(
        dashboard_dir.glob(
            "**/Hotel_Acquisition_Dashboard*.xlsx"
        )
    )

    print(f"[DEBUG] RUNS_DIR={dashboard_dir}")

    print(
        f"[DEBUG] dashboards found={len(dashboards)}"
    )

    for d in dashboards:
        print(d)

    if not dashboards:
        return

    latest = max(
        dashboards,
        key=lambda x: x.stat().st_mtime
    )

    print(
        f"[FEEDBACK] Using dashboard: {latest}"
    )

    df = pd.read_excel(
        latest,
        sheet_name="All Leads"
    )
    print(df.head())
    print(
        df[
            [
                "Hotel Name",
                "Lead Status ▼",
                "Feedback Reason"
            ]
        ].head()
    )

    
    print(df.columns.tolist())
    for _, row in df.iterrows():

        status = str(
            row.get("Lead Status ▼", "")
        ).strip()

        if not status:
            continue

        reason = row.get("Feedback Reason", "")
        notes = row.get("Feedback Notes", "")

        if pd.isna(reason):
            reason = ""

        if pd.isna(notes):
            notes = ""

        reason = str(reason).strip()
        notes = str(notes).strip()

        hotel_name = str(
            row.get("Hotel Name", "")
        ).strip()

        print(
            f"[SYNC] "
            f"{hotel_name} | "
            f"{status} | "
            f"{reason}"
        )

        update_feedback(
            hotel_name,
            status.upper(),
            reason,
            notes
        )

    print(
        "[FEEDBACK] Dashboard sync complete"
    )