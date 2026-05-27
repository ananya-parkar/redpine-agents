# agent-1/src/llm/reasoning_agent.py
import json
from src.llm.client import client
from src.llm.prompts import (
    SYSTEM_PROMPT,
    HOTEL_ANALYSIS_PROMPT
)
from src.llm.schemas import LLM_REASONING_SCHEMA

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
        "llm_star_rating": 0.0,
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
    prompt = HOTEL_ANALYSIS_PROMPT.format(
        hotel_data={
            "hotel_name": entity.hotel_name,
            "address": entity.address,
            "rating": entity.rating,
            "user_rating_count": entity.user_rating_count,
        },
        signals=entity.signals,
        heuristic_scores=entity.heuristic_scores,
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
        # print(
        #     f"[LLM RAW RESPONSE] {content}",
        #     flush=True
        # )
        # content = content.strip()

        # if content.startswith("```json"):
        #     content = (
        #         content
        #         .replace("```json", "")
        #         .replace("```", "")
        #         .strip()
        #     )

        # start = content.find("{")
        # end = content.rfind("}")

        # if start != -1 and end != -1:
        #     content = content[start:end+1]
        
        parsed = json.loads(content)            
        print(f"[LLM] Parsed response: {parsed}", flush=True)
        validated = validate_llm_response(parsed)
        return validated
    
    except Exception as e:
        print(f"[LLM ERROR] {str(e)}",flush=True)

        return default_failed_response(str(e))
                