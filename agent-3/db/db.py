# agent-3/db/db.py
"""
Postgres persistence layer for Agent 3.

Tables:
    candidates     - one row per unique company
    evidence       - evidence + LLM rationale; new row only if content changed
    review_status  - human review state, one current row per candidate

Upsert behavior:
    - candidates: always refresh structured fields + last_seen_date
    - evidence: only insert a new row if content actually changed since
                the last stored evidence row
    - review_status: created as 'New' on first insert only, never
                      overwritten automatically (human-owned field)
"""

import os
import re
import psycopg2
import psycopg2.extras
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


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

_NOISE_WORDS = [
    "inc", "incorporated", "llc", "l.l.c", "corp", "corporation",
    "co", "company", "ltd", "limited", "lp", "llp", "pllc",
    "holdings", "group", "enterprises", "super markets", "supermarkets",
]
_NOISE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _NOISE_WORDS) + r")\b\.?",
    flags=re.IGNORECASE,
)


def normalize_company_name(name):
    if not isinstance(name, str):
        return ""
    name = name.lower().strip()
    name = name.replace("&", "and")
    name = re.sub(r"[^\w\s]", "", name)
    name = _NOISE_PATTERN.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

def upsert_candidate(conn, row):
    """
    row: dict with keys matching candidates_with_rationale.csv columns.
    Returns the candidate's id (existing or newly created).
    """
    normalized_name = normalize_company_name(row.get("Company Name", ""))
    state = row.get("State") or None

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM candidates
            WHERE normalized_name = %s AND (state = %s OR (%s IS NULL AND state IS NULL))
            """,
            (normalized_name, state, state),
        )
        existing = cur.fetchone()

        if existing:
            candidate_id = existing[0]
            cur.execute(
                """
                UPDATE candidates
                SET company_name = %s,
                    industry = %s,
                    company_type = %s,
                    founded_year = %s,
                    revenue_estimate = %s,
                    years_in_business = %s,
                    founder_name = %s,
                    founder_led = %s,
                    family_owned = %s,
                    founder_age_estimate = %s,
                    ownership_status = %s,
                    ownership_tenure_years = %s,
                    extraction_confidence = %s,
                    seller_readiness_score = %s,
                    last_seen_date = CURRENT_DATE,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    row.get("Company Name"),
                    row.get("Industry"),
                    row.get("Company Type"),
                    row.get("Founded Year"),
                    row.get("Revenue Estimate"),
                    _safe_int(row.get("Years in Business")),
                    row.get("Founder Name"),
                    row.get("Founder Led"),
                    row.get("Family Owned"),
                    row.get("Founder Age Estimate"),
                    row.get("Ownership Status"),
                    _safe_int(row.get("Ownership Tenure Years")),
                    row.get("Extraction Confidence"),
                    _safe_int(row.get("Seller Readiness Score")),
                    candidate_id,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO candidates (
                    company_name, normalized_name, state, industry,
                    company_type, founded_year, revenue_estimate,
                    years_in_business, founder_name, founder_led,
                    family_owned, founder_age_estimate, ownership_status,
                    ownership_tenure_years, extraction_confidence,
                    seller_readiness_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    row.get("Company Name"),
                    normalized_name,
                    state,
                    row.get("Industry"),
                    row.get("Company Type"),
                    row.get("Founded Year"),
                    row.get("Revenue Estimate"),
                    _safe_int(row.get("Years in Business")),
                    row.get("Founder Name"),
                    row.get("Founder Led"),
                    row.get("Family Owned"),
                    row.get("Founder Age Estimate"),
                    row.get("Ownership Status"),
                    _safe_int(row.get("Ownership Tenure Years")),
                    row.get("Extraction Confidence"),
                    _safe_int(row.get("Seller Readiness Score")),
                ),
            )
            candidate_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO review_status (candidate_id, status)
                VALUES (%s, 'New')
                ON CONFLICT (candidate_id) DO NOTHING
                """,
                (candidate_id,),
            )

    return candidate_id


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Evidence (only insert if content changed since last stored row)
# ---------------------------------------------------------------------------

def upsert_evidence(conn, candidate_id, row):
    raw_evidence = row.get("Evidence", "") or ""
    raw_evidence_summary = row.get("Raw Evidence Summary", "") or ""
    why_selected = row.get("Why Selected", "") or ""
    evidence_summary = row.get("Evidence Summary", "") or ""
    one_line_reason = row.get("One-line Reason", "") or ""
    evidence_sources = row.get("Evidence Sources", "") or ""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT raw_evidence, why_selected, evidence_summary, one_line_reason,
                   evidence_sources, raw_evidence_summary
            FROM evidence
            WHERE candidate_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (candidate_id,),
        )
        last = cur.fetchone()

        unchanged = last is not None and last == (
            raw_evidence, why_selected, evidence_summary, one_line_reason,
            evidence_sources, raw_evidence_summary
        )

        if unchanged:
            return False  # nothing new to store

        cur.execute(
            """
            INSERT INTO evidence (
                candidate_id, raw_evidence, why_selected,
                evidence_summary, one_line_reason,
                evidence_sources, raw_evidence_summary
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                candidate_id, raw_evidence, why_selected,
                evidence_summary, one_line_reason,
                evidence_sources, raw_evidence_summary,
            ),
        )
        return True


# ---------------------------------------------------------------------------
# Pipeline run snapshot
# ---------------------------------------------------------------------------

def record_pipeline_run_snapshot(conn_factory=get_connection):
    conn = conn_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM candidates")
            total_targets = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM candidates WHERE first_seen_date = CURRENT_DATE"
            )
            new_this_run = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM review_status WHERE status = 'Pursuing'"
            )
            shortlisted = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM review_status WHERE status = 'New'"
            )
            in_review = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM review_status WHERE status IN ('Pursuing','Passed','Bad Data')"
            )
            reviewed = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (total_targets, new_this_run, shortlisted, in_review, reviewed)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (total_targets, new_this_run, shortlisted, in_review, reviewed),
            )
        conn.commit()
        print(f"Recorded pipeline run snapshot: {total_targets} total, "
              f"{new_this_run} new, {shortlisted} shortlisted, "
              f"{in_review} in review, {reviewed} reviewed")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_candidates_to_db(df):
    """
    df: the final enriched DataFrame (candidates_with_rationale.csv content).
    """
    conn = get_connection()
    new_evidence_count = 0

    try:
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            candidate_id = upsert_candidate(conn, row_dict)
            added = upsert_evidence(conn, candidate_id, row_dict)
            if added:
                new_evidence_count += 1
        conn.commit()
        print(f"Saved {len(df)} candidates to Postgres "
              f"({new_evidence_count} new/updated evidence rows)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()