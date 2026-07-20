"""
Layer 6 — LLM Reasoning Layer

Per spec:
- Generate human-readable rationale
- Why this company is a strong target
- Key evidence summary
- One-line reason for digest

Input:  deduplicated_candidates.csv (output of Layer 5)
Output: candidates_with_rationale.csv (adds Why Selected, Evidence Summary,
        One-line Reason columns)
"""

import os
import json
import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)


def generate_rationale(row):
    """
    row: dict-like (a pandas Series or dict) with the candidate's
    structured fields + Evidence string.

    Returns dict with:
        why_selected      - 2-3 sentence neutral summary (not a verdict)
        evidence_summary  - short summary of the supporting facts
        one_line_reason   - single line for the daily email digest
    """
    evidence = (row.get("Evidence Summary", "") or "No additional evidence captured.")
    why_discovered = (row.get("Why Discovered", "") or "Not specified.")
    fit_analysis = (row.get("Fit Analysis", "") or "Not specified.")

    prompt = f"""
        You are summarizing a company that surfaced during acquisition-target
        discovery. This is a SOURCING list, not a verdict on quality - the
        client wants to know what the company is and why it turned up, not
        whether an algorithm judged it a "good" target. Do not write as if
        you are recommending or endorsing the company. Base your summary
        ONLY on the data given below. Do not invent facts not present here.

        Company Name: {row.get("Company Name", "")}
        City: {row.get("City", "")}
        State: {row.get("State", "")}
        Industry: {row.get("Industry", "")}
        Why Discovered: {why_discovered}
        Fit Analysis: {fit_analysis}
        Founded Year: {row.get("Founded Year", "")}
        Years in Business: {row.get("Years in Business", "")}
        Founder Name: {row.get("Founder Name", "")}
        Founder Led: {row.get("Founder Led", "")}
        Family Owned: {row.get("Family Owned", "")}
        Founder Age Estimate: {row.get("Founder Age Estimate", "")}
        Evidence Summary: {evidence}

        Write:
        1. why_selected: 2-3 sentences describing what this company is and
           why it surfaced in this search, grounded in the fields above.
           Neutral, factual tone - not a sales pitch or recommendation.
        2. evidence_summary: 1-2 sentences summarizing the concrete
           evidence found (cite specifics from Evidence Summary where
           available; otherwise note evidence is limited).
        3. one_line_reason: a single short sentence (under 20 words)
           suitable for a daily email digest line item.

        If a field is "Unknown" or missing, do not pretend to know it -
        acknowledge the gap rather than guessing.

        Return JSON only:
        {{
            "why_selected": "",
            "evidence_summary": "",
            "one_line_reason": ""
        }}
    """

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1500,
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
        if hasattr(block, "text")
    ).strip()

    # Remove markdown fences
    if content.startswith("```json"):
        content = content[7:]

    if content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    # If Claude writes a sentence before the JSON,
    # keep only the JSON object.
    start = content.find("{")
    end = content.rfind("}")

    if start != -1 and end != -1:
        content = content[start:end+1]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "why_selected": "",
            "evidence_summary": "",
            "one_line_reason": ""
        }

def add_rationale_to_candidates(df):
    """
    Takes the deduplicated candidates DataFrame and returns a new
    DataFrame with Why Selected, Evidence Summary, One-line Reason
    columns appended.
    """
    rationale_rows = []

    for _, row in df.iterrows():
        company_name = row.get("Company Name", "Unknown")
        print(f"Generating rationale: {company_name}")

        rationale = generate_rationale(row)

        enriched_row = row.to_dict()
        enriched_row["Raw Evidence Summary"] = enriched_row.get("Evidence Summary", "")  # preserve original before overwrite
        enriched_row["Why Selected"] = rationale.get("why_selected", "")
        enriched_row["Evidence Summary"] = rationale.get("evidence_summary", "")  # LLM's rewritten version
        enriched_row["One-line Reason"] = rationale.get("one_line_reason", "")

        rationale_rows.append(enriched_row)

    print(f"\nGenerated rationale for {len(rationale_rows)} companies")
    return pd.DataFrame(rationale_rows)


def run_reasoning(deduped_file, output_file):
    """
    Full Layer 6 entry point.

    deduped_file: path to deduplicated_candidates.csv
    output_file:  path to write candidates_with_rationale.csv
    """
    print("\nRunning LLM Reasoning Layer...\n")

    try:
        df = pd.read_csv(deduped_file)
    except pd.errors.EmptyDataError:
        print(f"Deduplicated candidates file is empty: {deduped_file}")
        df = pd.DataFrame()

    if df.empty:
        print("No new candidates to reason about (deduplicated_candidates.csv is empty).")
        df.to_csv(output_file, index=False)
        return df

    enriched_df = add_rationale_to_candidates(df)
    enriched_df.to_csv(output_file, index=False)
    print(f"Saved {len(enriched_df)} rows with rationale -> {output_file}")

    return enriched_df