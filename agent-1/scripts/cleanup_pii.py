# agent-1/scripts/cleanup_pii.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from src.storage.postgres_storage import get_connection
conn = get_connection()
cur = conn.cursor()

cur.execute("""
DELETE
FROM hotel_leads
WHERE created_at < NOW() - INTERVAL '12 months'
AND lead_status <> 'PURSUING'
""")

deleted = cur.rowcount

conn.commit()
cur.close()
conn.close()

print(
    f"[PII CLEANUP] Deleted {deleted} expired records",
    flush=True
)