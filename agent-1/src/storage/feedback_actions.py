# agent-1/src/storage/feedback_actions.py
from psycopg2.extras import Json
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

def create_feedback_action(reason, count, action, recommendation_json=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO feedback_actions
        (
            feedback_reason,
            trigger_count,
            action_taken,
            recommendation_json
        )
        VALUES (%s,%s,%s,%s)

        ON CONFLICT (feedback_reason)
        DO UPDATE SET
            trigger_count = EXCLUDED.trigger_count,
            action_taken = EXCLUDED.action_taken,
            recommendation_json = EXCLUDED.recommendation_json
        """,
        (
            reason,
            count,
            action,
            Json(recommendation_json)
        )
    )

    conn.commit()
    cur.close()
    conn.close()
    
def get_existing_trigger_count(reason):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT trigger_count
        FROM feedback_actions
        WHERE feedback_reason=%s
        """,
        (reason,)
    )

    row = cur.fetchone()
    cur.close()
    conn.close()

    return row[0] if row else 0