# agent-1/src/utils/exporters.py

import json
from pathlib import Path

def save_ai_entities(path: Path, rows):
    entities = []
    for row in rows:
        entity = row.get("entity", {}).copy()
        entity["final_lead_score"] = row.get("final_lead_score", 0)
        entity["rank"] = row.get("rank", 0)
        entity["lead_reason"] = row.get("lead_reason", "")
        
        if entity:
            entities.append(entity)
    path.write_text(
        json.dumps(entities, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )