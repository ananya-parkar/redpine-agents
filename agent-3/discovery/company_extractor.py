# agent-3/discovery/company_extractor.py
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_companies_with_llm(content):

    if not content.strip():
        return []

    prompt = f"""
        Extract company names from the text below.

        Rules:
        - Return only company names.
        - Ignore cities.
        - Ignore rankings.
        - Ignore headings.
        - Ignore people.
        - Remove duplicates.

        Return valid JSON in this format:

        {{
            "companies": [
                {{
                    "company_name": "Publix"
                }}
            ]
        }}

        Text:

        {content}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    result = json.loads(response.choices[0].message.content)
    return result["companies"]