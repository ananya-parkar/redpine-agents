# agent-1/src/final_scoring.py

def calculate_final_lead_score(entity):
    score = 0

    heuristic = entity.heuristic_scores
    llm = entity.llm_analysis
    signals = entity.signals

    # Base heuristic distress
    score += heuristic.get("distress_score", 0) * 4

    # LLM opportunity weighting
    score += llm.get("opportunity_score", 0) * 0.3

    # Franchise distress
    if signals.get("franchise_affiliated"):
        score += 5

    if signals.get("franchise_loss"):
        score += 20

    # CMBS distress
    if signals.get("cmbs_special_servicing"):
        score += 25

    if signals.get("cmbs_delinquent"):
        score += 20

    if signals.get("cmbs_watchlist"):
        score += 10

    # Owner fatigue
    if signals.get("long_term_owner"):
        score += 10

    # Operational decline
    if signals.get("review_decline"):
        score += 10

    if signals.get("complaint_increase"):
        score += 10

    # Physical condition
    if signals.get("old_property"):
        score += 5

    if signals.get("renovation_needed"):
        score += 10

    # Normalize to 100
    score = min(round(score, 2), 100)

    return score