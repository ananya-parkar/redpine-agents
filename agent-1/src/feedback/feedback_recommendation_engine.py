# agent-1/src/feedback/feedback_recommendation_engine.py
from decimal import Decimal
import json
from anthropic import Anthropic
from src.core.config import ANTHROPIC_API_KEY

client = Anthropic(
    api_key=ANTHROPIC_API_KEY
)

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

    response = client.messages.create(
        model="claude-sonnet-5",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=1000
    )

    content = "".join(
        block.text
        for block in response.content
        if hasattr(block, "text")
    )

    return json.loads(content)
