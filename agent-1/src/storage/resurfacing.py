# agent-1/src/storage/resurfacing.py
def should_resurface(existing_score, new_score):
    return abs(new_score - existing_score) > 10