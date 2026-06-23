"""
run_paths.py — Manages dated Excel output files in a runs/ folder.

Each pipeline run writes to runs/stadium_leads_YYYY-MM-DD.xlsx instead
of overwriting one fixed file. This lets the client compare any two
days' workbooks side by side, and lets feedback_reader.py find the
most recent PREVIOUS run (the one Matthew/Anshi actually had a chance
to download and edit) without confusing it with today's file, which
gets created fresh later in the same run.
"""

from pathlib import Path
from datetime import date

RUNS_DIR = Path(__file__).parent / "runs"


def get_todays_output_file() -> Path:
    """
    Path for TODAY's run — where save_excel() writes to at STEP 6,
    and the file attached to today's email.
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR / f"stadium_leads_{date.today().isoformat()}.xlsx"


def get_latest_previous_run_file() -> Path | None:
    """
    Most recent EXISTING dated Excel file in runs/, excluding today's
    (which may not exist yet — it's created at STEP 6 of THIS run, but
    feedback needs to be read at STEP 0, before that happens).

    feedback_reader.py uses this to find the file Matthew/Anshi most
    recently downloaded and edited with Pursuing/Archive/Bad Data/etc.

    Returns None if no previous run file exists yet (e.g. the very
    first time the pipeline is ever run).
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    today_file = get_todays_output_file()
    files = sorted(
        f for f in RUNS_DIR.glob("stadium_leads_*.xlsx")
        if f != today_file
    )
    return files[-1] if files else None


def list_all_runs() -> list[Path]:
    """All dated run files, oldest to newest — useful for a future
    'compare two days' feature."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(RUNS_DIR.glob("stadium_leads_*.xlsx"))