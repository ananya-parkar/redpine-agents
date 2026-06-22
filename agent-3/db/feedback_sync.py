# agent-3/db/feedback_sync.py
"""
Feedback Sync — reads the dashboard Excel file BEFORE it gets
regenerated this run, pulls out whatever Feedback/Notes a human has
entered on the Top_Companies sheet, and writes those into Postgres.

Must run BEFORE generate_dashboard() in main.py, or the file gets
overwritten with a fresh blank-feedback version first and there's
nothing left to read.

Safety rule: only updates a candidate's status in Postgres if:
    1. The Excel row has a non-blank Feedback value, AND
    2. Postgres still shows that candidate as "New"

This means a human's decision, once recorded, can never be silently
reverted by a stale or re-opened Excel file - the only way to change
a status after the first sync is a deliberate new dropdown selection,
and even that requires the corresponding code path to treat it as an
explicit change (not built here yet - this version only captures the
FIRST decision per candidate).
"""

import os
from openpyxl import load_workbook
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "redpine_agent3"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

VALID_STATUSES = {"New", "Pursuing", "Passed", "Bad Data"}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def read_feedback_from_excel(dashboard_file_path):
    """
    Returns a list of dicts: [{"candidate_id": int, "feedback": str, "notes": str}, ...]
    Reads only rows with a non-blank Feedback value.
    """
    if not os.path.exists(dashboard_file_path):
        print(f"No existing dashboard file at {dashboard_file_path} - nothing to sync.")
        return []

    wb = load_workbook(dashboard_file_path, data_only=True)
    if "Top_Companies" not in wb.sheetnames:
        print("Top_Companies sheet not found - nothing to sync.")
        return []

    ws = wb["Top_Companies"]

    # Find the relevant columns by header name, rather than hardcoding
    # column letters - keeps this resilient to column reordering.
    header_row = [cell.value for cell in ws[1]]
    try:
        feedback_col = header_row.index("Feedback") + 1
        notes_col = header_row.index("Notes") + 1
        id_col = header_row.index("_candidate_id") + 1
    except ValueError:
        print("Expected columns (Feedback, Notes, _candidate_id) not found "
              "in Top_Companies - nothing to sync. (Is this an older "
              "dashboard file from before feedback columns were added?)")
        return []

    results = []
    for row in ws.iter_rows(min_row=2):
        candidate_id = row[id_col - 1].value
        feedback = row[feedback_col - 1].value
        notes = row[notes_col - 1].value

        if candidate_id is None:
            continue
        if not feedback or str(feedback).strip() == "":
            continue
        feedback = str(feedback).strip()
        if feedback not in VALID_STATUSES:
            print(f"Skipping candidate_id {candidate_id}: "
                  f"unrecognized feedback value '{feedback}'")
            continue

        results.append({
            "candidate_id": int(candidate_id),
            "feedback": feedback,
            "notes": str(notes).strip() if notes else None,
        })

    return results


def apply_feedback_to_postgres(feedback_rows):
    """
    Applies each feedback row to Postgres, but ONLY if the candidate's
    current status in Postgres is still 'New'. This is the safety rule
    that prevents a stale/reopened Excel file from reverting a real
    decision someone already made.
    """
    if not feedback_rows:
        print("No feedback rows to apply.")
        return 0

    conn = get_connection()
    applied_count = 0

    try:
        with conn.cursor() as cur:
            for item in feedback_rows:
                cur.execute(
                    "SELECT status FROM review_status WHERE candidate_id = %s",
                    (item["candidate_id"],),
                )
                row = cur.fetchone()
                current_status = row[0] if row else None

                if current_status != "New":
                    # Already reviewed via some other path - don't touch it.
                    continue

                cur.execute(
                    """
                    UPDATE review_status
                    SET status = %s,
                        comments = %s,
                        updated_at = NOW()
                    WHERE candidate_id = %s
                    """,
                    (item["feedback"], item["notes"], item["candidate_id"]),
                )
                applied_count += 1

        conn.commit()
        print(f"Applied feedback to {applied_count} of {len(feedback_rows)} "
              f"candidates (others were already reviewed, so skipped).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return applied_count


def sync_feedback_from_dashboard(dashboard_file_path):
    """
    Public entry point. Call this in main.py BEFORE generate_dashboard(),
    so the previous run's saved file (with any human feedback) is read
    before it gets overwritten by a fresh regeneration.
    """
    print("\nSyncing feedback from previous dashboard file...\n")
    feedback_rows = read_feedback_from_excel(dashboard_file_path)
    applied = apply_feedback_to_postgres(feedback_rows)
    return applied