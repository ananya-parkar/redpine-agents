# agent-1/src/analysis/signals.py

def build_signals(entity):
    scores = entity.heuristic_scores
    attom_age_flag = (str(entity.owner_data.get("is_older_than_20_years", "")).lower()== "yes")
        
    signals = {
        # Review trend signals
        "review_decline": scores.get("review_rating_delta", 0) <= -0.3,
        "review_rating_delta": scores.get("review_rating_delta", 0),
        "review_volume_decline": (scores.get("review_volume_change_pct", 0) <= -30),
        "complaint_increase": (scores.get("review_complaint_delta", 0)>= 0.5),
        "sentiment_decline": scores.get("sentiment_trend") == "Declining",
        "sentiment_trend": scores.get("sentiment_trend", "Stable"),
        "review_activity_trend": scores.get("review_activity_trend", "Stable"),
        "positive_reviews_recent": scores.get("positive_reviews_recent", 0),
        "negative_reviews_recent": scores.get("negative_reviews_recent", 0),
        "positive_reviews_prior": scores.get("positive_reviews_prior", 0),
        "negative_reviews_prior": scores.get("negative_reviews_prior", 0),

        # Physical condition
        "renovation_needed": scores.get("renovation_needed", False),
        "old_property": attom_age_flag,
        "physical_condition_score": scores.get("physical_condition_score", 0),

        # Franchise signals
        "franchise_loss": entity.franchise_data.get("brand_status") == "FORMER",
        "former_brand": entity.franchise_data.get("former_brand", ""),
        "franchise_affiliated":entity.franchise_data.get("franchise_affiliated", False),
        "current_brand": entity.franchise_data.get("current_brand", ""),
        "brand_status": entity.franchise_data.get("brand_status", "NONE"),

        # CMBS signals
        "cmbs_watchlist": entity.cmbs_data.get("cmbs_watchlist_flag", False),
        "cmbs_special_servicing": entity.cmbs_data.get("cmbs_special_servicing_flag", False),
        "cmbs_delinquent": entity.cmbs_data.get("cmbs_delinquency_flag", False),

        # Ownership signals
        "long_term_owner":
            (
                int(entity.owner_data.get("ownership_length_years", 0)) >= 10
                if str(entity.owner_data.get("ownership_length_years", "")).isdigit()
                else False
            ),

        "ownership_length_years": entity.owner_data.get("ownership_length_years", 0),
        "room_count": entity.owner_data.get("room_count", 0),

        # Final heuristic score
        "distress_score": scores.get("distress_score", 0),
    }

    return signals