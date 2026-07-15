import json
import time
from llm_client import call_llm_web_search_json
from reasoning_agent import compute_score, _lead_sort_key
from tuning_prompt import build_tuning_block
from db_writer import get_active_tuning_triggers

# ---------------------------------------------------
# STAKEHOLDER ENRICHMENT — Claude web search
#
# MIGRATED FROM SearchAPI → Claude's own built-in web search. No separate
# SearchAPI vendor key needed; Claude searches AND extracts stakeholders
# in one call using the same ANTHROPIC_API_KEY.
#
# WHY web search (not article text):
#   Articles cover the news event, not the full project team. We ask
#   Claude to specifically hunt for the project's:
#     - architect
#     - general contractor / construction company
#     - facilities director
#     - procurement officer
#     - developer / owner
#
# WEBSITE: Claude returns the org's official site URL only if it appears
#   in its search results — not guessed.
#
# EMAIL: returned ONLY if a concrete contact email actually appears in
#   the search results. NEVER fabricated (no info@domain.com guessing).
#
# Runs for ALL relevant leads (engage_now + monitor).
#
# FAILURE HANDLING: if the web-search call fails (returns nothing) for
# several CONSECUTIVE leads, we stop early rather than hammering a
# failing endpoint for the rest of the run.
# ---------------------------------------------------

# How many CONSECUTIVE leads can fail at the web-search call before we
# stop enrichment for the rest of this run.
MAX_CONSECUTIVE_FAILURES = 4

EXTRACT_PROMPT = """
You are a BD researcher finding the project team for a specific US
stadium/arena construction or renovation project.

Use the web_search tool to find the people and companies working on THIS
specific venue's project. Search for things like the venue's architect,
general contractor / construction manager, facilities director, developer,
owner, and procurement/capital-projects officials.

Extract ONLY people and companies that actually appear in your search
results for THIS venue. Do NOT invent names. Do NOT guess. If you cannot
find a real name/firm, return fewer (or zero) stakeholders — that is
correct and expected.

For contact_email: include an email address ONLY if a concrete address
actually appears in the search results for that organization. NEVER
fabricate or guess an email (e.g. do NOT invent "info@<domain>.com").
Leave it as "" if none is found.

For website: include the organization's official site URL ONLY if it
appears in your search results. Leave "" if not found.

If the input includes "need_capacity": true, ALSO find this venue's
planned/expected seating capacity from your search results and return it
as an integer in "venue_capacity". If you cannot find a specific number,
return 0. Never guess a precise number that isn't stated.

Return ONLY valid JSON:
{
  "venue_capacity": <integer seating capacity if need_capacity was true and
    a specific number was found in results, else 0>,
  "stakeholders": [
    {
      "name": <exact person or firm name from search results>,
      "type": <"Architect"|"GC"|"Developer"|"Owner"|"City Official"|"Facilities Director"|"Procurement"|"Other">,
      "organization": <company/org name if mentioned, else "">,
      "title": <job title if mentioned, else "">,
      "website": <official site URL if found in results, else "">,
      "contact_email": <concrete email from results, else "">,
      "relevance": <"high"|"medium"|"low">
    }
  ]
}

Rules:
- Only names/firms that appear in your search results for THIS venue
- Skip generic company names with no tie to this project
- Prioritize: Architects, GCs, Facilities Directors, Procurement officers
- Include firm names for Architect and GC even without a person name
""".strip()


# League-based fallback capacity — used ONLY for scoring when a planned
# venue has no capacity in Wikipedia AND web search couldn't find a
# specific number. These are rough typical sizes, not real data.
LEAGUE_DEFAULT_CAPACITY = {
    "NFL":  65000,
    "NCAA": 50000,
    "MLB":  40000,
    "MLS":  25000,
    "NBA":  18000,
    "NHL":  18000,
    "Convention Center": 20000,
}


