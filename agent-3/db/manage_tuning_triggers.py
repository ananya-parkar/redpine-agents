"""
Small CLI for managing tuning_triggers - the human side of the
learning loop.

Usage (run from agent-3 root):
    python -m db.manage_tuning_triggers list
    python -m db.manage_tuning_triggers resolve <id>

`list` shows every currently-active trigger (these are the ones being
injected into discover_companies()/profile_company() prompts right
now). `resolve <id>` marks one as resolved once you've confirmed
whatever fix was needed actually landed - it then stops being injected
into future prompts.
"""

import sys
from db.feedback_sync import get_connection


def list_active_triggers():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, feedback_type, root_cause, occurrences,
                       recommendation, created_at, updated_at
                FROM tuning_triggers
                WHERE status = 'active'
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No active tuning triggers.")
        return

    print(f"\n{len(rows)} active tuning trigger(s):\n")
    for (trigger_id, feedback_type, root_cause, occurrences,
         recommendation, created_at, updated_at) in rows:
        print(f"[{trigger_id}] ({feedback_type}, {occurrences}x) \"{root_cause}\"")
        print(f"    Recommendation: {recommendation}")
        print(f"    First seen: {created_at} | Last updated: {updated_at}")
        print()


def resolve_trigger(trigger_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT root_cause, feedback_type FROM tuning_triggers WHERE id = %s",
                (trigger_id,),
            )
            row = cur.fetchone()
            if not row:
                print(f"No trigger found with id {trigger_id}.")
                return
            cur.execute(
                "UPDATE tuning_triggers SET status = 'resolved', updated_at = NOW() WHERE id = %s",
                (trigger_id,),
            )
        conn.commit()
        print(f"Marked trigger {trigger_id} (\"{row[0]}\", {row[1]}) as resolved. "
              f"It will no longer be injected into future prompts.")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "resolve"):
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "list":
        list_active_triggers()
    elif sys.argv[1] == "resolve":
        if len(sys.argv) < 3:
            print("Usage: python -m db.manage_tuning_triggers resolve <id>")
            sys.exit(1)
        resolve_trigger(int(sys.argv[2]))