# agent-3/db/pii_retention.py
"""
PII Retention Job

Confirmed policy (per legal/compliance sign-off):
    - review_status = 'Pursuing'  -> KEEP forever (active deal, PII still needed)
    - any other status (New, Passed, Bad Data) -> after 12 months from
      first_seen_date, NULL out the PII fields: founder_name, founder_age_estimate

This does NOT delete the candidate row itself - company-level fields
(name, industry, score, etc.) are retained for historical/analytics
purposes. Only the two personally-identifiable fields are nulled.

KNOWN GAP (explicitly out of scope per product decision): free-text
fields in the evidence table (raw_evidence, why_selected,
evidence_summary) may still contain the founder's name in prose, since
this job only nulls the structured candidates table fields. Revisit
if/when full PII scrubbing of free text is required.

Run this on a schedule (e.g. monthly) - it's idempotent, safe to run
repeatedly. Already-nulled rows simply won't match the WHERE clause
again.
"""

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

RETENTION_MONTHS = 12


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def find_candidates_due_for_pii_removal(conn):
    """
    Returns the list of (candidate_id, company_name) for candidates
    that are about to have their PII nulled - useful for logging /
    audit trail before the destructive UPDATE runs.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.company_name, c.first_seen_date, rs.status
            FROM candidates c
            LEFT JOIN review_status rs ON rs.candidate_id = c.id
            WHERE c.first_seen_date < CURRENT_DATE - INTERVAL '%s months'
              AND (rs.status IS NULL OR rs.status != 'Pursuing')
              AND (c.founder_name IS NOT NULL OR c.founder_age_estimate IS NOT NULL)
            """,
            (RETENTION_MONTHS,),
        )
        return cur.fetchall()


def apply_pii_retention(dry_run=False):
    """
    Nulls founder_name and founder_age_estimate for every candidate
    that:
      1. Is older than RETENTION_MONTHS (by first_seen_date), AND
      2. Is NOT currently marked 'Pursuing'

    dry_run=True logs what WOULD be affected without making changes -
    use this first to verify scope before running for real.
    """
    conn = get_connection()
    try:
        due = find_candidates_due_for_pii_removal(conn)

        if not due:
            print("No candidates are due for PII removal.")
            return 0

        print(f"{'[DRY RUN] ' if dry_run else ''}"
              f"{len(due)} candidate(s) due for PII removal:")
        for candidate_id, company_name, first_seen, status in due:
            print(f"  id={candidate_id} | {company_name} | "
                  f"first_seen={first_seen} | status={status or 'New'}")

        if dry_run:
            print("\nDry run only - no changes made. "
                  "Call apply_pii_retention(dry_run=False) to apply.")
            return len(due)

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE candidates c
                SET founder_name = NULL,
                    founder_age_estimate = NULL,
                    updated_at = NOW()
                WHERE c.first_seen_date < CURRENT_DATE - INTERVAL '%s months'
                  AND (
                      NOT EXISTS (
                          SELECT 1 FROM review_status rs
                          WHERE rs.candidate_id = c.id AND rs.status = 'Pursuing'
                      )
                  )
                  AND (c.founder_name IS NOT NULL OR c.founder_age_estimate IS NOT NULL)
                """,
                (RETENTION_MONTHS,),
            )
            affected = cur.rowcount

        conn.commit()
        print(f"\nPII removed from {affected} candidate(s).")
        return affected

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Default to dry run when executed directly, so nobody accidentally
    # nulls real data by running this file without thinking.
    apply_pii_retention(dry_run=True)