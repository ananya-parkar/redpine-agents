# agent-3/extraction/signal_extractor.py
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

STATE_MAPPING = {
    "Florida": "FL",
    "Fla.": "FL"
}

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
        - ownership_status
        - evidence_summary
        - extraction_confidence

        Rules:

        - founder_led:
          Return "Yes" only if the founder currently serves as:
            - CEO
            - President
            - Founder-CEO
            - Founder-President
            - Managing Director
            - Owner-Operator

            Do not classify the following as founder-led:
            - Executive Chairman
            - Chairman
            - Board Member
            - Director
            - Advisor
            - Investor
          Do not assume founder-led based only on the founder being mentioned.
          If founder and current leadership are different people, return "No".
          Return "No" if there is explicit evidence that leadership is not founder-led.

          Ownership by a founder does not automatically imply family-owned.
          A company can be founder-led and not family-owned.
          
          Founder-led means the ORIGINAL founder currently serves in a qualifying leadership role.
          Do NOT classify as founder-led when:
          - a son, daughter, grandson, granddaughter or descendant leads the company

          Family leadership is not the same as founder-led.

          Example:
          Founded by Robert Beall
          Current CEO Matt Beall

          Return: Founder Led = No
        
         Otherwise return "Unknown".

        - family_owned:
            Return "Yes" only if ownership is explicitly described as:
                - family-owned
                - family-controlled
                - family-operated
                - multi-generation family ownership

            Do NOT classify a company as family-owned merely because:
            - family offices invest in it
            - family offices back it
            - family capital funds it
            - family office appears in ownership structure
            - the company mentions family values
            - the company refers to employees as family

            Family-owned requires evidence that ownership itself remains within a family.

            Historical family ownership is not sufficient.
            Return Yes only if there is evidence that the company is
            currently family-owned or family-controlled.

            A company that was family-owned decades ago but later
            acquired or institutionalized should not be classified
            as family-owned.

            Return "No" only if ownership is explicitly not family-owned.

            The following statements are NOT valid evidence:
            - family business culture
            - family values
            - family atmosphere
            - employees are family
            - founder still leads company

            These do not imply family ownership.

            Otherwise return "Unknown".

        - company_type:
          Return one of:
            Private
            Public
            Unknown

          Only return Private or Public if explicitly stated in the content.
        
        - founder_age_estimate:
            If a founder's age is not explicitly stated but there is enough evidence
            to estimate a range (for example founded company in 1981 and still CEO),
            return a conservative estimate.

            Examples:
            60-70
            70-80
            Unknown

            Do not invent exact ages.
        
        - ownership_status:
            Possible values:
            Founder Owned
            Family Owned
            PE Backed
            Corporate Owned
            Unknown

        - evidence_summary:
            List the exact facts that support the extraction.

            Examples:
            - Founded in 1981 by Reinhold Schmieding
            - Reinhold Schmieding currently serves as President
            - Company explicitly described as private
                
        - extraction_confidence:
            High: Multiple sources support the extraction.
            Medium: Some evidence exists but incomplete.
            Low: Weak or conflicting evidence.
        

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
            "evidence_summary": [
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

    result = json.loads(response.choices[0].message.content)

    state = result.get("state")
    if state in STATE_MAPPING:
        result["state"] = STATE_MAPPING[state]

    return result