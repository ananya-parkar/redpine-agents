"""
Regenerates the dashboard Excel from data ALREADY in Postgres, without
running discovery/profiling/dedup/reasoning/feedback-sync. Use this
whenever you're only changing dashboard.py (formatting, columns,
charts) and want to see the result in seconds instead of waiting
through a full pipeline run.

Usage:
    python -m db.test_dashboard --list
        Shows every search_request_id currently in the DB and how many
        candidates each has, so you know which id to test against.

    python -m db.test_dashboard <search_request_id>
        Regenerates the dashboard for that search using whatever's
        currently in Postgres, saves it to db/test_output/, and prints
        the path.

Requires at least one search to already have candidates in the DB
(i.e. you've run main.py at least once, or seeded data some other
way). This does NOT create fake data - if the DB is empty (e.g. right
after wipe_db.py --all), run main.py once for real first, then use
this script for every dashboard-only iteration after that.
"""

import sys
import time
from pathlib import Path

from db.feedback_sync import get_connection
from dashboard.dashboard import generate_dashboard

OUTPUT_DIR = Path(__file__).parent / "test_output"


def list_searches():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT search_request_id, COUNT(*) AS candidate_count
                FROM candidates
                GROUP BY search_request_id
                ORDER BY search_request_id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No candidates in the DB at all. Run main.py at least once first "
              "(this script only re-renders existing data, it doesn't create any).")
        return

    print("\nsearch_request_id | candidate_count")
    print("-------------------|----------------")
    for search_request_id, count in rows:
        print(f"{search_request_id:<19}| {count}")


def run(search_request_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM candidates WHERE search_request_id = %s",
                (search_request_id,),
            )
            count = cur.fetchone()[0]
    finally:
        conn.close()

    if count == 0:
        print(f"No candidates found for search_request_id={search_request_id}. "
              f"Run 'python -m db.test_dashboard --list' to see what's available.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"test_dashboard_{search_request_id}_{int(time.time())}.xlsx"

    print(f"Regenerating dashboard for search_request_id={search_request_id} "
          f"({count} candidates)...")
    start = time.time()
    generate_dashboard(output_file, search_request_id)
    elapsed = time.time() - start

    print(f"\nDone in {elapsed:.2f}s -> {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--list":
        list_searches()
    else:
        try:
            search_request_id = int(sys.argv[1])
        except ValueError:
            print("Usage: python -m db.test_dashboard <search_request_id>")
            print("   or: python -m db.test_dashboard --list")
            sys.exit(1)
        run(search_request_id)