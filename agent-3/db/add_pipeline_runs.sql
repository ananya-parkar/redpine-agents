-- agent-3/db/add_pipeline_runs.sql
-- Run this once against redpine_agent3 to add run-history tracking
-- (needed for "vs Last Week" deltas on the dashboard).
--
--   docker cp add_pipeline_runs.sql redpine-postgres:/add_pipeline_runs.sql
--   docker exec -it redpine-postgres psql -U postgres -d redpine_agent3 -f /add_pipeline_runs.sql

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  SERIAL PRIMARY KEY,
    run_date            DATE NOT NULL DEFAULT CURRENT_DATE,
    run_timestamp        TIMESTAMP NOT NULL DEFAULT NOW(),
    total_targets         INTEGER NOT NULL,
    new_this_run          INTEGER NOT NULL,
    shortlisted           INTEGER NOT NULL,
    in_review             INTEGER NOT NULL,
    reviewed              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_date ON pipeline_runs(run_date);