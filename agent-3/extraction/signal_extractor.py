# agent-3/extraction/signal_extractor.py
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_signals(raw_content):
    prompt = f"""
        You are extracting acquisition-relevant business signals.

        Extract information ONLY if explicitly supported
        by the provided content.

        Do not guess.

        Return JSON.

        Fields:

        - industry
        - state
        - company_type
        - founded_year
        - founder_name
        - founder_led
        - family_owned
        - founder_age_estimate
        - evidence

        Rules:

        - founder_led:
          Return "Yes" only if the founder is explicitly identified as a current CEO, President, Founder-CEO, Founder-President, Managing Director, or current executive.
          Do not assume founder-led based only on the founder being mentioned.
          If founder and current leadership are different people, return "No".
          Return "No" if there is explicit evidence that leadership is not founder-led.
          Otherwise return "Unknown".

        - family_owned:
          Return "Yes" only if there is explicit evidence that the business is family-owned, family-operated, multi-generation owned, or described as a family business.
          Return "No" only if there is explicit evidence that ownership is not family-owned.
          Otherwise return "Unknown".

        - company_type:
          Return one of:
            Private
            Public
            Unknown

          Only return Private or Public if explicitly stated in the content.
        
        - founder_age_estimate:
            Only provide if evidence exists.
            Otherwise return "Unknown".

        - evidence:
            List the exact facts that support the extraction.

        Return format:

        {{
            "industry": "",
            "state": "",
            "company_type": "",
            "founded_year": "",
            "founder_name": "",
            "founder_led": "",
            "family_owned": "",
            "founder_age_estimate": "",
            "evidence": [
                ""
            ]
        }}

        Content:

        {raw_content[:15000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}])

    return json.loads(response.choices[0].message.content)