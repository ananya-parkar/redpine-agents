"""
wipe_db.py — Wipes ALL Agent 2 pipeline data for a completely fresh start.

Truncates: signals, leads, tier_changes, stakeholders, tuning_triggers
RESTART IDENTITY resets auto-increment IDs back to 1.
CASCADE handles any foreign-key dependent rows automatically.

Usage:
    python wipe_db.py            # asks for confirmation first
    python wipe_db.py --yes      # skips confirmation (for scripts/CI)
"""

import sys
from db_writer import get_conn

TABLES = ["signals", "leads", "tier_changes", "stakeholders", "tuning_triggers"]


def wipe():
    conn = get_conn()
    cur = conn.cursor()
    table_list = ", ".join(TABLES)
    cur.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Wiped: {table_list}")
    print("   All tables empty, auto-increment IDs reset to 1.")


if __name__ == "__main__":
    skip_confirm = "--yes" in sys.argv

    if not skip_confirm:
        print("⚠️  This will PERMANENTLY delete ALL data in:")
        for t in TABLES:
            print(f"     - {t}")
        confirm = input("Type 'wipe' to confirm: ").strip().lower()
        if confirm != "wipe":
            print("Cancelled — no changes made.")
            sys.exit(0)

    wipe()