# agent-3/reasoning.py
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
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_rationale(row):
    """
    row: dict-like (a pandas Series or dict) with the candidate's
    structured fields + Evidence string.

    Returns dict with:
        why_selected      - 2-3 sentence explanation
        evidence_summary  - short summary of the supporting facts
        one_line_reason   - single line for the daily email digest
    """
    evidence = row.get("Evidence", "") or "No additional evidence captured."

    prompt = f"""
        You are writing a rationale for why a company appears on an
        acquisition target list. Base your reasoning ONLY on the data
        given below. Do not invent facts not present here.

        Company Name: {row.get("Company Name", "")}
        State: {row.get("State", "")}
        Industry: {row.get("Industry", "")}
        Founded Year: {row.get("Founded Year", "")}
        Years in Business: {row.get("Years in Business", "")}
        Founder Name: {row.get("Founder Name", "")}
        Founder Led: {row.get("Founder Led", "")}
        Family Owned: {row.get("Family Owned", "")}
        Founder Age Estimate: {row.get("Founder Age Estimate", "")}
        Seller Readiness Score: {row.get("Seller Readiness Score", "")}
        Evidence: {evidence}

        Write:
        1. why_selected: 2-3 sentences explaining why this company is a
           strong acquisition target, grounded in the fields above.
        2. evidence_summary: 1-2 sentences summarizing the concrete
           evidence that supports the selection (cite specifics from
           Evidence where available; otherwise note evidence is limited).
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

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )

    return json.loads(response.choices[0].message.content)


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
        enriched_row["Why Selected"] = rationale.get("why_selected", "")
        enriched_row["Evidence Summary"] = rationale.get("evidence_summary", "")
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

    df = pd.read_csv(deduped_file)

    if df.empty:
        print("No new candidates to reason about (deduplicated_candidates.csv is empty).")
        df.to_csv(output_file, index=False)
        return df

    enriched_df = add_rationale_to_candidates(df)
    enriched_df.to_csv(output_file, index=False)
    print(f"Saved {len(enriched_df)} rows with rationale -> {output_file}")

    return enriched_df