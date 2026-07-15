# agent-3/collection/company_profile.py
import json
import re

from anthropic.types import TextBlock
from dotenv import load_dotenv

from llm.client import client
from utils.json_parser import parse_llm_json

load_dotenv(override=True)


def profile_company(company_name, state=""):
    # Performs end-to-end company research using Claude Web Search.
    prompt = f"""
        You are researching a private company for acquisition sourcing.
        Use live web search.

        Search Priority

        1. Official company website
        2. Company About page
        3. Leadership page
        4. Local business journals
        5. Chamber of Commerce
        6. Industry associations
        7. Local news
        8. Press releases
        9. Google Maps
        10. State business registry

        Company

        Name:
        {company_name}

        State:
        {state}

        Your objective is to determine whether this company appears to fit a lower-middle-market acquisition profile.

        Extract ONLY information supported by public sources.

        Never guess.

        Missing public information should reduce confidence, not eliminate the company from consideration.
        Use multiple public sources before returning Unknown.

        If a value cannot be verified:
        - Use "Unknown" for categorical fields.
        - Use an empty string for descriptive text fields.
        - Never invent information.

        Determine:

        1. Company description
        2. Industry
        3. Website
        4. Headquarters city
        5. Headquarters state
        6. Company type
           Possible values:
           Private
           Public
           Unknown
        7. Founded year

        8. Years in business
           Calculate from the founded year when possible.
           If the founded year is unknown, leave blank.
        
        9. Revenue estimate
           Estimate revenue only when supported by reliable public information.
           Private company revenue is frequently unavailable.
           
           If it cannot be verified:
           Return "Unknown".

           Never infer revenue from employee count, office size, company reputation or similar signals.

           Private company revenue is often unavailable.

           If you cannot verify it,
           return "Unknown".

           Do not guess.

        10. Founder name
        11. Founder-led
            Yes
            No
            Unknown

        12. Family-owned
            Yes
            No
            Unknown

        13. Founder age estimate
            Estimate founder age only when supported by reliable public information.

            Acceptable sources include:
            - executive biographies
            - interviews
            - leadership pages
            - press releases

            Otherwise return "Unknown".

            Never estimate age from photographs,
            graduation year,
            or career history.

        14. Ownership status
            Founder Owned
            Family Owned
            PE Backed
            Corporate Owned
            Unknown
        
        15. Ownership Tenure (Years)
        Only calculate if ownership dates are publicly supported.
        Otherwise return "Unknown".

        16. Evidence Summary
            List only factual evidence found during web search.

            Examples:

            - Founded in 1973.
            - Company states it is family-owned.
            - Founder Fred Keller currently serves as Chairman.
            - Leadership page identifies Christina Keller as CEO.

            Do not include opinions.
            Do not include reasoning.
            Do not include acquisition analysis.

            Each evidence item should correspond to one factual statement supported by one or more public sources.

        17. Extraction confidence
            High:
            Most important fields verified from multiple sources.

            Medium:
            Some important fields verified.

            Low:
            Limited publicly available information.

        18. Seller readiness signals

        19. Fit analysis

        20. Source URLs


        Return ONLY valid JSON.
        Do not include markdown.

        Return exactly:

        {{
            "company_description":"",
            "industry":"",
            "website":"",
            "city":"",
            "state":"",
            "company_type": "",
            "founded_year":"",
            "years_in_business":"",
            "revenue_estimate":"",
            "founder_name":"",
            "founder_led":"",
            "family_owned":"",
            "founder_age_estimate":"",
            "ownership_status":"",
            "ownership_tenure_years": "",
            "evidence_summary": [],
            "extraction_confidence": "",
            "fit_analysis":"",
            "seller_readiness_signals":[],
            "source_urls":[]
        }}
    """

    last_exception = None

    for attempt in range(2):

        try:

            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=5000,
                tools=[
                    {
                        "type": "web_search_20260318",
                        "name": "web_search",
                        "allowed_callers": ["direct"],
                        "max_uses": 8,
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            text = "".join(
                block.text
                for block in response.content
                if isinstance(block, TextBlock)
            )

            result = parse_llm_json(text)
            
            result.setdefault("company_type", "Unknown")
            result.setdefault("revenue_estimate", "Unknown")
            result.setdefault("founder_led", "Unknown")
            result.setdefault("family_owned", "Unknown")
            result.setdefault("founder_age_estimate", "Unknown")
            result.setdefault("ownership_status", "Unknown")
            result.setdefault("ownership_tenure_years", "Unknown")
            result.setdefault("evidence_summary", [])
            result.setdefault("extraction_confidence", "Low")
            result.setdefault("fit_analysis", "")
            result.setdefault("seller_readiness_signals", [])
            result.setdefault("source_urls", [])

            return result

        except Exception as e:

            last_exception = e
            print(f"[PROFILE RETRY {attempt+1}] {e}")

    print("[CLAUDE PROFILE ERROR]", last_exception)

    return {
        "company_description": "",
        "industry": "",
        "website": "",
        "city": "",
        "state": state,
        "company_type": "Unknown",
        "founded_year": "",
        "years_in_business": "",
        "revenue_estimate": "Unknown",
        "founder_name": "",
        "founder_led": "Unknown",

        "family_owned": "Unknown",

        "founder_age_estimate": "Unknown",

        "ownership_status": "Unknown",

        "ownership_tenure_years": "Unknown",

        "evidence_summary": [],

        "extraction_confidence": "Low",

        "fit_analysis": "",

        "seller_readiness_signals": [],

        "source_urls": []
    }