# agent-1/src/llm/schemas.py

LLM_REASONING_SCHEMA = {
    "distress_probability": float,
    "seller_fatigue_probability": float,
    "opportunity_score": int,
    "llm_star_rating": float,
    "confidence": str,
    "top_distress_signals": list,
    "investment_thesis": str,
    "recommended_action": str,
    "distress_summary": str,
}