# agent-3/db/db.py
"""
Postgres persistence layer for Agent 3.

SCOPING (important):
Every candidate belongs to a search_request (see search_request_db.py).
The client can change what they're searching for, so "have I seen this
company before?" means "have I seen it FOR THIS SEARCH?" - not globally.
Every query below is scoped by search_request_id accordingly.

Tables:
    search_requests - one row per distinct set of client search params
    candidates      - one row per unique company PER SEARCH REQUEST
    evidence        - evidence + LLM rationale; new row only if changed
    review_status   - human review state, one current row per candidate
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


def _safe_int(value):
    if value in (None, "", "Unknown"):
        return None

    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

def upsert_candidate(conn, row, search_request_id):
    """
    row: dict with keys matching candidates_with_rationale.csv columns.
    search_request_id: which client search this candidate belongs to.

    Returns the candidate's id (existing or newly created).

    The existence check is scoped to search_request_id - the same company
    found under a DIFFERENT search gets its own separate row, with its
    own independent review_status. That's deliberate: the client might
    pursue a company under one mandate and pass on it under another.
    """
    normalized_name = normalize_company_name(row.get("Company Name", ""))
    state = row.get("State") or None

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM candidates
            WHERE normalized_name = %s
              AND (state = %s OR (%s IS NULL AND state IS NULL))
              AND search_request_id = %s
            """,
            (normalized_name, state, state, search_request_id),
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
                    search_request_id,
                    company_name, normalized_name, state, industry,
                    company_type, founded_year, revenue_estimate,
                    years_in_business, founder_name, founder_led,
                    family_owned, founder_age_estimate, ownership_status,
                    ownership_tenure_years, extraction_confidence,
                    seller_readiness_score
                ) VALUES (
                    %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s
                )
                RETURNING id
                """,
                (
                    search_request_id,
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
            return False

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
# Pipeline run snapshot - SCOPED, so "vs Last Week" compares this search
# against itself, not against whatever the client was searching for last
# week under different params.
# ---------------------------------------------------------------------------

def record_pipeline_run_snapshot(search_request_id, conn_factory=get_connection):
    conn = conn_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM candidates WHERE search_request_id = %s",
                (search_request_id,),
            )
            total_targets = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM candidates
                WHERE first_seen_date = CURRENT_DATE
                  AND search_request_id = %s
                """,
                (search_request_id,),
            )
            new_this_run = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM review_status rs
                JOIN candidates c ON c.id = rs.candidate_id
                WHERE rs.status = 'Pursuing' AND c.search_request_id = %s
                """,
                (search_request_id,),
            )
            shortlisted = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM review_status rs
                JOIN candidates c ON c.id = rs.candidate_id
                WHERE rs.status = 'New' AND c.search_request_id = %s
                """,
                (search_request_id,),
            )
            in_review = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM review_status rs
                JOIN candidates c ON c.id = rs.candidate_id
                WHERE rs.status IN ('Pursuing','Passed','Bad Data')
                  AND c.search_request_id = %s
                """,
                (search_request_id,),
            )
            reviewed = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (search_request_id, total_targets, new_this_run,
                     shortlisted, in_review, reviewed)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (search_request_id, total_targets, new_this_run,
                 shortlisted, in_review, reviewed),
            )
        conn.commit()
        print(f"Recorded pipeline run snapshot (search {search_request_id}): "
              f"{total_targets} total, {new_this_run} new, "
              f"{shortlisted} shortlisted, {in_review} in review, "
              f"{reviewed} reviewed")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def save_candidates_to_db(df, search_request_id):
    """
    df: the final enriched DataFrame (candidates_with_rationale.csv).
    search_request_id: which client search these candidates belong to.
    """
    conn = get_connection()
    new_evidence_count = 0

    try:
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            candidate_id = upsert_candidate(conn, row_dict, search_request_id)
            added = upsert_evidence(conn, candidate_id, row_dict)
            if added:
                new_evidence_count += 1
        conn.commit()
        print(f"Saved {len(df)} candidates to Postgres "
              f"(search {search_request_id}, "
              f"{new_evidence_count} new/updated evidence rows)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()