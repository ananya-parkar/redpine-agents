-- agent-3/db/add_search_requests.sql
--
-- Scopes candidates to the search request that found them, so switching
-- geography/industry/etc gives the client a clean slate instead of
-- mixing old Florida leads into a new Texas run.
--
-- Run with:
--   docker cp add_search_requests.sql redpine-postgres:/add_search_requests.sql
--   docker exec -it redpine-postgres psql -U postgres -d redpine_agent3 -f /add_search_requests.sql

-- ---------------------------------------------------------------------
-- 1. The search request registry.
--    request_key is a canonical string of all params (see
--    search_request_db.build_request_key). Single TEXT UNIQUE rather
--    than a multi-column UNIQUE, because Postgres treats NULLs as
--    distinct - a multi-column UNIQUE would let duplicate rows through
--    whenever an optional param was blank.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS search_requests (
    id                    SERIAL PRIMARY KEY,
    request_key           TEXT NOT NULL UNIQUE,
    geography             TEXT,
    industry              TEXT,
    revenue_range         TEXT,
    min_years             INTEGER,
    ownership_preference  TEXT,
    founder_age           TEXT,
    created_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- 2. Tag every candidate with the search that found it.
-- ---------------------------------------------------------------------
ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS search_request_id INTEGER
    REFERENCES search_requests(id) ON DELETE CASCADE;

-- ---------------------------------------------------------------------
-- 3. Backfill: park every EXISTING candidate under one "legacy" search
--    request, so old rows aren't orphaned with a NULL scope (they'd
--    otherwise vanish from every scoped query and never be deduped
--    against again).
-- ---------------------------------------------------------------------
INSERT INTO search_requests (request_key, geography)
VALUES ('__legacy__', 'Legacy (pre-scoping runs)')
ON CONFLICT (request_key) DO NOTHING;

UPDATE candidates
SET search_request_id = (
        SELECT id FROM search_requests WHERE request_key = '__legacy__'
    )
WHERE search_request_id IS NULL;

-- ---------------------------------------------------------------------
-- 4. Uniqueness is now PER SEARCH, not global.
--    The same company can legitimately appear under two different
--    searches (client might pursue it under one mandate, pass under
--    another) - each gets its own row and its own review_status.
-- ---------------------------------------------------------------------
ALTER TABLE candidates
    DROP CONSTRAINT IF EXISTS candidates_normalized_name_state_key;

ALTER TABLE candidates
    DROP CONSTRAINT IF EXISTS candidates_unique_per_search;

ALTER TABLE candidates
    ADD CONSTRAINT candidates_unique_per_search
    UNIQUE (normalized_name, state, search_request_id);

-- ---------------------------------------------------------------------
-- 5. pipeline_runs must be scoped too, or the dashboard's "vs Last
--    Week" deltas would compare this week's Texas run against last
--    week's Florida run.
-- ---------------------------------------------------------------------
ALTER TABLE pipeline_runs
    ADD COLUMN IF NOT EXISTS search_request_id INTEGER
    REFERENCES search_requests(id) ON DELETE CASCADE;

UPDATE pipeline_runs
SET search_request_id = (
        SELECT id FROM search_requests WHERE request_key = '__legacy__'
    )
WHERE search_request_id IS NULL;

-- ---------------------------------------------------------------------
-- 6. Indexes for the scoped lookups the dashboard/dedupe now do.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_candidates_search_request
    ON candidates(search_request_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_search_request
    ON pipeline_runs(search_request_id);