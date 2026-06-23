import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------
# DB WRITER — PostgreSQL (Docker)
#
# Credentials from .env:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#
# Field mapping (reasoning_agent → DB):
#   engagement      → current_engagement / engagement_action
#   score           → current_score / final_score
#   likelihood      → current_likelihood / project_likelihood
#   project_type    → current_scale
#   whats_happening → current_summary
#   why_priority    → current_reason
#   source          → current_url (the link)
#   source_name     → current_source (name of publication)
#   stakeholders_raw→ parsed into stakeholder_names / stakeholder_types
#
# Keeps all original features:
#   - Tier change logging (tier_changes table)
#   - PII purge (purge_old_pii)
#   - Feedback tracking (Archive / Pursuing / Bad Data / Passed)
#   - Bad data pattern detection
#   - Tuning triggers
# ---------------------------------------------------

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME",     "stadium_leads"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id                  SERIAL PRIMARY KEY,
    venue_name          VARCHAR(200),
    league              VARCHAR(50),
    city                VARCHAR(100),
    state               VARCHAR(5),
    capacity            INTEGER,
    signal_tier         INTEGER,
    tier_label          VARCHAR(100),
    signal_type         VARCHAR(20) DEFAULT 'news',
    headline            TEXT,
    description         TEXT,
    source              VARCHAR(200),
    url                 TEXT,
    published_at        TIMESTAMPTZ,
    matched_keywords    TEXT DEFAULT '',
    opportunity_score   NUMERIC,
    tier_score          NUMERIC,
    venue_size_score    NUMERIC,
    recency_score       NUMERIC,
    status_bonus        NUMERIC,
    scraped_at          TIMESTAMPTZ,
    run_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (venue_name, url)
);

