# agent-3/discovery/universe_filter.py

import json
import os
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(response.choices[0].message.content)
    return result