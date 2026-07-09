# agent-1/src/analysis/ranking_engine.py

def calculate_final_lead_score(entity):
    score = 0

    heuristic = entity.heuristic_scores
    llm = entity.llm_analysis
    signals = entity.signals

    # Base heuristic distress
    heuristic_score = min(heuristic.get("distress_score", 0) * 4, 100)
    llm_score = llm.get("opportunity_score", 0)
    score += (heuristic_score * 0.6 + llm_score * 0.4)
    
    # Franchise distress
    if signals.get("franchise_affiliated"):
        score += 5

    if (
        signals.get("franchise_loss")
        or signals.get("brand_status") == "FORMER"
    ):
        score += 20

    # CMBS distress
    # if signals.get("cmbs_special_servicing"):
    #     score += 5

    # if signals.get("cmbs_delinquent"):
    #     score += 3

    # if signals.get("cmbs_watchlist"):
    #     score += 2

    # Owner fatigue
    if signals.get("long_term_owner"):
        score += 15

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

    print(
            f"""
        [SCORE DEBUG] {entity.hotel_name}

        distress_score={heuristic.get('distress_score', 0)}
        opportunity_score={llm.get('opportunity_score', 0)}

        franchise_affiliated={signals.get('franchise_affiliated')}
        brand_status={signals.get('brand_status')}
        franchise_loss={signals.get('franchise_loss')}

        long_term_owner={signals.get('long_term_owner')}
        review_decline={signals.get('review_decline')}
        complaint_increase={signals.get('complaint_increase')}
        old_property={signals.get('old_property')}
        renovation_needed={signals.get('renovation_needed')}

        FINAL={score}
        """,
            flush=True
        )

    return score