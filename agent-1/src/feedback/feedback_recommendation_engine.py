# agent-1/src/feedback/feedback_recommendation_engine.py
from openai import OpenAI
from decimal import Decimal
import json

client = OpenAI()

def clean_json(obj):

    if isinstance(obj, Decimal):
        return float(obj)

    raise TypeError

def generate_feedback_recommendation(reason, sample_leads):
    prompt = f"""
        You are a QA analyst for a hotel acquisition sourcing agent.

        Recurring feedback reason:
        {reason}

        Rejected leads:
        {json.dumps(sample_leads, indent=2, default=clean_json)}

        Determine:

        1. Common pattern
        2. Root cause
        3. Suggested pipeline change
        4. Suggested scoring change
        5. Suggested prompt change

        Return JSON:
        {{
        "root_cause":"",
        "pipeline_fix":"",
        "scoring_fix":"",
        "prompt_fix":""
        }}
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type":"json_object"},
        messages=[{"role":"user","content":prompt}])

    return json.loads(response.choices[0].message.content)