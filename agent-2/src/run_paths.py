"""
run_paths.py — Manages dated Excel output files in a runs/ folder.

Each pipeline run writes to its own file in runs/ instead of
overwriting one fixed path. This lets the client compare any two
runs' workbooks side by side, and lets feedback_reader.py find the
most recent PREVIOUS run (the one Matthew/Anshi actually had a chance
to download and edit) without confusing it with the file THIS run is
about to create.

FIXED: filenames now include the TIME, not just the date
(stadium_leads_2026-06-24_143022.xlsx). The original date-only
version broke if the pipeline ran more than once on the same
calendar day — the second run's "today's file" path was IDENTICAL
to the first run's already-saved file, so get_latest_previous_run_file()
excluded it (thinking it was "today's file, not created yet") and
fell back to an OLDER file instead — meaning any feedback/notes added
between the two same-day runs were silently skipped.

With time included, "today's file" is always a brand-new path that
has never existed before, so no exclusion logic is needed at all —
get_latest_previous_run_file() can simply return whatever file
already exists on disk, which correctly includes a same-day earlier
run.
"""

from pathlib import Path
from datetime import datetime

RUNS_DIR = Path(__file__).parent / "runs"

# Cached per-process so multiple calls within ONE pipeline run always
# return the SAME path — otherwise calling this twice (e.g. once to
# log it, once to actually save) a few seconds apart would generate
# two DIFFERENT timestamps and the email would attach the wrong file.
_current_run_file: Path | None = None


def get_todays_output_file() -> Path:
    """
    Path for THIS run — runs/stadium_leads_YYYY-MM-DD_HHMMSS.xlsx.
    Where save_excel() writes to at STEP 6, and the file attached to
    this run's email. Computing this does NOT create the file on disk
    — that only happens later, when save_excel() actually writes to it.
    """
    global _current_run_file
    if _current_run_file is None:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        _current_run_file = RUNS_DIR / f"stadium_leads_{ts}.xlsx"
    return _current_run_file


def get_latest_previous_run_file() -> Path | None:
    """
    Most recent EXISTING dated Excel file in runs/.

    This is always called at STEP 0, before THIS run's own file is
    created at STEP 6 — so the current run's file simply doesn't
    exist on disk yet, and no date/time-based exclusion is needed.
    Just return whatever the latest existing file is. This correctly
    picks up a file from an EARLIER run today (the bug in the old
    date-only version), as well as yesterday's file on a normal
    once-a-day schedule.

    Returns None if no previous run file exists yet (e.g. the very
    first time the pipeline is ever run).
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(RUNS_DIR.glob("stadium_leads_*.xlsx"))
    return files[-1] if files else None


def list_all_runs() -> list[Path]:
    """All dated run files, oldest to newest — useful for a future
    'compare two days' feature."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(RUNS_DIR.glob("stadium_leads_*.xlsx"))