# ---------------------------------------------------
# TUNING PROMPT BUILDER
#
# Reads active tuning triggers from DB and builds a negative-examples
# block to inject into the relevant LLM prompt.
#
# IMPORTANT — not every root cause is something a prompt can fix.
# Some feedback is about fields the LLM never touches at all:
#   - venue capacity/owner/city/state/year come from Wikipedia
#     (pd.read_html) and Wikidata in venue_fetcher.py — ZERO LLM
#     involvement for these specific fields. No prompt tweak can
#     change a Wikidata-sourced value.
#   - stakeholder Owner/Architect/GC *names* come from a DIFFERENT
#     LLM call — stakeholder_enrichment.py's EXTRACT_PROMPT, not
#     reasoning_agent.py's BATCH_PROMPT/DEEP_PROMPT.
#
# Each root cause below is tagged with WHICH prompt (if any) it
# should be injected into, so we never waste tokens on an instruction
# that has no chance of changing behavior, and so an instruction
# meant for one LLM call doesn't end up in the wrong one.
# ---------------------------------------------------

# scope:
#   "reasoning"   → inject into reasoning_agent.py's BATCH_PROMPT/DEEP_PROMPT
#                   (relevance, tier assignment, evidence wording)
#   "stakeholder" → inject into stakeholder_enrichment.py's EXTRACT_PROMPT
#                   (stakeholder name/type/owner extraction — a SEPARATE
#                   LLM call from reasoning_agent.py)
#   "code_only"   → NOT an LLM issue. The field comes from Wikipedia/
#                   Wikidata/regex matching with no LLM involvement.
#                   No prompt injection happens for these — they stay
#                   logged in tuning_triggers.txt as a developer-facing
#                   alert only (see feedback_reader.py).
# Explicit DENY-list — root causes we are SURE the LLM has zero
# control over, because the field comes from Wikipedia/Wikidata table
# parsing in venue_fetcher.py, or from deterministic code logic, with
# no LLM call touching it at all. Keep this list SMALL and CURATED —
# anything not explicitly listed here falls through to the default
# "reasoning" scope below, since most fields (tier, likelihood, score,
# evidence wording, relevance, engagement, project type) ARE genuine
# LLM judgment calls, even ones we didn't anticipate the exact wording
# for (e.g. "wrong likelihood", "score too high", "tier should be
# lower" — none of these need their own dictionary entry to work).
CODE_ONLY_KEYWORDS = {
    "duplicate",      # main.py's exact (venue, headline) key match
    "wrong capacity",  # Wikipedia table parsing, venue_fetcher.py
    "wrong city",      # Wikipedia table parsing, venue_fetcher.py
    "wrong state",     # Wikipedia table parsing, venue_fetcher.py
    "wrong year",      # Wikipedia table parsing, venue_fetcher.py
}

