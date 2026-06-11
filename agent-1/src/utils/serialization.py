# agent-1/src/utils/serialization.py
from dataclasses import asdict

def serialize_entity(entity):
    return asdict(entity)