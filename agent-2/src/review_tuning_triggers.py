"""
review_tuning_triggers.py — Human-in-the-loop approval for tuning triggers.

Per the SOW requirement: the pipeline should TRIGGER a recommendation
when the same Bad Data root cause is flagged 3+ times — it should NOT
automatically apply that recommendation to its own prompts. A newly
detected pattern is logged with status='pending' (see db_writer.py's
log_tuning_trigger) and has ZERO effect on reasoning_agent.py or
stakeholder_enrichment.py until a developer runs this script and
explicitly approves it.

This creates the continuous-improvement loop the SOW describes, while
keeping a human in control of what changes the sourcing/scoring
behavior — nothing changes silently based on 3 coincidentally-similar
feedback notes.

Usage:
    python review_tuning_triggers.py
"""

import psycopg2.extras
from db_writer import get_conn
from tuning_prompt import _match_rule


def get_pending_triggers() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, root_cause, occurrences, affected_venues,
               recommendation, triggered_at
        FROM tuning_triggers
        WHERE status = 'pending'
        ORDER BY occurrences DESC, triggered_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def set_status(trigger_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE tuning_triggers
        SET status = %s, reviewed_at = NOW()
        WHERE id = %s
    """, (status, trigger_id))
    conn.commit()
    cur.close()
    conn.close()


def run():
    print("\n" + "=" * 60)
    print("  TUNING TRIGGER REVIEW")
    print("=" * 60)

    pending = get_pending_triggers()
    if not pending:
        print("  No pending tuning triggers to review.\n")
        return

    print(f"  {len(pending)} pattern(s) awaiting your review.\n")

    for row in pending:
        root = row["root_cause"] or "unspecified"
        rule = _match_rule(root)

        print("-" * 60)
        print(f"Root cause     : '{root}'")
        print(f"Flagged        : {row['occurrences']} time(s)")
        print(f"Example venues : {(row['affected_venues'] or '')[:100]}")
        print(f"Detected on    : {str(row['triggered_at'])[:16]}")
        print(f"Dev note       : {row['recommendation']}")
        print(f"Would target   : {rule['scope']} "
              f"({'reasoning_agent.py prompt' if rule['scope']=='reasoning' else 'stakeholder_enrichment.py prompt' if rule['scope']=='stakeholder' else 'NOT an LLM prompt — code/data fix needed instead'})")
        if rule["instruction"]:
            print(f"Instruction    : {rule['instruction']}")

        choice = input("\n  Approve this rule? [y]es / [n]o-reject / [s]kip for now: ").strip().lower()

        if choice in ("y", "yes"):
            if rule["scope"] == "code_only":
                print("  ⚠️  This is a code_only pattern — approving it will NOT inject "
                      "any prompt instruction (there isn't one). It's just being "
                      "marked active for record-keeping; the actual fix still needs "
                      "to happen in code.")
            set_status(row["id"], "active")
            print(f"  ✅ Approved — will apply from the next pipeline run.")
        elif choice in ("n", "no"):
            set_status(row["id"], "rejected")
            print(f"  🚫 Rejected — will not be applied.")
        else:
            print(f"  ⏭  Skipped — still pending, ask again next time.")
        print()

    print("=" * 60)
    print("  Review complete.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run()