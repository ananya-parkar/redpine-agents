-- ============================================================
-- STADIUM LEAD GEN — DATABASE SCHEMA
-- Three tables:
--   signals      — every raw signal ever collected (history)
--   leads        — one row per venue, current best state
--   tier_changes — audit log of every tier progression
-- ============================================================

-- -----------------------------------------------------------
-- SIGNALS — full history of every signal from every run
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    id                  SERIAL PRIMARY KEY,
    venue_name          VARCHAR(120),
    league              VARCHAR(50),
    city                VARCHAR(60),
    state               VARCHAR(20),
    capacity            INTEGER,
    signal_tier         INTEGER,
    tier_label          VARCHAR(60),
    signal_type         VARCHAR(20),
    headline            TEXT,
    description         TEXT,
    source              VARCHAR(200),
    url                 TEXT,
    published_at        TIMESTAMPTZ,
    matched_keywords    TEXT,
    opportunity_score   FLOAT,
    tier_score          INTEGER,
    venue_size_score    INTEGER,
    recency_score       INTEGER,
    status_bonus        INTEGER,
    scraped_at          TIMESTAMPTZ,
    run_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (venue_name, url)
);

-- -----------------------------------------------------------
-- LEADS — one row per venue, updated every run
-- This is the master table the Excel dashboard reads from
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS leads (
    id                       SERIAL PRIMARY KEY,
    venue_name               VARCHAR(120) UNIQUE NOT NULL,
    league                   VARCHAR(50),
    city                     VARCHAR(60),
    state                    VARCHAR(20),
    capacity                 INTEGER,
    venue_status             VARCHAR(50),
    year_built               VARCHAR(10),
    planned_year             VARCHAR(10),
    owner_name               VARCHAR(100),

    -- Current best signal
    current_tier             INTEGER,
    current_tier_label       VARCHAR(60),
    current_engagement       VARCHAR(50),
    current_score            FLOAT,
    current_likelihood       INTEGER,
    current_scale            VARCHAR(50),
    current_summary          TEXT,
    current_reason           TEXT,
    current_headline         TEXT,
    current_source           VARCHAR(200),
    current_url              TEXT,
    current_signal_type      VARCHAR(20),
    current_matched_keywords TEXT,

    -- Stakeholders (full JSON + display strings)
    stakeholders_raw         TEXT,
    stakeholder_names        TEXT,
    stakeholder_types        TEXT,
    llm_confidence           VARCHAR(20),

    -- Tier tracking
    tier_last_changed_at     TIMESTAMPTZ,
    times_tier_changed       INTEGER DEFAULT 0,

    -- Timestamps
    first_detected_at        TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- TIER_CHANGES — append-only audit log
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS tier_changes (
    id                   SERIAL PRIMARY KEY,
    venue_name           VARCHAR(120) NOT NULL,
    from_tier            INTEGER,
    from_tier_label      VARCHAR(60),
    to_tier              INTEGER,
    to_tier_label        VARCHAR(60),
    changed_at           TIMESTAMPTZ DEFAULT NOW(),
    trigger_headline     TEXT,
    trigger_source       VARCHAR(200),
    trigger_url          TEXT,
    score_at_change      FLOAT,
    likelihood_at_change INTEGER,
    notes                VARCHAR(300)
);

-- -----------------------------------------------------------
-- INDEXES
-- -----------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_signals_venue    ON signals(venue_name);
CREATE INDEX IF NOT EXISTS idx_signals_run_at   ON signals(run_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_tier       ON leads(current_tier);
CREATE INDEX IF NOT EXISTS idx_leads_engagement ON leads(current_engagement);
CREATE INDEX IF NOT EXISTS idx_leads_updated    ON leads(last_updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tc_venue         ON tier_changes(venue_name);
CREATE INDEX IF NOT EXISTS idx_tc_date          ON tier_changes(changed_at DESC);

-- PII + feedback columns (run once)
ALTER TABLE leads ADD COLUMN IF NOT EXISTS stakeholder_contacts TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS retain_pii           BOOLEAN DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS feedback             VARCHAR(30);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS feedback_note        TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS feedback_at          TIMESTAMPTZ;