def extract_stakeholders_web(lead: dict, tuning_block: str = "") -> tuple[list[dict] | None, int]:
    """
    Claude searches the web and extracts stakeholders for one lead. If the
    lead's capacity is missing (0/blank), it ALSO asks Claude to find the
    venue's planned capacity in the same search (no extra call).

    Returns:
      (stakeholders, capacity)
        stakeholders : list[dict] found (possibly empty), or None if the
                       web-search call itself failed (circuit breaker)
        capacity     : int capacity found via web search (0 if not found
                       or not requested)
    """
    venue = lead.get("venue_name", "")
    team  = (lead.get("team", "") or "").split(";")[0].strip()
    city  = lead.get("city", "")
    state = lead.get("state", "")

    # Only ask for capacity if we don't already have one.
    try:
        cur_cap = int(float(lead.get("capacity") or 0))
    except (TypeError, ValueError):
        cur_cap = 0
    need_capacity = cur_cap <= 0

    payload = {
        "venue_name":       venue,
        "team":             team,
        "city":             city,
        "state":            state,
        "league":           lead.get("league", ""),
        "project_summary":  lead.get("whats_happening", ""),
        "need_capacity":    need_capacity,
        "instruction": (
            f"Find the project team (architect, general contractor, "
            f"facilities director, developer, owner, procurement officials) "
            f"for the '{venue}' {team} stadium/arena project in {city}, "
            f"{state}. Search the web and extract only real, named people "
            f"and firms tied to this specific project."
            + (f" Also find the venue's planned seating capacity."
               if need_capacity else "")
        ),
    }
    user_content = json.dumps(payload, ensure_ascii=True)

    try:
        result = call_llm_web_search_json(
            system=EXTRACT_PROMPT + tuning_block,
            user_content=user_content,
            max_tokens=2000, temperature=0.0,
            max_uses=4,   # up to 4 searches per lead — bounds cost
        )
    except Exception as e:
        print(f"      [WEB-SEARCH ERROR] {e}", flush=True)
        return None, 0

    if not isinstance(result, dict):
        return None, 0

    # Parse capacity found via web search (0 if not found/not requested)
    found_cap = 0
    if need_capacity:
        try:
            found_cap = int(float(result.get("venue_capacity") or 0))
        except (TypeError, ValueError):
            found_cap = 0
        # sanity bound — ignore absurd values
        if not (1000 < found_cap < 250000):
            found_cap = 0

    stakes = result.get("stakeholders", [])
    # Keep the same filter as before: must have a name, drop low relevance.
    filtered = [s for s in stakes
                if s.get("name", "").strip()
                and s.get("relevance", "") != "low"]
    return filtered, found_cap


