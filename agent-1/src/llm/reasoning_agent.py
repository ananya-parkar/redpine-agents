# agent-1/src/llm/reasoning_agent.py
import json
from src.llm.client import client
from src.llm.prompts import (
    SYSTEM_PROMPT,
    HOTEL_ANALYSIS_PROMPT
)
from src.llm.schemas import LLM_REASONING_SCHEMA
from src.storage.postgres_storage import get_feedback_recommendations

def validate_llm_response(parsed: dict):

    defaults = {
        "distress_probability": 0.0,
        "seller_fatigue_probability": 0.0,
        "opportunity_score": 0,
        "confidence": "LOW",
        "top_distress_signals": [],
        "investment_thesis": "",
        "recommended_action": "Monitor",
        "distress_summary": "",
        "review_summary": "",
        "llm_star_rating": 2.0,
    }

    for key, value in defaults.items():
        if key not in parsed:
            parsed[key] = value

    return parsed

def default_failed_response(error_message: str):
    return {
        "distress_probability": 0.0,
        "seller_fatigue_probability": 0.0,
        "opportunity_score": 0,
        "confidence": "LOW",
        "top_distress_signals": [],
        "investment_thesis": "LLM analysis failed",
        "recommended_action": "Monitor",
        "distress_summary": error_message,
        "review_summary": "",
        "llm_star_rating": 0.0,
        "error": True
    }

def analyze_hotel(entity):
    recommendations = get_feedback_recommendations()
    feedback_text = "\n".join([
        (
            f"Reason: {row['feedback_reason']}\n"
            f"Prompt Guidance: "
            f"{row['recommendation_json'].get('prompt_fix','')}"
        )for row in recommendations])

    

    prompt = HOTEL_ANALYSIS_PROMPT.format(
        hotel_data={
            "hotel_name": entity.hotel_name,
            "address": entity.address,
            "rating": entity.rating,
            "user_rating_count": entity.user_rating_count,
        },
        signals=entity.signals,
        heuristic_scores=entity.heuristic_scores,
        feedback_patterns=feedback_text
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            # model="grok-3-mini",
            response_format={"type": "json_object"},
            timeout=60,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content
        
        parsed = json.loads(content)
        if ("acquisition_attractiveness_star_rating" in parsed and "llm_star_rating" not in parsed):
            parsed["llm_star_rating"] = parsed["acquisition_attractiveness_star_rating"]

        if ("star_rating" in parsed and "llm_star_rating" not in parsed):
            parsed["llm_star_rating"] = parsed["star_rating"]
        
        if ("recommended_acquisition_strategy" in parsed and "recommended_action" not in parsed):
            parsed["recommended_action"] = parsed["recommended_acquisition_strategy"]

        if ("acquisition_strategy" in parsed and "recommended_action" not in parsed):
            parsed["recommended_action"] = parsed["acquisition_strategy"]
        
        print(f"[LLM] Parsed response: {parsed}", flush=True)       
        validated = validate_llm_response(parsed)
        if (validated.get("llm_star_rating", 0) == 0 and validated.get("opportunity_score", 0) > 0):
            validated["llm_star_rating"] = round(validated["opportunity_score"] / 20, 1)
        
        return validated
            
    except Exception as e:
        print(f"[LLM ERROR] {str(e)}",flush=True)

        return default_failed_response(str(e))
                