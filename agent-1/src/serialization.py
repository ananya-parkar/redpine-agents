# agent-1/src/serialization.py
from dataclasses import asdict

def serialize_entity(entity):
    return asdict(entity)