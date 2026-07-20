"""
Wipes Agent 3's Postgres data for clean testing. Two modes:

  Full wipe (everything - all searches, all candidates, all history):
      python -m db.wipe_db --all

  Scoped wipe (just one search_request_id, leaves other searches intact):
      python -m db.wipe_db --search-request-id 3

Both modes require typing "yes" to confirm (prints which DB/host you're
about to wipe first) unless you pass --yes to skip the prompt (useful
for CI/scripted test resets - do NOT alias this to skip by default).

--all wipes: candidates, evidence, review_status, pipeline_runs,
search_requests, tuning_triggers - full reset, search_request_ids will
restart from 1 on next run.

--search-request-id N wipes only that search's candidates/evidence/
review_status/pipeline_runs/the search_requests row itself. Does NOT
touch tuning_triggers, since those are cross-search by design - use
`python -m db.manage_tuning_triggers resolve <id>` to clear those
individually if you want a clean learning-loop test too.

SAFETY: this is destructive and irreversible. Never point this at a
database you can't afford to lose. Double-check DB_CONFIG / your .env
before running.
"""

import argparse
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB_AGENT3", "redpine_agent3"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def _confirm(message, skip_prompt):
    print(f"\nTarget database: {DB_CONFIG['dbname']} @ {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(message)
    if skip_prompt:
        return True
    answer = input("\nType 'yes' to proceed: ").strip().lower()
    return answer == "yes"


def wipe_all(skip_prompt=False):
    ok = _confirm(
        "This will PERMANENTLY DELETE ALL DATA in: candidates, evidence, "
        "review_status, pipeline_runs, search_requests, tuning_triggers.\n"
        "Every search's history, feedback, and learning-loop state will be gone.",
        skip_prompt,
    )
    if not ok:
        print("Aborted - no changes made.")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE TABLE
                    evidence,
                    review_status,
                    pipeline_runs,
                    candidates,
                    search_requests,
                    tuning_triggers
                RESTART IDENTITY CASCADE
                """
            )
        conn.commit()
        print("\nAll tables wiped. IDs will restart from 1 on next run.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def wipe_search(search_request_id, skip_prompt=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM candidates WHERE search_request_id = %s",
                (search_request_id,),
            )
            candidate_count = cur.fetchone()[0]

        ok = _confirm(
            f"This will PERMANENTLY DELETE search_request_id={search_request_id} "
            f"and its {candidate_count} candidate(s), their evidence, review "
            f"status, and pipeline_runs history. tuning_triggers is NOT "
            f"touched (it's cross-search by design).",
            skip_prompt,
        )
        if not ok:
            print("Aborted - no changes made.")
            return

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM evidence
                WHERE candidate_id IN (
                    SELECT id FROM candidates WHERE search_request_id = %s
                )
                """,
                (search_request_id,),
            )
            cur.execute(
                """
                DELETE FROM review_status
                WHERE candidate_id IN (
                    SELECT id FROM candidates WHERE search_request_id = %s
                )
                """,
                (search_request_id,),
            )
            cur.execute(
                "DELETE FROM pipeline_runs WHERE search_request_id = %s",
                (search_request_id,),
            )
            cur.execute(
                "DELETE FROM candidates WHERE search_request_id = %s",
                (search_request_id,),
            )
            cur.execute(
                "DELETE FROM search_requests WHERE id = %s",
                (search_request_id,),
            )
        conn.commit()
        print(f"\nWiped search_request_id={search_request_id} "
              f"({candidate_count} candidate(s) removed).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Wipe everything.")
    group.add_argument("--search-request-id", type=int, help="Wipe only this search.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    if args.all:
        wipe_all(skip_prompt=args.yes)
    else:
        wipe_search(args.search_request_id, skip_prompt=args.yes)