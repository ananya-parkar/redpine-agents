# agent-3/db/search_request_db.py
"""
Search Request Registry.

The client can change what they're searching for (geography, industry,
revenue band, etc). Every candidate is tagged with WHICH search request
found it, so that:

    - dedupe asks "have I seen this company FOR THIS SEARCH?"
      (not "have I ever seen this company anywhere?")
    - the dashboard shows only leads matching the CURRENT search
    - the email digest does the same

Without this, switching Florida -> Texas would show the client all the
old Florida leads mixed into their Texas run.

Identity: a search request is uniquely identified by a canonical
`request_key` built from all its params. Two runs with identical params
reuse the same row (so feedback + dedupe history carry over correctly).
Change ANY param -> new request_key -> new scope, fresh start.

We use a single TEXT request_key rather than a multi-column UNIQUE
constraint on purpose: Postgres treats NULLs as distinct in UNIQUE
constraints, so a multi-column UNIQUE would happily insert duplicate
rows whenever an optional field (industry, founder_age...) was blank.
Canonicalising to a string sidesteps that entirely.
"""

import os
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

# The params that define a distinct search. Order matters (it's part of
# the key), so don't reorder this without accepting that every existing
# search_request row becomes unreachable.
REQUEST_FIELDS = [
    "geography",
    "industry",
    "revenue_range",
    "min_years",
    "ownership_preference",
    "founder_age",
]


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def _canon(value):
    """
    Canonicalise one param so that 'Florida', ' florida ', and 'FLORIDA'
    all produce the same key, and blank/NaN/None all collapse to "".
    """
    if value is None:
        return ""
    text = str(value).strip()
    # pandas gives NaN for empty Excel cells; str(NaN) == 'nan'
    if text.lower() in ("", "nan", "none"):
        return ""
    return text.lower()


def build_request_key(search_request):
    """
    search_request: the dict returned by load_search_request().
    Returns a deterministic string uniquely identifying this search.
    """
    return "|".join(_canon(search_request.get(f)) for f in REQUEST_FIELDS)


def get_or_create_search_request(search_request):
    """
    Looks up this exact search; creates it if it's new.
    Returns the search_request_id (int).

    Same params as a previous run -> same id -> dedupe history and
    client feedback carry over.
    Any param changed -> new id -> clean scope, nothing from the old
    search leaks into the new one.
    """
    request_key = build_request_key(search_request)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM search_requests WHERE request_key = %s",
                (request_key,),
            )
            existing = cur.fetchone()

            if existing:
                search_request_id = existing[0]
                print(f"Reusing existing search request id={search_request_id}")
            else:
                cur.execute(
                    """
                    INSERT INTO search_requests (
                        request_key, geography, industry, revenue_range,
                        min_years, ownership_preference, founder_age
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        request_key,
                        search_request.get("geography"),
                        search_request.get("industry"),
                        search_request.get("revenue_range"),
                        _safe_int(search_request.get("min_years")),
                        search_request.get("ownership_preference"),
                        search_request.get("founder_age"),
                    ),
                )
                search_request_id = cur.fetchone()[0]
                print(f"Created NEW search request id={search_request_id} "
                      f"(params changed -> fresh scope)")

        conn.commit()
        return search_request_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None