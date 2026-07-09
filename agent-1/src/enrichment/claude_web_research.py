# agent-1/src/enrichment/claude_web_research.py
import json
import re
from anthropic.types import TextBlock
from src.llm.client import client


def research_hotel(
    hotel_name,
    address="",
    reviews=None,
    rating=None,
    review_count=None,
):

    review_text = ""

    if reviews:

        snippets = []

        for review in reviews[:10]:

            text = review.get("text", {})

            if isinstance(text, dict):
                snippets.append(text.get("text", ""))

            else:
                snippets.append(str(text))

        review_text = "\n".join(snippets)

    prompt = f"""
You are researching a hotel using live web search.

Use web search to gather the latest publicly available information.

Prefer:
- Official hotel website
- Official brand website
- Google Maps
- Recent news
- Hospitality publications
- Public business listings

Ignore low-quality directory listings unless corroborated.

Hotel

Name:
{hotel_name}

Address:
{address}

Google Rating:
{rating}

Review Count:
{review_count}

Recent Google Reviews:
{review_text}

Determine:

1. Current hotel brand
2. Previous hotel brand
3. Whether the hotel lost a franchise
4. Whether it is independently operated
5. Recent operational issues
6. Recent financial/distress indicators
7. Confidence (High / Medium / Low)

Return ONLY valid JSON.

{{
    "franchise_affiliated": true,
    "current_brand": "",
    "former_brand": "",
    "brand_status": "CURRENT",
    "franchise_confidence": "High",
    "franchise_evidence": "",
    "recent_distress_news": "",
    "ownership_context": ""
}}
"""

    try:

        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1200,
            tools=[
                {
                    "type": "web_search_20260318",
                    "name": "web_search",
                    "allowed_callers": ["direct"],
                    "max_uses": 3
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        text = "".join(
            block.text
            for block in response.content
            if isinstance(block, TextBlock)
        )

        match = re.search(r"\{.*\}", text, re.S)

        if not match:
            raise ValueError("No JSON found in Claude response.")

        return json.loads(match.group())

    except Exception as e:

        print("[CLAUDE WEB SEARCH ERROR]", e)

        return {
            "franchise_affiliated": False,
            "current_brand": "",
            "former_brand": "",
            "brand_status": "NONE",
            "franchise_confidence": "Error",
            "franchise_evidence": str(e),
            "recent_distress_news": "",
            "ownership_context": ""
        }