# agent-1/scripts/update_lead_status.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from src.storage.postgres_storage import update_lead_status

address = input("Address: ")
status = input(
    "Status (NEW/PURSUING/PASSED/MONITORING): "
)

update_lead_status(address, status)

print("Updated successfully")