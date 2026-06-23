# ---------------------------------------------------
# TUNING PROMPT BUILDER
# Reads active tuning triggers from DB and builds
# a negative-examples block to inject into LLM prompt.
# Called by reasoning_agent.py at the start of each run.
# ---------------------------------------------------

def build_tuning_block(triggers: list[dict]) -> str:
    """
    Converts DB tuning triggers into a prompt block like:

    KNOWN FALSE POSITIVE PATTERNS — AVOID THESE MISTAKES:
    - Root cause: 'wrong owner' (flagged 4 times)
      Venues affected: AT&T Stadium, SoFi Stadium...
      Instruction: Do NOT confidently name an owner unless explicitly
                   stated in the article. Mark as 'unverified'.
    """
    if not triggers:
        return ""

    INSTRUCTIONS = {
        "wrong owner":     "Do NOT confidently name an owner unless explicitly stated in the article. Mark stakeholder as 'unverified' if inferred.",
        "wrong venue":     "Double-check venue name matches exactly. Reject signals where venue name is ambiguous or similar to another.",
        "no construction": "Reject signals that mention venues without explicit construction, renovation, or expansion activity. General news is not a signal.",
        "old news":        "Check article date carefully. Reject signals older than 90 days unless they reference new funding or approvals.",
        "not our market":  "Only include venues in the stadium/arena/convention center category. Reject minor leagues and non-sports venues.",
        "duplicate":       "If you see the same project mentioned twice, keep only the most recent and specific signal.",
        "fake signal":     "Be sceptical of rumour-only articles with no named source, budget, or official confirmation.",
    }

    lines = [
        "\n\n--- KNOWN FALSE POSITIVE PATTERNS (learned from past feedback) ---",
        "The following mistakes have been flagged 3+ times by the human reviewer.",
        "Apply extra scrutiny when these patterns appear:\n",
    ]

    for t in triggers:
        root = (t.get("root_cause") or "unspecified").lower()
        count   = t.get("occurrences", 0)
        venues  = t.get("affected_venues", "")[:120]

        # Find matching instruction
        instruction = next(
            (v for k, v in INSTRUCTIONS.items() if k in root),
            f"Be extra careful about: {root}."
        )

        lines.append(f"• Pattern: '{root}' — flagged {count} times")
        lines.append(f"  Example venues: {venues}")
        lines.append(f"  Rule: {instruction}\n")

    lines.append("--- END OF FALSE POSITIVE PATTERNS ---\n")
    return "\n".join(lines)