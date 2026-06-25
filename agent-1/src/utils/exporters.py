# agent-1/src/utils/exporters.py
import json
import numpy as np

def json_serializer(obj):
    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.bool_):
        return bool(obj)

    return str(obj)

def save_ai_entities(file_path, entities):
    file_path.write_text(
        json.dumps(
            entities,
            indent=2,
            ensure_ascii=False,
            default=json_serializer
        ),
        encoding="utf-8"
    )