# agent-3/discovery/universe_filter.py

import json
import os
import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

def load_filtered_universe(input_file):
    return pd.read_csv(input_file)

def classify_company(company_name):

    prompt = f"""
        You are helping build a universe of potential acquisition candidates.
        Your job is ONLY to classify whether a company should remain in the candidate universe for further investigation.

        Do NOT assume:
        - revenue
        - founder age
        - ownership structure
        - seller readiness

        Based only on publicly recognizable knowledge:
        
        KEEP if:
        - Appears to be a private business
        - Appears to be a legitimate operating company
        - Could reasonably be investigated further

        REMOVE if:
        - Public company
        - Government entity
        - University
        - Hospital
        - Non-profit

        - Venture Capital firm
        - Private Equity firm
        - Investment Firm
        - Asset Management Firm
        - Wealth Management Firm
        - Family Office
        - Holding Company
        - Search Fund
        - Acquisition Vehicle
        - Large public mega-corporation
        - Fortune-scale private enterprise
        - National mega-company
        - Enterprise clearly too large to fit a typical lower-middle-market acquisition target

        Strong Name Heuristics:
        If company name contains terms like:

        Capital
        Ventures
        Ventures LLC
        Partners
        Equity
        Fund
        Holdings
        Management
        Investments
        Family Office

        and appears to be an investment business,
        return REMOVE.

        Be aggressive in removing investment entities.
        False positives are preferred over keeping PE/VC firms.

        Return JSON only:
        {{
            "decision": "KEEP",
            "reason": "Private company"
        }}

        Allowed reasons:
        - Private company
        - Public company
        - Hospital
        - University
        - Government entity
        - Investment firm
        - Non-profit organization
        - Not a business
        - Large public corporation
        - Venture Capital firm
        - Private Equity firm
        - Investment firm
        - Holding company
        - Unknown

        Company:
        {company_name}

    """

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1000,
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ]
    )

    content = "".join(
        block.text
        for block in response.content
        if hasattr(block,"text")
    )

    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]

    if content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    result = json.loads(content)
    
    return result