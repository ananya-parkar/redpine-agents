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

        Use web search to verify information from authoritative public sources.

        Search priority:

        1. Official hotel website
        2. Official brand website
        3. Google Maps
        4. Hospitality publications
        5. Local news
        6. Press releases

        Ignore low-quality directory listings unless corroborated by another source.

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

        1. Current hotel brand.

        2. Previous hotel brand, if any.

        3. Whether the hotel has lost a major franchise
        (Marriott, Hilton, IHG, Wyndham, Choice, Hyatt, Best Western).

        4. If a franchise loss occurred,
        estimate the month/year when it occurred.

        5. Whether the hotel is now independently operated.

        6. Search for evidence of:

        - franchise termination
        - rebranding
        - management company change
        - temporary closure
        - permanent closure
        - reopening after renovation

        7. Summarize any recent operational distress reported publicly.

        You MUST return ONLY a valid JSON object.
        Do not include explanations.
        Do not include markdown.
        Do not include code fences.
        Do not include any text before or after the JSON.

        If a field cannot be verified from public sources, return an empty string for that field.
        Do not invent values.
        Do not guess.

        Never omit keys.

        Always return every field.

        {{
            "franchise_affiliated": true,
            "current_brand": "",
            "former_brand": "",
            "brand_status": "CURRENT",
            "franchise_loss_date": "",
            "franchise_confidence": "High",
            "franchise_evidence": "",
            "recent_distress_news": "",
            "ownership_context": ""
        }}
    """

    try:
        last_exception = None
        for attempt in range(2):
            try:
                response = client.messages.create(
                    model="claude-sonnet-5",
                    max_tokens=1800,
                    tools=[
                        {
                            "type": "web_search_20260318",
                            "name": "web_search",
                            "allowed_callers": ["direct"],
                            "max_uses": 5
                        }
                    ],
                    messages=[{"role": "user", "content": prompt}]
                )

                text = "".join(block.text for block in response.content if isinstance(block, TextBlock))
                match = re.search(r"\{.*\}", text, re.S)

                if not match:
                    raise ValueError("No JSON found in Claude response.")

                result = json.loads(match.group())
                break

            except Exception as e:
                last_exception = e
                print(
                    f"[CLAUDE RETRY {attempt + 1}] {e}",
                    flush=True
                )

        else:

            print("[CLAUDE WEB SEARCH ERROR]", last_exception)

            return {
                "franchise_affiliated": False,
                "current_brand": "",
                "former_brand": "",
                "brand_status": "NONE",
                "franchise_loss_date": "",
                "franchise_confidence": "Error",
                "franchise_evidence": str(last_exception),
                "recent_distress_news": "",
                "ownership_context": ""
            }

        for field in [
            "current_brand",
            "former_brand",
            "franchise_loss_date",
            "franchise_evidence",
            "recent_distress_news",
            "ownership_context",
        ]:
            value = result.get(field)

            if isinstance(value, str):
                normalized = value.strip().lower()

                if normalized in {
                    "none",
                    "none found",
                    "none identified",
                    "not applicable",
                    "n/a",
                    "null",
                    "unknown",
                    "unknown brand",
                    "not available",
                }:
                    result[field] = ""
                    continue

                if field in ["current_brand", "former_brand"]:
                    cleaned = (
                        value
                        .replace("(independent)", "")
                        .replace("- independent", "")
                        .replace("independent", "")
                        .strip(" -")
                        .strip()
                    )

                    result[field] = cleaned
        
        # ------------------------------
        # Normalize franchise output
        # ------------------------------

        brand_status = str(result.get("brand_status", "")).upper()
        result["brand_status"] = brand_status

        # Default
        result["franchise_affiliated"] = False

        if brand_status == "CURRENT" and result.get("current_brand"):
            result["franchise_affiliated"] = True

        return result

    except Exception as e:

        print("[CLAUDE WEB SEARCH ERROR]", e)

        return {
            "franchise_affiliated": False,
            "current_brand": "",
            "former_brand": "",
            "brand_status": "NONE",
            "franchise_loss_date": "",
            "franchise_confidence": "Error",
            "franchise_evidence": str(e),
            "recent_distress_news": "",
            "ownership_context": ""
        }