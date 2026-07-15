# agent-3/discovery/company_discovery.py
import json
import re

from anthropic.types import TextBlock
from llm.client import client
from utils.json_parser import parse_llm_json

from dotenv import load_dotenv
load_dotenv(override=True)


def discover_companies(
    geography,
    industry="Any",
    ownership_preference="Any",
    min_years=10,
    revenue_range="$10M-$50M",
    founder_age="60+",
    max_companies=10,
):
#    Discover acquisition candidates using Claude's web search.
    prompt = f"""
        You are an M&A sourcing analyst.
        Your task is to discover PRIVATE companies that could be acquisition targets.
        Search Criteria

        Geography:
        {geography}

        Industry:
        {industry}

        Ownership Preference:
        {ownership_preference}

        Minimum Years in Business:
        {min_years}

        Preferred Revenue:
        {revenue_range} (soft preference only)

        Revenue estimates for private companies are often unavailable or unreliable.
        Do NOT exclude a company simply because revenue cannot be determined.
        If revenue cannot be estimated from public information, return "Unknown".

        Preferred Founder Age:
        {founder_age}

        Search Priority:
        Use multiple public sources where possible before deciding a field is Unknown.

        1. Official company website
        2. Company About page
        3. Local business journals
        4. Chamber of Commerce
        5. State business registry
        6. Industry associations
        7. Trade publications
        8. Local news
        9. Press releases
        10. Google Maps

        Guidelines

        - Discover operating businesses only.
        - Prefer companies that are relatively unknown outside their local or regional markets.
        - Prioritize family-owned and founder-led businesses.
        - Prefer lower-middle-market companies.
        - Include manufacturers, industrial businesses, distributors, B2B service businesses and niche regional companies.
        - Maximize diversity across industries.
        - Avoid returning multiple companies from the same parent organization.
        - Do not invent companies.
        - If information cannot be verified:
            - Leave descriptive fields blank.
            - Use "Unknown" for fields that explicitly support Unknown values.
            - Never infer missing facts.

        Missing public information should not exclude an otherwise relevant company.
        Prioritize discovering legitimate operating businesses over returning perfectly enriched profiles.

        Exclude
        - Public companies
        - Venture Capital firms
        - Private Equity firms
        - Investment firms
        - Holding companies
        - Banks
        - Universities
        - Hospitals
        - Government organizations
        - Non-profits

        Return up to {max_companies} companies that best match the search criteria.

        Do not reject an otherwise suitable operating business simply because
        revenue, founder age, or ownership information cannot be determined.

        It is acceptable to return companies with incomplete enrichment if they
        appear to be legitimate lower-middle-market operating businesses.

        Return ONLY JSON.
        
        Do not include markdown.
        Do not include explanations.
        Do not include code fences.
        Do not include text before or after the JSON.

        Never omit keys.

        Return exactly:

        {{
            "companies": [
                {{
                    "company_name": "",
                    "city": "",
                    "state": "",
                    "industry": "",
                    "why_discovered": ""
                }}
            ]
        }}

    """

    last_exception = None

    for attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=6000,
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

            companies = result.get("companies", [])

            if not isinstance(companies, list):
                raise ValueError("'companies' is not a list.")

            break

        except Exception as e:

            last_exception = e
            print(f"[DISCOVERY RETRY {attempt + 1}] {e}")

    else:

        print("[CLAUDE DISCOVERY ERROR]", last_exception)

        return []

    # Remove duplicates

    seen = set()
    unique = []

    for company in companies:

        name = str(company.get("company_name", "")).strip()

        if not name:
            continue

        normalized = name.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique.append(company)

    return unique
