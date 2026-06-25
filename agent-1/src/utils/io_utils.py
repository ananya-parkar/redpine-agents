# agent-1/src/utils/io_utils.py
import json
from pathlib import Path
from typing import List, Dict
import numpy as np

def parse_locations(file_path: Path) -> List[Dict]:
    rows = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [x.strip() for x in line.split("|")]
        if len(parts) < 2:
            raise ValueError(f"Invalid input line: {line}")

        row = {
            "location": parts[0],
            "radius_miles": float(parts[1])
        }

        if len(parts) >= 3 and parts[2]:
            row["min_rooms"] = parts[2]
        if len(parts) >= 4 and parts[3]:
            row["max_rooms"] = parts[3]
        if len(parts) >= 5 and parts[4]:
            row["year_built_range"] = parts[4]
        if len(parts) >= 6 and parts[5]:
            row["price_tier"] = parts[5]

        rows.append(row)
    return rows

def json_converter(obj):
    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    return str(obj)


def save_json(data, file_path):
    file_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
            default=json_converter
        ),
        encoding="utf-8"
    )