# agent-3/deduplication/dedupe.py
"""
Layer 5 — Deduplication Layer

Per spec:
- Check against previously reviewed set (now: Postgres `candidates` table,
  not a CSV — see NOTE below)
- Match by name, state (other fields wired in as soon as they exist upstream)
- Remove duplicates & near-duplicates
- Keep highest quality record

CHANGE FROM EARLIER VERSION:
master_reviewed_companies.csv is retired. Cross-run "have I seen this
company before" now queries Postgres directly via db.get_connection(),
using the SAME normalized_name + state matching that db.py's
upsert_candidate() already uses — so dedup and the DB upsert logic can
never disagree about what counts as the same company.

Output: deduplicated_candidates.csv (clean, unique list ready for
        reasoning / ranking)
"""

import os
import re
import json
import pandas as pd
from rapidfuzz import fuzz
from anthropic import Anthropic
from dotenv import load_dotenv

from db.db import get_connection, normalize_company_name

load_dotenv(override=True)
client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MATCH_FIELDS = ["Company Name", "State"]

HIGH_CONFIDENCE_THRESHOLD = 92
LOW_CONFIDENCE_THRESHOLD = 80


def normalize_state(state):
    if not isinstance(state, str):
        return ""
    return state.lower().strip()


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def fuzzy_match_score(row_a, row_b):
    name_a = normalize_company_name(row_a.get("Company Name", ""))
    name_b = normalize_company_name(row_b.get("Company Name", ""))

    if not name_a or not name_b:
        return 0

    state_a = normalize_state(row_a.get("State", ""))
    state_b = normalize_state(row_b.get("State", ""))

    if state_a and state_b and state_a != state_b:
        return 0

    return fuzz.token_sort_ratio(name_a, name_b)


def llm_tiebreak(row_a, row_b):
    prompt = f"""
        Do these two records refer to the SAME real-world business?

        Record A:
        Company Name: {row_a.get("Company Name", "")}
        State: {row_a.get("State", "")}
        Industry: {row_a.get("Industry", "")}

        Record B:
        Company Name: {row_b.get("Company Name", "")}
        State: {row_b.get("State", "")}
        Industry: {row_b.get("Industry", "")}

        Return JSON only:
        {{
            "same_company": true,
            "reason": "short explanation"
        }}
    """

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1000,
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ]
    )

    content = "".join(
        block.text
        for block in response.content
        if hasattr(block,"text")
    )

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return False
    return bool(result.get("same_company", False))


def is_duplicate(row_a, row_b):
    score = fuzzy_match_score(row_a, row_b)

    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return True
    if score < LOW_CONFIDENCE_THRESHOLD:
        return False

    return llm_tiebreak(row_a, row_b)


# ---------------------------------------------------------------------------
# Record quality
# ---------------------------------------------------------------------------

def record_quality_score(row):
    score = 0
    for col, val in row.items():
        if col == "Company Name":
            continue
        if pd.isna(val):
            continue
        val_str = str(val).strip()
        if val_str and val_str.lower() not in ("unknown", "nan", ""):
            score += 1
    return score


def pick_best_record(rows):
    return max(rows, key=record_quality_score)


# ---------------------------------------------------------------------------
# Within-batch dedup (unchanged - no DB access needed)
# ---------------------------------------------------------------------------

def deduplicate_batch(df):
    records = df.to_dict("records")
    n = len(records)
    assigned = [False] * n
    clusters = []

    for i in range(n):
        if assigned[i]:
            continue
        cluster = [records[i]]
        assigned[i] = True
        for j in range(i + 1, n):
            if assigned[j]:
                continue
            if is_duplicate(records[i], records[j]):
                cluster.append(records[j])
                assigned[j] = True
        clusters.append(cluster)

    deduped_rows = [pick_best_record(cluster) for cluster in clusters]
    print(f"\nWithin-batch dedup: {n} rows -> {len(deduped_rows)} unique rows")
    return pd.DataFrame(deduped_rows)


# ---------------------------------------------------------------------------
# Against-Postgres dedup (replaces the old CSV-based check)
# ---------------------------------------------------------------------------

def fetch_existing_candidates_for_matching(search_request_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT company_name, state, industry FROM candidates "
                "WHERE search_request_id = %s",
                (search_request_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [{"Company Name": r[0], "State": r[1], "Industry": r[2]} for r in rows]


def deduplicate_against_postgres(df, search_request_id):
    """
    Splits today's deduplicated batch into:
      - new_rows: not already in Postgres -> goes to reasoning + Postgres
      - everything else: already seen, dropped from today's output

    Unlike the old CSV version, this does NOT write anything itself -
    db.save_candidates_to_db() already handles refreshing last_seen_date
    for existing rows. This function's only job is filtering.
    """
    existing_candidates = fetch_existing_candidates_for_matching(search_request_id)
    new_rows = []

    for _, candidate in df.iterrows():
        candidate_dict = candidate.to_dict()
        match_found = False

        for existing in existing_candidates:
            if is_duplicate(candidate_dict, existing):
                match_found = True
                break

        if not match_found:
            new_rows.append(candidate_dict)

    new_df = pd.DataFrame(new_rows)

    if new_df.empty:
        # Preserve the input's columns so the CSV has a header row even
        # with zero data rows - otherwise pd.read_csv() downstream
        # (in run_reasoning) crashes on a truly empty file.
        new_df = pd.DataFrame(columns=df.columns)

    print(f"Against-Postgres dedup: {len(df)} candidates -> "
          f"{len(new_df)} new, {len(df) - len(new_df)} already in database")

    return new_df


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_deduplication(scored_df, output_file, search_request_id):
    """
    Full Layer 5 pipeline:
      1. Dedup within today's batch
      2. Dedup against Postgres (previously seen candidates)
      3. Save clean unique list -> output_file

    Returns the deduplicated DataFrame (today's new, unique candidates).
    """
    print("\nRunning Deduplication Layer...\n")

    batch_deduped = deduplicate_batch(scored_df)
    new_df = deduplicate_against_postgres(batch_deduped, search_request_id)
    new_df.to_csv(output_file, index=False)
    print(f"Saved {len(new_df)} deduplicated rows -> {output_file}")
    return new_df
