# agent-1/src/signal_schema.py
SIGNAL_SCHEMA = {
    "review_decline": bool,
    "review_rating_delta": float,
    "review_volume_decline": bool,
    "complaint_increase": bool,

    "renovation_needed": bool,
    "old_property": bool,
    "physical_condition_score": int,

    "franchise_loss": bool,
    "former_brand": str,
    "franchise_affiliated": bool,
    "brand_status": str,

    "cmbs_watchlist": bool,
    "cmbs_special_servicing": bool,
    "cmbs_delinquent": bool,

    "long_term_owner": bool,
    "ownership_length_years": int,

    "distress_score": int,
}