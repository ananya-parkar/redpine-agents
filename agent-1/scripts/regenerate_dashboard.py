#agent-1/scripts/regenerate_dashboard.py
import pickle
import pandas as pd

from src.core.config import RUNS_DIR
from src.reporting.dashboard.dashboard_export import export_dashboard

def latest_run():
    runs = [
        d for d in RUNS_DIR.iterdir()
        if d.is_dir() and (d / "dashboard_source.pkl").exists()
    ]
    if not runs:
        raise RuntimeError("No run folders found.")

    return max(runs, key=lambda d: d.stat().st_mtime)


def main():

    run_dir = latest_run()
    dashboard_source = run_dir / "dashboard_source.pkl"
    if not dashboard_source.exists():
        raise FileNotFoundError(dashboard_source)

    print(f"Using run: {run_dir.name}")

    with open(dashboard_source, "rb") as f:
        rows = pickle.load(f)

    reports_dir = run_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    dashboard = export_dashboard(
        reports_dir,
        rows
    )

    print()
    print("Dashboard regenerated")
    print(dashboard)


if __name__ == "__main__":
    main()