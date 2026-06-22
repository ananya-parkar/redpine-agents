"""
agent-3/dashboard/test_dashboard_local.py

Quick-iteration script for dashboard formatting.
Run this directly (no pipeline run needed) to regenerate the Excel
dashboard from whatever is currently in Postgres:

    python test_dashboard_local.py

Edit dashboard.py, save, rerun this script, check the output file.
Repeat until formatting is finalized.
"""

from dashboard.dashboard import generate_dashboard

if __name__ == "__main__":
    output_path = "test_dashboard_output.xlsx"
    generate_dashboard(output_path)
    print(f"\nOpen {output_path} to review formatting changes.")