# Specific, well-understood patterns get a TAILORED instruction.
# Anything else still reaches the LLM via the generic fallback in
# _match_rule() below — it just gets a more generic caution instead
# of a hand-written one.
TUNING_RULES = {
    "wrong owner": {
        "scope": "stakeholder",
        "instruction": ("Do NOT confidently name an owner/stakeholder unless "
                         "explicitly stated in the search results provided. "
                         "Mark relevance as 'low' if the name is inferred "
                         "rather than directly stated."),
    },
    "wrong venue": {
        "scope": "reasoning",
        "instruction": ("Double-check the article is unambiguously about THIS "
                         "exact venue, not a similarly-named one nearby. If in "
                         "doubt, set venue_confirmed=false rather than guessing."),
    },
    "no construction": {
        "scope": "reasoning",
        "instruction": ("Reject signals that mention a venue without explicit "
                         "construction, renovation, funding, or expansion "
                         "activity. General team/event news is not a signal."),
    },
    "old news": {
        "scope": "reasoning",
        "instruction": ("Check the published date carefully. Treat articles "
                         "older than 90 days as lower confidence unless they "
                         "describe NEW funding/approval, not a historical event."),
    },
    "not our market": {
        "scope": "reasoning",
        "instruction": ("Only include venues in the stadium/arena/convention "
                         "center category. Reject minor-league or non-sports "
                         "venues even if construction-related."),
    },
    "fake signal": {
        "scope": "reasoning",
        "instruction": ("Be skeptical of rumor-only articles with no named "
                         "source, budget figure, or official confirmation. "
                         "Use Tier 1 (lowest confidence) for these, never higher."),
    },
    "wrong tier": {
        "scope": "reasoning",
        "instruction": ("Re-verify the tier against the EVIDENCE-BASED TIER "
                         "RULE — use the stage explicitly stated in the "
                         "article, never an assumption. Common mistake: "
                         "'funding approved' language is Tier 2, not Tier 1."),
    },
    "wrong likelihood": {
        "scope": "reasoning",
        "instruction": ("Base the likelihood score strictly on how concrete "
                         "and specific the article's claims are — vague or "
                         "speculative language should score lower, not higher."),
    },
    "wrong score": {
        "scope": "reasoning",
        "instruction": ("Follow the SCORING FORMULA exactly as specified — "
                         "do not adjust the score based on venue fame or size "
                         "beyond the stated capacity bonus rules."),
    },
}


def _match_rule(root_cause: str) -> dict:
    """
    Returns a rule dict for the given root cause. Known patterns get
    their hand-written instruction from TUNING_RULES. Known non-LLM
    fields get scope="code_only" (no instruction is ever built for
    these). Anything else — including feedback wording we didn't
    anticipate — defaults to scope="reasoning" with a generic caution,
    so it still reaches the LLM rather than being silently dropped.
    """
    rc_lower = (root_cause or "").lower()

    for keyword in CODE_ONLY_KEYWORDS:
        if keyword in rc_lower:
            return {"scope": "code_only", "instruction": None}

    for keyword, rule in TUNING_RULES.items():
        if keyword in rc_lower:
            return rule

    # Unmapped — assume it's an LLM-judgment issue (tier/score/
    # likelihood/evidence-wording/relevance are all far more common
    # feedback topics than genuinely code-only ones) and forward a
    # generic instruction rather than silently dropping it.
    return {
        "scope": "reasoning",
        "instruction": (f"Re-verify carefully: human reviewers have flagged "
                         f"'{root_cause}' as a recurring mistake. Base your "
                         f"answer strictly on what the article explicitly "
                         f"states, not assumption."),
    }


def build_tuning_block(triggers: list[dict], scope: str) -> str:
    """
    Builds a prompt block containing ONLY triggers whose root cause
    maps to the given scope ("reasoning" or "stakeholder"). Triggers
    that map to "code_only" are skipped here entirely — those were
    already written to tuning_triggers.txt by feedback_reader.py for
    a developer to fix in code; no prompt instruction can act on them.
    """
    if not triggers:
        return ""

    applicable = []
    for t in triggers:
        root = t.get("root_cause") or "unspecified"
        rule = _match_rule(root)
        if rule["scope"] == scope and rule["instruction"]:
            applicable.append((t, rule))

    if not applicable:
        return ""

    lines = [
        "\n\n--- KNOWN FALSE POSITIVE PATTERNS (learned from past feedback) ---",
        "The following mistakes have been flagged 3+ times by the human reviewer.",
        "Apply extra scrutiny when these patterns appear:\n",
    ]
    for t, rule in applicable:
        root   = (t.get("root_cause") or "unspecified").lower()
        count  = t.get("occurrences", 0)
        venues = (t.get("affected_venues") or "")[:120]
        lines.append(f"• Pattern: '{root}' — flagged {count} times")
        lines.append(f"  Example venues: {venues}")
        lines.append(f"  Rule: {rule['instruction']}\n")
    lines.append("--- END OF FALSE POSITIVE PATTERNS ---\n")
    return "\n".join(lines)