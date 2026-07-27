CREATE TABLE IF NOT EXISTS hotel_leads (
    id                          SERIAL PRIMARY KEY,
    hotel_name                  TEXT,
    address                     TEXT,
    lead_key                    TEXT,
    place_id                    TEXT UNIQUE,
    final_lead_score            NUMERIC,
    opportunity_score           NUMERIC,
    owner_name                  TEXT,
    mailing_address             TEXT,
    franchise_affiliated        BOOLEAN,
    current_brand               TEXT,
    franchise_loss_date         DATE,
    distress_probability        NUMERIC,
    seller_fatigue_probability  NUMERIC,
    review_summary              TEXT,
    investment_thesis           TEXT,
    recommended_action          TEXT,
    distress_summary            TEXT,
    llm_star_rating             NUMERIC,
    ownership_since             DATE,
    ownership_length_years      INTEGER,
    attom_year_built            INTEGER,
    cmbs_watchlist              BOOLEAN DEFAULT FALSE,
    cmbs_delinquent             BOOLEAN DEFAULT FALSE,
    cmbs_special_servicing      BOOLEAN DEFAULT FALSE,
    room_count                  INTEGER,
    price_tier                  TEXT,
    lead_reason                 TEXT,
    lead_status                 VARCHAR(20) DEFAULT 'NEW',
    first_surfaced              TIMESTAMP,
    last_resurfaced             TIMESTAMP,
    last_score                  NUMERIC,
    feedback_reason             TEXT,
    feedback_notes              TEXT,
    feedback_penalty            NUMERIC DEFAULT 0,
    feedback_rule_applied       VARCHAR(100),
    cleanup_due_date            TIMESTAMP,
    pii_retention_exempt        BOOLEAN DEFAULT FALSE,
    created_at                  TIMESTAMP DEFAULT NOW()
);



CREATE INDEX IF NOT EXISTS idx_hotel_leads_status
ON hotel_leads(lead_status);


CREATE INDEX IF NOT EXISTS idx_hotel_leads_score
ON hotel_leads(final_lead_score);


CREATE INDEX IF NOT EXISTS idx_hotel_leads_leadkey
ON hotel_leads(lead_key);


CREATE INDEX IF NOT EXISTS idx_hotel_leads_place_id
ON hotel_leads(place_id);



CREATE TABLE IF NOT EXISTS lead_feedback (
    id              SERIAL PRIMARY KEY,
    address         TEXT,
    lead_status     TEXT,
    notes           TEXT,
    updated_at      TIMESTAMP
);



CREATE TABLE IF NOT EXISTS feedback_actions (
    id                      SERIAL PRIMARY KEY,
    feedback_reason         VARCHAR(100),
    trigger_count           INTEGER,
    action_taken            TEXT,
    recommended_fix         TEXT,
    recommendation_json     JSONB,
    status                  VARCHAR(20) DEFAULT 'PENDING',
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP,
    CONSTRAINT ux_feedback_reason
    UNIQUE(feedback_reason)
);



CREATE TABLE IF NOT EXISTS agent_runs (
    run_id                  UUID PRIMARY KEY,
    started_at              TIMESTAMP,
    completed_at            TIMESTAMP,
    search_area             TEXT,
    locations_processed     INTEGER,
    hotels_found            INTEGER,
    hotels_after_dedupe     INTEGER,
    new_leads               INTEGER DEFAULT 0,
    duplicates              INTEGER DEFAULT 0,
    priority_leads          INTEGER,
    email_sent              BOOLEAN
);