def enrich_stakeholders(all_leads: list[dict],
                        act_now:   list[dict]) -> tuple[list, list, list]:
    """
    Enrich stakeholders via Claude web search for engage_now + monitor
    leads. Returns updated all_leads, act_now, and flat stakeholder_rows.
    """
    to_enrich = [l for l in all_leads
                 if l.get("engagement") in ("engage_now", "monitor")]

    print(f"\n[STEP 4] Stakeholder enrichment via Claude web search "
          f"({len(to_enrich)} leads)...", flush=True)

    # Same tuning-trigger mechanism as before, scoped to "stakeholder".
    active_triggers = get_active_tuning_triggers()
    stakeholder_tuning_block = build_tuning_block(active_triggers, scope="stakeholder")
    if stakeholder_tuning_block:
        print(f"  [TUNING] Injecting {stakeholder_tuning_block.count('Pattern:')} "
              f"known false-positive pattern(s) into stakeholder prompt", flush=True)

    stakeholder_rows = []
    consecutive_failures = 0

    for i, lead in enumerate(to_enrich, 1):
        vname = lead.get("venue_name", "")
        eng   = lead.get("engagement", "")
        print(f"  [{i:02d}/{len(to_enrich)}] {vname[:40]} [{eng}]", flush=True)

        stakes, found_cap = extract_stakeholders_web(
            lead, tuning_block=stakeholder_tuning_block)

        # CIRCUIT BREAKER: None means the web-search call itself failed
        # (not "this lead has no stakeholders", which is an empty list).
        if stakes is None:
            consecutive_failures += 1
            print(f"      [FAIL] web search failed — "
                  f"{consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}", flush=True)
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                remaining = len(to_enrich) - i
                print(f"\n  [STOPPING] Web search failed "
                      f"{MAX_CONSECUTIVE_FAILURES} times in a row — "
                      f"skipping remaining {remaining} leads this run.", flush=True)
                break
            time.sleep(1.0)
            continue
        consecutive_failures = 0  # any real response resets this — even []

        # CAPACITY BACKFILL: if this lead had no capacity and web search
        # found one, fill it in AND recompute the score (which depends on
        # capacity). If web search found nothing, fall back to a rough
        # league-based default so the score isn't unfairly low — but only
        # use the default for SCORING, keep the displayed capacity honest.
        try:
            cur_cap = int(float(lead.get("capacity") or 0))
        except (TypeError, ValueError):
            cur_cap = 0
        if cur_cap <= 0:
            display_cap = found_cap  # real number from web (0 if none found)
            score_cap = found_cap or LEAGUE_DEFAULT_CAPACITY.get(
                lead.get("league", ""), 0)
            if display_cap > 0:
                lead["capacity"] = display_cap
                print(f"      [CAPACITY] found {display_cap:,} via web search", flush=True)
            elif score_cap > 0:
                print(f"      [CAPACITY] none found — using league default "
                      f"{score_cap:,} for scoring only", flush=True)
            # Recompute score with the better capacity (real or default).
            # Engagement/likelihood don't change here — they're derived from
            # tier, not capacity — so only the score needs refreshing.
            if score_cap > 0:
                new_score = compute_score(
                    lead.get("signal_tier") or 1,
                    score_cap,
                    lead.get("venue_status", "existing"),
                    lead.get("likelihood"),
                )
                old_score = lead.get("score")
                lead["score"] = new_score
                print(f"      [SCORE] {old_score} → {new_score} "
                      f"(capacity-adjusted)", flush=True)

        print(f"      → {len(stakes)} stakeholders found", flush=True)

        if stakes:
            lead["stakeholders_raw"] = json.dumps(stakes)
            for s in stakes:
                stakeholder_rows.append({
                    "venue_name":       vname,
                    "league":           lead.get("league", ""),
                    "team":             lead.get("team", ""),
                    "signal_tier":      lead.get("signal_tier"),
                    "engagement":       eng,
                    "stakeholder_name": s.get("name", ""),
                    "title":            s.get("title", ""),
                    "organization":     s.get("organization", ""),
                    "type":             s.get("type", ""),
                    "website":          s.get("website", ""),
                    "contact_email":    s.get("contact_email", ""),
                    "notes":            s.get("relevance", ""),
                })

        time.sleep(1.0)

    found_website = sum(1 for r in stakeholder_rows if r["website"])
    found_email   = sum(1 for r in stakeholder_rows if r["contact_email"])
    print(f"\n  Total stakeholders  : {len(stakeholder_rows)}", flush=True)
    print(f"  With website        : {found_website}/{len(stakeholder_rows)}", flush=True)
    print(f"  With email          : {found_email}/{len(stakeholder_rows)}", flush=True)

    # Capacity backfill above may have changed some scores, so re-sort and
    # re-rank both lists to keep the displayed order consistent with the
    # updated scores (same sort key / ranking scheme as reasoning_agent).
    all_leads.sort(key=_lead_sort_key)
    for i, r in enumerate(all_leads, 1):
        r["rank"] = i

    lead_map = {l["venue_name"]: l for l in all_leads}
    act_now  = [lead_map.get(l["venue_name"], l) for l in act_now]
    act_now.sort(key=_lead_sort_key)
    for i, r in enumerate(act_now, 1):
        r["act_now_rank"] = i

    return all_leads, act_now, stakeholder_rows