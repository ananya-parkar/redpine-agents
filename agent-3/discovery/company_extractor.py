# agent-3/discovery/company_extractor.py
import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from utils.json_parser import parse_llm_json

load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)
def extract_companies_with_llm(content):

    if not content.strip():
        return []

    prompt = f"""
        Extract only operating businesses.
        Do NOT extract:
        - Venture Capital firms
        - Private Equity firms
        - Investment firms
        - Family offices
        - Holding companies
        - Search funds
        - Acquisition vehicles
        - Banks
        - Universities
        - Hospitals
        - Government entities

        Only extract actual operating businesses that sell products or services.

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

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4000,
        thinking={"type": "disabled"},
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = "".join(
        block.text
        for block in response.content
        if hasattr(block, "text")
    ).strip()

    # Remove Markdown code fences if Claude added them
    if content.startswith("```"):
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

    content = content.strip()
    # Remove markdown fences if present
    if content.startswith("```json"):
        content = content.replace("```json", "", 1)

    if content.startswith("```"):
        content = content.replace("```", "", 1)

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    # Keep only the first JSON object
    start = content.find("{")
    end = content.rfind("}")

    content = content[start:end+1]

    try:
        result = parse_llm_json(content)
    except (json.JSONDecodeError, ValueError):
        return {
            "decision": "KEEP",
            "reason": "Unknown"
        }