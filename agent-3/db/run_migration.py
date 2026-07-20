"""
One-off migration script - adds the new discovery-focused columns to
`candidates`. Safe to run more than once (IF NOT EXISTS guards).

Usage:
    cd agent-3
    python -m db.run_migration
    (or: python db/run_migration.py, run from the agent-3 root so the
    db package and .env are found the same way main.py finds them)
"""

from db.db import get_connection

MIGRATION_SQL = """
ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS website TEXT,
    ADD COLUMN IF NOT EXISTS city TEXT,
    ADD COLUMN IF NOT EXISTS company_description TEXT,
    ADD COLUMN IF NOT EXISTS fit_analysis TEXT,
    ADD COLUMN IF NOT EXISTS seller_readiness_signals TEXT,
    ADD COLUMN IF NOT EXISTS why_discovered TEXT;

CREATE TABLE IF NOT EXISTS tuning_triggers (
    id                   SERIAL PRIMARY KEY,
    root_cause           TEXT NOT NULL,
    occurrences          INTEGER NOT NULL,
    affected_candidates  TEXT,
    recommendation       TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE tuning_triggers
    ADD COLUMN IF NOT EXISTS feedback_type TEXT DEFAULT 'Bad Data',
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
"""


def run_migration():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
        conn.commit()
        print("Migration applied successfully.")

        # Verify - list columns now present on candidates
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'candidates'
                ORDER BY ordinal_position
                """
            )
            columns = [r[0] for r in cur.fetchall()]
        print("\ncandidates columns now:")
        for c in columns:
            print(f"  - {c}")

        expected_new = {
            "website", "city", "company_description",
            "fit_analysis", "seller_readiness_signals", "why_discovered",
        }
        missing = expected_new - set(columns)
        if missing:
            print(f"\n[WARNING] Still missing: {missing}")
        else:
            print("\nAll 6 new columns confirmed present.")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT to_regclass('public.tuning_triggers') IS NOT NULL AS exists
                """
            )
            table_exists = cur.fetchone()[0]
        if table_exists:
            print("tuning_triggers table confirmed present.")
        else:
            print("[WARNING] tuning_triggers table not found after migration.")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'tuning_triggers'
                ORDER BY ordinal_position
                """
            )
            tt_columns = {r[0] for r in cur.fetchall()}
        expected_tt = {"feedback_type", "status", "updated_at"}
        missing_tt = expected_tt - tt_columns
        if missing_tt:
            print(f"[WARNING] tuning_triggers missing: {missing_tt}")
        else:
            print("tuning_triggers learning-loop columns confirmed present.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()