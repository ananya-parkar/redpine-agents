-- agent-3/db/schema.sql
-- Run after creating the database:
--   docker exec -it redpine-postgres psql -U postgres -c "CREATE DATABASE redpine_agent3;"
--   docker cp schema.sql redpine-postgres:/schema.sql
--   docker exec -it redpine-postgres psql -U postgres -d redpine_agent3 -f /schema.sql

-- ---------------------------------------------------------------------------
-- candidates: one row per unique company. The stable identity + structured
-- facts from Layers 1-4. This replaces master_reviewed_companies.csv.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidates (
    id                      SERIAL PRIMARY KEY,
    company_name            TEXT NOT NULL,
    normalized_name         TEXT NOT NULL,   -- lowercased, suffix-stripped, used for dedup matching
    state                   TEXT,
    industry                TEXT,
    company_type            TEXT,
    founded_year            TEXT,
    revenue_estimate        TEXT,
    years_in_business       INTEGER,
    founder_name            TEXT,
    founder_led             TEXT,
    family_owned            TEXT,
    founder_age_estimate    TEXT,
    ownership_status        TEXT,
    ownership_tenure_years  INTEGER,
    extraction_confidence   TEXT,
    seller_readiness_score  INTEGER,
    first_seen_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    last_seen_date            DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at               TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMP NOT NULL DEFAULT NOW(),

    -- prevents the same company (by normalized name + state) being inserted twice
    UNIQUE (normalized_name, state)
);

-- ---------------------------------------------------------------------------
-- evidence: one row per company holding raw evidence + LLM rationale.
-- Kept separate from candidates since this is reasoning-layer output,
-- and could later hold multiple evidence entries per company over time.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evidence (
    id                   SERIAL PRIMARY KEY,
    candidate_id         INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    raw_evidence         TEXT,
    why_selected         TEXT,
    evidence_summary     TEXT,
    one_line_reason      TEXT,
    evidence_sources     TEXT,
    raw_evidence_summary TEXT,
    created_at           TIMESTAMP NOT NULL DEFAULT NOW()
);
-- ---------------------------------------------------------------------------
-- review_status: tracks human review state per company over time.
-- Maps to Layer 8 (Review Status Storage) in the pipeline diagram.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_status (
    id              SERIAL PRIMARY KEY,
    candidate_id     INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    status           TEXT NOT NULL DEFAULT 'New',   -- New / Pursuing / Passed / Bad Data
    comments         TEXT,
    reviewed_by       TEXT,
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE (candidate_id)   -- one current status row per candidate; history via updated_at if needed later
);

-- Helpful indexes for dashboard filtering (geography, score, status)
CREATE INDEX IF NOT EXISTS idx_candidates_state ON candidates(state);
CREATE INDEX IF NOT EXISTS idx_candidates_score ON candidates(seller_readiness_score);
CREATE INDEX IF NOT EXISTS idx_review_status_status ON review_status(status);
