# agent-1/src/storage/feedback_actions.py
from src.storage.postgres_storage import get_connection

def action_already_exists(reason):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM feedback_actions
        WHERE feedback_reason = %s
        LIMIT 1
        """,
        (reason,)
    )
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists

def create_feedback_action(
    reason,
    count,
    action
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 1
        FROM feedback_actions
        WHERE feedback_reason=%s
        """,
        (reason,)
    )

    if cur.fetchone():
        cur.close()
        conn.close()
        return

    cur.execute(
        """
        INSERT INTO feedback_actions
        (
            feedback_reason,
            trigger_count,
            action_taken
        )
        VALUES (%s,%s,%s)
        """,
        (
            reason,
            count,
            action
        )
    )

    conn.commit()
    cur.close()
    conn.close()