CREATE TABLE IF NOT EXISTS leads (
    id                      SERIAL PRIMARY KEY,
    venue_name              VARCHAR(200) UNIQUE NOT NULL,
    league                  VARCHAR(50),
    city                    VARCHAR(100),
    state                   VARCHAR(5),
    capacity                INTEGER,
    venue_status            VARCHAR(50)  DEFAULT 'existing',
    year_built              VARCHAR(10),
    planned_year            VARCHAR(10),
    owner_name              VARCHAR(200),
    current_tier            INTEGER,
    current_tier_label      VARCHAR(100),
    current_engagement      VARCHAR(50),
    current_score           NUMERIC,
    current_likelihood      INTEGER,
    current_scale           VARCHAR(100),
    current_summary         TEXT,
    current_reason          TEXT,
    current_headline        TEXT,
    current_source          VARCHAR(200),
    current_url             TEXT,
    current_signal_type     VARCHAR(20) DEFAULT 'news',
    current_matched_keywords TEXT DEFAULT '',
    stakeholders_raw        TEXT        DEFAULT '[]',
    stakeholder_names       TEXT        DEFAULT '',
    stakeholder_types       TEXT        DEFAULT '',
    stakeholder_contacts    TEXT,
    llm_confidence          VARCHAR(20),
    tier_last_changed_at    TIMESTAMPTZ,
    times_tier_changed      INTEGER     DEFAULT 0,
    first_detected_at       TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at         TIMESTAMPTZ DEFAULT NOW(),
    feedback                VARCHAR(50) DEFAULT '',
    feedback_at             TIMESTAMPTZ,
    feedback_note           TEXT        DEFAULT '',
    retain_pii              BOOLEAN     DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS tier_changes (
    id                  SERIAL PRIMARY KEY,
    venue_name          VARCHAR(200),
    from_tier           INTEGER,
    from_tier_label     VARCHAR(100),
    to_tier             INTEGER,
    to_tier_label       VARCHAR(100),
    changed_at          TIMESTAMPTZ DEFAULT NOW(),
    trigger_headline    TEXT,
    trigger_source      VARCHAR(200),
    trigger_url         TEXT,
    score_at_change     NUMERIC,
    likelihood_at_change INTEGER,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS stakeholders (
    id               SERIAL PRIMARY KEY,
    venue_name       VARCHAR(200),
    league           VARCHAR(50),
    team             VARCHAR(200),
    signal_tier      INTEGER,
    engagement_action VARCHAR(50),
    stakeholder_name VARCHAR(200),
    title            VARCHAR(200),
    organization     VARCHAR(200),
    type             VARCHAR(100),
    website          VARCHAR(200),
    contact_email    VARCHAR(200),
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tuning_triggers (
    id               SERIAL PRIMARY KEY,
    root_cause       TEXT,
    occurrences      INTEGER,
    affected_venues  TEXT,
    recommendation   TEXT,
    triggered_at     TIMESTAMPTZ DEFAULT NOW(),
    resolved         BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_signals_venue   ON signals(venue_name);
CREATE INDEX IF NOT EXISTS idx_signals_run_at  ON signals(run_at);
CREATE INDEX IF NOT EXISTS idx_leads_engagement ON leads(current_engagement);
CREATE INDEX IF NOT EXISTS idx_tier_changes_at  ON tier_changes(changed_at);

-- Safety net for databases that already existed before feedback_at was
-- added above — CREATE TABLE IF NOT EXISTS is a no-op on an existing
-- table, so this ALTER ensures the column is there either way.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS feedback_at TIMESTAMPTZ;
"""


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def db_available() -> bool:
    try:
        conn = get_conn(); conn.close(); return True
    except Exception:
        return False


def init_db():
    """Create all tables if they don't exist."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()
        print("  [DB] Schema ready ✅", flush=True)
    except Exception as e:
        print(f"  [DB] Schema init failed: {e}", flush=True)


# ── Field normalizers ────────────────────────────────────────────

def _normalize_lead(r: dict) -> dict:
    """
    Map current reasoning_agent output fields → DB column names.
    Handles both old field names and new ones transparently.
    """
    # engagement: reasoning_agent outputs "engagement", DB stores as current_engagement
    engagement = (r.get("engagement_action") or
                  r.get("engagement") or "monitor")

    # score: reasoning_agent outputs "score", DB stores as current_score
    score = (r.get("final_score") or r.get("score"))

    # likelihood: reasoning_agent outputs "likelihood"
    likelihood = (r.get("project_likelihood") or r.get("likelihood"))

    # project_type → current_scale
    scale = (r.get("project_scale") or r.get("project_type") or "")

    # whats_happening → current_summary
    summary = (r.get("opportunity_summary") or r.get("whats_happening") or "")

    # why_priority → current_reason
    reason = (r.get("engagement_reason") or r.get("why_priority") or "")

    # source vs url: reasoning_agent puts URL in "source", name in "source_name"
    url     = r.get("url") or r.get("source") or ""
    src_name= r.get("source_name") or r.get("source") or ""

    # stakeholders_raw (JSON) → stakeholder_names (semicolons), stakeholder_types
    stakes_raw = r.get("stakeholders_raw") or "[]"
    try:
        stakes_list = json.loads(stakes_raw) if isinstance(stakes_raw, str) else stakes_raw
        names = "; ".join(s.get("name","") for s in stakes_list if s.get("name"))
        types = "; ".join(s.get("type","") for s in stakes_list if s.get("type"))
    except Exception:
        names = ""; types = ""

    return {
        "venue_name":     (r.get("venue_name") or "").strip(),
        "league":         r.get("league") or "",
        "city":           r.get("city") or "",
        "state":          r.get("state") or "",
        "capacity":       r.get("capacity"),
        "venue_status":   r.get("venue_status") or "existing",
        "year_built":     r.get("year_built") or "",
        "planned_year":   r.get("planned_year") or "",
        "owner_name":     r.get("owner_name") or r.get("owner") or "",
        "signal_tier":    r.get("signal_tier"),
        "tier_label":     r.get("tier_label") or "",
        "engagement":     engagement,
        "score":          _safe_float(score),
        "likelihood":     _safe_int(likelihood),
        "scale":          scale,
        "summary":        summary,
        "reason":         reason,
        "headline":       r.get("headline") or "",
        "src_name":       src_name,
        "url":            url,
        "signal_type":    r.get("signal_type") or "news",
        "matched_kw":     r.get("matched_keywords") or "",
        "stakes_raw":     stakes_raw if isinstance(stakes_raw, str) else json.dumps(stakes_raw),
        "stake_names":    names,
        "stake_types":    types,
        "llm_confidence": r.get("llm_confidence") or "",
    }


# ============================================================
# WRITE — SIGNALS
# ============================================================

def upsert_signals(signals: list[dict], signal_type: str = "news") -> int:
    """
    Store all raw signals from current run.
    signal_type: "news" for GNews signals, "government" for LegiStar/RSS signals.
    Skips duplicates (same venue + URL).
    """
    if not signals:
        return 0
    try:
        conn = get_conn()
        cur  = conn.cursor()
        inserted = 0
        for s in signals:
            try:
                pub = s.get("published_at") or s.get("run_at")
                cur.execute("""
                    INSERT INTO signals (
                        venue_name, league, city, state, capacity,
                        signal_tier, tier_label, signal_type,
                        headline, description, source, url,
                        published_at, matched_keywords,
                        opportunity_score, tier_score, venue_size_score,
                        recency_score, status_bonus, scraped_at, run_at
                    ) VALUES (
                        %s,%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,
                        %s,%s, %s,%s,%s,%s,%s, %s,%s
                    )
                    ON CONFLICT (venue_name, url) DO NOTHING
                """, (
                    s.get("venue_name",""),
                    s.get("league",""),
                    s.get("city",""),
                    s.get("state",""),
                    _safe_int(s.get("capacity")),
                    s.get("signal_tier"),          # None at signal stage — set by LLM later
                    s.get("tier_label",""),
                    s.get("signal_type") or signal_type,
                    s.get("headline",""),
                    s.get("description",""),
                    s.get("source_name") or s.get("source",""),
                    s.get("url",""),
                    _parse_ts(pub),
                    s.get("matched_keywords",""),
                    None, None, None, None, None,  # scores not computed at signal stage
                    _parse_ts(s.get("scraped_at")),
                    datetime.now(timezone.utc)
                ))
                if cur.rowcount > 0:
                    inserted += 1
            except Exception as e:
                conn.rollback()
                print(f"    [DB SIGNAL ERROR] {s.get('venue_name','?')}: {e}", flush=True)
                continue
            conn.commit()
        cur.close(); conn.close()
        print(f"  [DB] {inserted}/{len(signals)} new {signal_type} signals saved", flush=True)
        return inserted
    except Exception as e:
        print(f"  [DB] Signal write failed: {e}", flush=True)
        return 0


# ============================================================
# WRITE — LEADS
# ============================================================

def upsert_leads(results: list[dict]) -> dict:
    """
    For each result:
      NEW venue   → INSERT
      SEEN before → UPDATE (log tier change if tier moved)
    Returns stats dict.
    """
    stats = {"inserted": 0, "tier_changed": 0, "updated": 0, "errors": 0}

    try:
        conn = get_conn()
    except Exception as e:
        print(f"\n  [DB] Cannot connect: {e}", flush=True)
        print(f"  [DB] Is Docker running? → docker-compose up -d", flush=True)
        return stats

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now = datetime.now(timezone.utc)

    for r in results:
        n = _normalize_lead(r)
        venue_name = n["venue_name"]
        if not venue_name:
            continue

        try:
            cur.execute(
                "SELECT id, current_tier, current_tier_label, times_tier_changed "
                "FROM leads WHERE venue_name = %s",
                (venue_name,)
            )
            existing = cur.fetchone()

            if existing is None:
                # ── INSERT — new venue ────────────────────────
                cur.execute("""
                    INSERT INTO leads (
                        venue_name, league, city, state, capacity,
                        venue_status, year_built, planned_year, owner_name,
                        current_tier, current_tier_label, current_engagement,
                        current_score, current_likelihood, current_scale,
                        current_summary, current_reason,
                        current_headline, current_source, current_url,
                        current_signal_type, current_matched_keywords,
                        stakeholders_raw, stakeholder_names, stakeholder_types,
                        llm_confidence, tier_last_changed_at,
                        first_detected_at, last_updated_at
                    ) VALUES (
                        %s,%s,%s,%s,%s, %s,%s,%s,%s,
                        %s,%s,%s, %s,%s,%s, %s,%s,
                        %s,%s,%s, %s,%s, %s,%s,%s,
                        %s,%s, %s,%s
                    )
                """, (
                    venue_name,
                    n["league"], n["city"], n["state"],
                    _safe_int(n["capacity"]),
                    n["venue_status"], n["year_built"], n["planned_year"], n["owner_name"],
                    n["signal_tier"], n["tier_label"], n["engagement"],
                    n["score"], n["likelihood"], n["scale"],
                    n["summary"], n["reason"],
                    n["headline"], n["src_name"], n["url"],
                    n["signal_type"], n["matched_kw"],
                    n["stakes_raw"], n["stake_names"], n["stake_types"],
                    n["llm_confidence"], now, now, now
                ))

                # Log first detection in tier_changes
                cur.execute("""
                    INSERT INTO tier_changes (
                        venue_name, from_tier, from_tier_label,
                        to_tier, to_tier_label, changed_at,
                        trigger_headline, trigger_source, trigger_url,
                        score_at_change, likelihood_at_change, notes
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    venue_name, None, None,
                    n["signal_tier"], n["tier_label"], now,
                    n["headline"], n["src_name"], n["url"],
                    n["score"], n["likelihood"],
                    "First detection"
                ))

                conn.commit()
                stats["inserted"] += 1
                print(f"    [DB] NEW    {venue_name[:40]:<40} | {n['tier_label']}", flush=True)

            else:
                # ── UPDATE — existing venue ───────────────────
                old_tier       = existing["current_tier"]
                old_tier_label = existing["current_tier_label"] or ""
                tier_changed   = (old_tier != n["signal_tier"])

                cur.execute("""
                    UPDATE leads SET
                        league=%s, city=%s, state=%s, capacity=%s,
                        current_tier=%s, current_tier_label=%s,
                        current_engagement=%s, current_score=%s,
                        current_likelihood=%s, current_scale=%s,
                        current_summary=%s, current_reason=%s,
                        current_headline=%s, current_source=%s,
                        current_url=%s, current_signal_type=%s,
                        current_matched_keywords=%s,
                        stakeholders_raw=%s, stakeholder_names=%s,
                        stakeholder_types=%s, llm_confidence=%s,
                        last_updated_at=%s,
                        tier_last_changed_at = CASE WHEN %s THEN %s
                                               ELSE tier_last_changed_at END,
                        times_tier_changed   = CASE WHEN %s
                                               THEN times_tier_changed + 1
                                               ELSE times_tier_changed END
                    WHERE venue_name=%s
                """, (
                    n["league"], n["city"], n["state"],
                    _safe_int(n["capacity"]),
                    n["signal_tier"], n["tier_label"],
                    n["engagement"], n["score"],
                    n["likelihood"], n["scale"],
                    n["summary"], n["reason"],
                    n["headline"], n["src_name"], n["url"],
                    n["signal_type"], n["matched_kw"],
                    n["stakes_raw"], n["stake_names"],
                    n["stake_types"], n["llm_confidence"],
                    now,
                    tier_changed, now,
                    tier_changed,
                    venue_name
                ))

                if tier_changed:
                    cur.execute("""
                        INSERT INTO tier_changes (
                            venue_name, from_tier, from_tier_label,
                            to_tier, to_tier_label, changed_at,
                            trigger_headline, trigger_source, trigger_url,
                            score_at_change, likelihood_at_change, notes
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        venue_name, old_tier, old_tier_label,
                        n["signal_tier"], n["tier_label"], now,
                        n["headline"], n["src_name"], n["url"],
                        n["score"], n["likelihood"],
                        f"Tier T{old_tier} → T{n['signal_tier']}"
                    ))
                    conn.commit()
                    stats["tier_changed"] += 1
                    arrow = "UP" if (n["signal_tier"] or 0) > (old_tier or 0) else "DOWN"
                    print(f"    [DB] TIER {arrow}  {venue_name[:35]:<35} | T{old_tier}→T{n['signal_tier']}", flush=True)
                else:
                    conn.commit()
                    stats["updated"] += 1
                    print(f"    [DB] UPDATE {venue_name[:40]:<40} | T{n['signal_tier']} (no change)", flush=True)

        except Exception as e:
            conn.rollback()
            print(f"    [DB ERROR] {venue_name}: {e}", flush=True)
            stats["errors"] += 1

    cur.close(); conn.close()
    return stats


# ============================================================
# READ — for Excel + Dashboard
# ============================================================

def get_all_leads_for_excel() -> list[dict]:
    """
    Read ALL leads from DB, sorted by score (with recency as a
    tiebreak — see note below).
    Returns fields matching dashboard expectations:
      engagement_action, final_score, first_detected_at, stakeholder_names
    """
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # NOTE: previously this was `ORDER BY current_score DESC NULLS LAST`
        # only — a lead that scored high 60 days ago would always outrank
        # a lead that became Act Now TODAY with a slightly lower score,
        # since recency played no role at all. Adding last_updated_at as
        # a secondary sort key means today's run's leads surface first
        # among similarly-scored leads, without fully overriding score
        # (which is still the primary, most important signal).
        cur.execute("""
            SELECT * FROM leads
            ORDER BY current_score DESC NULLS LAST,
                     last_updated_at DESC NULLS LAST
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()

        results = []
        for i, row in enumerate(rows, 1):
            results.append({
                "rank":              i,
                "venue_name":        row["venue_name"] or "",
                "league":            row["league"] or "",
                "city":              row["city"] or "",
                "state":             row["state"] or "",
                "capacity":          row["capacity"] or "",
                "venue_status":      row["venue_status"] or "existing",
                "year_built":        row["year_built"] or "",
                "planned_year":      row["planned_year"] or "",
                "owner_name":        row["owner_name"] or "",
                "signal_tier":       row["current_tier"],
                "tier_label":        row["current_tier_label"] or "",
                # Dashboard-expected field names:
                "engagement_action": row["current_engagement"] or "",
                "final_score":       row["current_score"],
                "project_likelihood":row["current_likelihood"],
                "project_scale":     row["current_scale"] or "",
                "whats_happening":   row["current_summary"] or "",
                "why_priority":      row["current_reason"] or "",
                "headline":          row["current_headline"] or "",
                "source":            row["current_url"] or "",
                "source_name":       row["current_source"] or "",
                "signal_type":       row["current_signal_type"] or "news",
                "matched_keywords":  row["current_matched_keywords"] or "",
                "stakeholders_raw":  row["stakeholders_raw"] or "[]",
                "stakeholder_names": row["stakeholder_names"] or "",
                "stakeholder_types": row["stakeholder_types"] or "",
                "llm_confidence":    row["llm_confidence"] or "",
                "first_detected_at": str(row["first_detected_at"])[:10] if row["first_detected_at"] else "",
                "last_updated_at":   str(row["last_updated_at"])[:10] if row["last_updated_at"] else "",
                "times_tier_changed":row["times_tier_changed"] or 0,
                "feedback":          row["feedback"] or "",
                "feedback_note":     row["feedback_note"] or "",
            })
        return results
    except Exception as e:
        print(f"  [DB] Could not read leads: {e}", flush=True)
        return []


def get_all_signals_for_excel(days: int = 90) -> list[dict]:
    """Read all signals from last N days — 2 per venue max."""
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY venue_name
                           ORDER BY opportunity_score DESC NULLS LAST, run_at DESC
                       ) AS rn
                FROM signals
                WHERE run_at >= NOW() - (%s * INTERVAL '1 day')
            ) ranked
            WHERE rn <= 2
            ORDER BY opportunity_score DESC NULLS LAST, run_at DESC
        """, (days,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        signals = []
        for i, row in enumerate(rows, 1):
            signals.append({
                "rank":             i,
                "venue_name":       row["venue_name"] or "",
                "league":           row["league"] or "",
                "city":             row["city"] or "",
                "state":            row["state"] or "",
                "capacity":         row["capacity"] or "",
                "signal_tier":      row["signal_tier"],
                "tier_label":       row["tier_label"] or "",
                "signal_type":      row["signal_type"] or "news",
                "headline":         row["headline"] or "",
                "source":           row["source"] or "",
                "url":              row["url"] or "",
                "published_at":     str(row["published_at"])[:19] if row["published_at"] else "",
                "matched_keywords": row["matched_keywords"] or "",
                "opportunity_score":row["opportunity_score"] or 0,
            })
        return signals
    except Exception as e:
        print(f"  [DB] Could not read signals: {e}", flush=True)
        return []


def get_tier_alerts() -> list[dict]:
    """Venues that changed tier in the last 7 days."""
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT tc.venue_name, l.league, l.city,
                   tc.from_tier, tc.from_tier_label,
                   tc.to_tier, tc.to_tier_label,
                   tc.changed_at, tc.notes,
                   l.current_engagement, l.current_score
            FROM tier_changes tc
            JOIN leads l ON l.venue_name = tc.venue_name
            WHERE tc.changed_at >= NOW() - INTERVAL '7 days'
              AND tc.from_tier IS NOT NULL
            ORDER BY tc.changed_at DESC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"  [DB] Could not fetch tier alerts: {e}", flush=True)
        return []


# ============================================================
# PII CLEANUP
# ============================================================

def purge_old_pii() -> int:
    """
    Nullify stakeholder contacts/names for leads older than 12 months.

    FIX: the original version only cleared `stakeholder_contacts` and
    `stakeholders_raw`. It missed `stakeholder_names` and
    `stakeholder_types` — two SEPARATE columns that are populated
    independently at upsert time (see _normalize_lead) and read
    directly by dashboard_writer.py's "Firms Identified" KPI
    (r.get("stakeholder_names")). Without this fix, a purged lead's
    JSON (stakeholders_raw) is wiped, but the plain-text name list
    sitting in stakeholder_names survives untouched — meaning old PII
    (person names) keeps showing up on the dashboard indefinitely,
    defeating the purpose of the purge.
    """
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE leads
            SET stakeholder_contacts = NULL,
                stakeholders_raw     = '[]',
                stakeholder_names    = '',
                stakeholder_types    = ''
            WHERE first_detected_at < NOW() - INTERVAL '12 months'
              AND (retain_pii IS NULL OR retain_pii = FALSE)
              AND (stakeholder_contacts IS NOT NULL
                   OR stakeholders_raw  != '[]'
                   OR stakeholder_names != ''
                   OR stakeholder_types != '')
        """)
        count = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        return count
    except Exception as e:
        print(f"  [DB] PII purge failed: {e}", flush=True)
        return 0


# ============================================================
# FEEDBACK FUNCTIONS
# ============================================================

def get_archived_venues() -> set:
    """Venues Matthew marked Archive — excluded from pipeline."""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT LOWER(venue_name) FROM leads
            WHERE feedback = 'Archive'
               OR current_engagement = 'archived'
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        result = {r[0] for r in rows}
        if result:
            print(f"  [DB] {len(result)} archived venue(s) excluded", flush=True)
        return result
    except Exception as e:
        print(f"  [DB] Archived venues fetch failed: {e}", flush=True)
        return set()


def get_pursuing_venues() -> set:
    """Venues Matthew marked Pursuing — get +15 score boost."""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT LOWER(venue_name) FROM leads WHERE feedback = 'Pursuing'")
        rows = cur.fetchall()
        cur.close(); conn.close()
        result = {r[0] for r in rows}
        if result:
            print(f"  [DB] {len(result)} pursuing venue(s) will get score boost", flush=True)
        return result
    except Exception as e:
        print(f"  [DB] Pursuing venues fetch failed: {e}", flush=True)
        return set()


def get_bad_data_patterns() -> list[dict]:
    """Find root causes where 3+ leads were tagged Bad Data."""
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                LOWER(TRIM(feedback_note))     AS root_cause,
                COUNT(*)                        AS occurrences,
                STRING_AGG(venue_name, ', ')    AS affected_venues
            FROM leads
            WHERE feedback = 'Bad Data'
              AND feedback_note IS NOT NULL
              AND TRIM(feedback_note) != ''
            GROUP BY LOWER(TRIM(feedback_note))
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"  [DB] Pattern check failed: {e}", flush=True)
        return []


def log_tuning_trigger(root_cause: str, count: int, venues: str, recommendation: str):
    """Log a tuning trigger to DB for tracking."""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO tuning_triggers
                (root_cause, occurrences, affected_venues, recommendation)
            VALUES (%s, %s, %s, %s)
        """, (root_cause, count, venues, recommendation))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"  [DB] Could not log tuning trigger: {e}", flush=True)


def get_active_tuning_triggers() -> list[dict]:
    """Read unresolved tuning triggers — injected into LLM prompt."""
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT root_cause, occurrences, affected_venues, recommendation
            FROM tuning_triggers
            WHERE resolved = FALSE
            ORDER BY occurrences DESC LIMIT 10
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"  [DB] Tuning triggers fetch failed: {e}", flush=True)
        return []


def get_bad_data_notes_by_venue() -> dict:
    """Returns {venue_name_lower: [notes]} for all Bad Data leads."""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT LOWER(TRIM(venue_name)), feedback_note FROM leads
            WHERE feedback = 'Bad Data'
              AND feedback_note IS NOT NULL
              AND TRIM(feedback_note) != ''
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        result = {}
        for name, note in rows:
            result.setdefault(name, []).append(note)
        return result
    except Exception as e:
        print(f"  [DB] Bad data notes fetch failed: {e}", flush=True)
        return {}


def get_passed_venues() -> set:
    """Venues Matthew marked Passed — used to slightly lower similar lead scores."""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT LOWER(venue_name) FROM leads WHERE feedback = 'Passed'")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {r[0] for r in rows}
    except Exception as e:
        print(f"  [DB] Passed venues fetch failed: {e}", flush=True)
        return set()


# ============================================================
# HELPERS
# ============================================================

def _safe_float(val):
    try:    return float(val) if val is not None else None
    except: return None

def _safe_int(val):
    try:    return int(val) if val is not None else None
    except: return None

def _parse_ts(val):
    if not val: return None
    try:
        if isinstance(val, str):
            return datetime.fromisoformat(val.replace("Z","+00:00"))
        return val
    except Exception:
        return None