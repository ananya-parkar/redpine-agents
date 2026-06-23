import re
import json
import time
from datetime import datetime
from openai import OpenAI
from tavily import TavilyClient
from config import OPENAI_API_KEY, OPENAI_MODEL, TAVILY_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# Set to False to skip Stage 3 entirely (e.g. to save cost on a test run,
# or if TAVILY_API_KEY isn't configured yet).
ENABLE_TAVILY_VERIFICATION = True

# ---------------------------------------------------
# REASONING AGENT — Three-stage LLM
#
# STAGE 1 (batch): classify headlines → relevant or not
#
# STAGE 2 (deep): full article analysis for ALL relevant leads
#   - For EXISTING venues: LLM must explicitly confirm the article is
#     about THIS venue's own construction (not nearby land, not a
#     different project, not vague city development). If not confirmed,
#     the lead is DROPPED — never shown as a lead on a guess.
#   - For PLANNED / UNDER_CONSTRUCTION venues: confirmed as real via
#     Wikipedia/league data already — these are GUARANTEED leads
#     regardless of what the LLM concludes from the article. The LLM
#     still reads the article (if any) to enrich tier/score/stakeholders,
#     but can never cause the lead to be dropped.
#   - Tier must be justified with a specific stated fact from the
#     article, not inferred from venue size/fame/assumption.
#
# STAGE 3 (verify, new): the article Stage 2 read may be stale by the
#   time the pipeline runs — a project can have moved from "funding
#   approved" to "actively under construction" months later, and the
#   original article never gets updated. Stage 3 does a fresh Tavily
#   search per lead and asks the LLM to reconcile the ORIGINAL article's
#   tier against CURRENT real-world status, only ever moving the tier
#   forward (never backward) unless the evidence is unambiguous.
# ---------------------------------------------------

BATCH_PROMPT = """
You classify news headlines about US sports venues.
Return ONLY valid JSON:

{
  "results": [
    {
      "idx": <same index as input>,
      "relevant": <true|false>,
      "signal_tier": <1|2|3|4|null>,
      "engagement": <"engage_now"|"monitor"|"too_late"|"not_relevant">,
      "reason": <one short phrase>
    }
  ]
}

TIER DEFINITIONS (Tier 1 is EARLIEST and HIGHEST VALUE, Tier 4 is LATEST
and LOWEST VALUE — by the time an RFP is posted we are already late):
1 = renovation/expansion discussed, no funding yet — earliest, most valuable
2 = funding/bond/budget approved by city/authority
3 = architect or GC explicitly named and hired — engage at the latest here
4 = construction started, RFP posted, opens within 2 years — already late

PLANNED VENUE RULE:
  venue_status = "under_construction" → Tier 3-4, engagement = too_late OR monitor
  venue_status = "planned"            → Tier 1-2, engagement = engage_now
  venue_status = "confirmed_no_news"  → mark relevant=true automatically,
    signal_tier = 1 (if context suggests "planned") or 3 (if "under_construction"),
    engagement = engage_now (planned) or monitor (under_construction).
    This is a guaranteed real project from league data — never mark not_relevant.

relevant=TRUE only if:
  ✓ Headline/description is about THIS specific venue
  ✓ Describes construction, renovation, funding, or planning
  ✓ Venue is in the United States

relevant=FALSE if:
  ✗ Different venue mentioned (not the queried venue)
  ✗ Article is about LAND NEAR the venue, a separate adjacent
    development, or a different project entirely — not the venue itself
  ✗ Team news (player, signing, mural) — not the building
  ✗ Small grant < $1M
  ✗ Outside USA (Canada, UK, Japan etc.)
  ✗ Concert, game result, team performance
  ✗ School/charity/housing construction

CRITICAL: Tier 4 MUST be too_late — never engage_now
CRITICAL: Do not guess tier from venue size or fame — only from what the
headline/description explicitly states.
""".strip()


def batch_classify(signals: list[dict]) -> dict:
    print(f"\n[STEP 3A] Batch classifying {len(signals)} headlines...", flush=True)
    classified = {}
    batches = [signals[i:i+10] for i in range(0, len(signals), 10)]

    for b_idx, batch in enumerate(batches):
        payload = [
            {
                "idx":          b_idx * 10 + i,
                "venue":        s.get("venue_name",""),
                "league":       s.get("league",""),
                "venue_status": s.get("venue_status","existing"),
                "capacity":     s.get("capacity", 0),
                "planned_year": s.get("planned_year",""),
                "headline":     s.get("headline",""),
                "description":  (s.get("description","") or "")[:200],
                "content":      (s.get("content","") or "")[:500],
                "published":    (s.get("published_at","") or "")[:10],
            }
            for i, s in enumerate(batch)
        ]

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL, max_tokens=800, temperature=0.0,
                    response_format={"type":"json_object"},
                    messages=[
                        {"role":"system","content":BATCH_PROMPT},
                        {"role":"user","content":
                            "Classify these headlines:\n" +
                            json.dumps(payload, ensure_ascii=True)}
                    ]
                )
                raw    = resp.choices[0].message.content.strip()
                parsed = json.loads(raw)
                items  = parsed.get("results", parsed) if isinstance(parsed,dict) else parsed
                if isinstance(items, list):
                    for item in items:
                        classified[item["idx"]] = item
                break
            except Exception as e:
                if "429" in str(e):
                    time.sleep(30*(attempt+1)); continue
                print(f"    [BATCH ERROR] batch {b_idx}: {e}", flush=True)
                for p in payload:
                    classified[p["idx"]] = {
                        "idx":p["idx"],"relevant":False,
                        "signal_tier":None,"engagement":"not_relevant",
                        "reason":"classification-error"
                    }
                break
        time.sleep(0.5)
        done = (b_idx+1)*10
        print(f"  Classified {min(done,len(signals))}/{len(signals)}", end="\r", flush=True)

    print()
    return classified


DEEP_PROMPT = """
You are a senior BD analyst for a company that manufactures aluminum railings,
platforms, and structural components for large sports venues.

Analyze the article and return ONLY valid JSON — no markdown, no extra text.
Keep "whats_happening" and "why_priority" SHORT (max 2 sentences each) so the
response never gets truncated.

{
  "venue_confirmed": <true|false>,
  "evidence": <ONE short sentence, paraphrased in your own words, stating the
    specific fact from the article that supports your tier — not a quote>,
  "signal_tier": <1|2|3|4>,
  "tier_label": <"Tier 1 — Early Rumor"|"Tier 2 — Funding Committed"|"Tier 3 — Design Phase"|"Tier 4 — Procurement">,
  "score": <0-100>,
  "likelihood": <0-100>,
  "project_type": <"New Construction"|"Major Renovation"|"Minor Upgrade"|"Expansion"|"Repurposing">,
  "whats_happening": <max 2 sentences — factual description>,
  "why_priority": <max 1-2 sentences — why this matters for railing/platform business>,
  "stakeholders": [
    {"name": <exact name from article only>, "type": <"Architect"|"GC"|"Owner"|"City Official"|"Other">}
  ],
  "engagement": <"engage_now"|"monitor"|"too_late">
}

VENUE_CONFIRMED RULE (applies ONLY when venue_status = "existing"):
  Set venue_confirmed=true ONLY if the article is unambiguously about THIS
  venue's own construction, renovation, or funding — not:
    - land/development NEAR the venue but not the venue itself
    - a different venue or a separate unrelated project
    - vague city-wide development with no specific tie to this venue
  If you cannot confirm the article is about this specific venue's own
  project, set venue_confirmed=false. A false here means this lead will
  be DROPPED — be honest, do not default to true to be helpful.

  If venue_status is "planned", "under_construction", or "confirmed_no_news":
    Always set venue_confirmed=true — this project is already verified
    true via official league/Wikipedia data, independent of the article.

EVIDENCE-BASED TIER RULE:
  Your signal_tier MUST be justified by a specific fact stated in the
  article (or, for confirmed projects with no article, by the
  venue_status itself). Never infer a higher or lower tier from the
  venue's size, fame, or your own assumption about how renovations
  "usually" proceed. If the article doesn't state anything specific
  about funding/architect/construction stage, set engagement="monitor"
  and use the lowest tier consistent with what IS stated.

SCORING FORMULA:
  Base by Tier:    T1=60, T2=45, T3=30, T4=15
    (Score must decrease monotonically from T1 to T4 — never score a
    later tier higher than an earlier one.)
  Capacity bonus:  >60k cap = +10, >40k = +8, >20k = +5, else = +2
  Confirmed project bonus:
    venue_status = "planned"            → +20
    venue_status = "under_construction" → +10
    venue_status = "confirmed_no_news"  → +15
  Likelihood adj:  multiply by (likelihood/100)

  No-article case (venue_status = "confirmed_no_news", empty article_body):
    Use signal_tier=1 if context/planned_year suggests early-stage
    ("planned"), or signal_tier=3 if it's an under_construction project.
    Set evidence = "Confirmed via league/Wikipedia source — no public
    news article found yet." and whats_happening should say the same.

STAKEHOLDERS: ONLY names explicitly in the provided text — never invent.
If article_body is empty, return an empty stakeholders list.
""".strip()


def fetch_full_article(url: str) -> str:
    if not url: return ""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded)
        return (text or "")[:3000]
    except Exception:
        return ""


def _repair_truncated_json(raw: str) -> str:
    """
    If the LLM response got cut off mid-string (hit max_tokens),
    try to salvage a valid JSON object by closing open strings/braces.
    """
    raw = raw.strip()
    # Count unescaped quotes to detect an unterminated string
    if raw.count('"') % 2 != 0:
        raw += '"'
    # Balance braces
    open_braces  = raw.count("{")
    close_braces = raw.count("}")
    open_brackets  = raw.count("[")
    close_brackets = raw.count("]")
    raw += "]" * max(0, open_brackets - close_brackets)
    raw += "}" * max(0, open_braces - close_braces)
    return raw


def deep_analyze(signal: dict) -> dict | None:
    full_text = signal.get("content","") or ""
    if not full_text and signal.get("url"):
        full_text = fetch_full_article(signal["url"])

    payload = {
        "venue_name":   signal.get("venue_name",""),
        "league":       signal.get("league",""),
        "team":         signal.get("team",""),
        "city":         signal.get("city",""),
        "state":        signal.get("state",""),
        "capacity":     signal.get("capacity",""),
        "venue_status": signal.get("venue_status","existing"),
        "planned_year": signal.get("planned_year",""),
        "headline":     signal.get("headline",""),
        "description":  signal.get("description",""),
        "article_body": full_text,
        "source":       signal.get("source",""),
        "url":          signal.get("url",""),
        "published_at": signal.get("published_at",""),
    }
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL, max_tokens=1100, temperature=0.1,
                response_format={"type":"json_object"},
                messages=[
                    {"role":"system","content":DEEP_PROMPT},
                    {"role":"user","content":json.dumps(payload, ensure_ascii=True)}
                ]
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r'^```[a-z]*\n?','',raw).rstrip('`').strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Try to repair a truncated response before giving up
                repaired = _repair_truncated_json(raw)
                return json.loads(repaired)
        except json.JSONDecodeError as e:
            print(f"    [JSON ERROR] {e} — retrying with shorter content", flush=True)
            # Shrink article body and retry once
            payload["article_body"] = payload["article_body"][:1200]
            continue
        except Exception as e:
            if "429" in str(e):
                time.sleep(30*(attempt+1)); continue
            print(f"    [LLM ERROR] {e}", flush=True); return None
    return None


# ---------------------------------------------------------------
# STAGE 3 — Tavily current-status cross-check
#
# The Stage 2 tier is only as fresh as the single article it read.
# This stage searches for the venue's CURRENT status independent of
# that article and asks the LLM to reconcile the two — but biased to
# only ever move the tier FORWARD (stages don't reverse), to avoid a
# noisy/ambiguous search result accidentally downgrading a correct
# tier.
# ---------------------------------------------------------------

VERIFY_PROMPT = """
You are reconciling a stadium/arena construction lead's tier against
fresh web search results, because the original article may be months
old and the project may have progressed since.

First, check the FRESH SEARCH RESULTS against ALL FOUR stages
explicitly — do not stop at the first one that seems to match:
  Q1: Is it still early discussion/rumor, with NO funding committed?  → Tier 1
  Q2: Has funding/budget/bond been approved or committed?            → Tier 2
  Q3: Has an architect or general contractor been named/hired?       → Tier 3
  Q4: Has construction physically started (groundbreaking, crews on
      site, structural milestones), OR is there a confirmed opening
      date within ~2 years?                                          → Tier 4
Pick the stage indicated by the search results, even if it skips past
the original tier by more than one level (e.g. original=Tier 1 but
fresh results show active construction → Tier 4 is correct, don't cap
the jump at Tier 2).

TIER DEFINITIONS (1=earliest/highest value, 4=latest/lowest value):
1 = renovation/expansion discussed, no funding yet
2 = funding/bond/budget approved
3 = architect or GC explicitly named and hired
4 = construction started / RFP posted / opens within 2 years

RULES:
- Construction stages only move FORWARD over time (1→2→3→4), never
  backward. Only propose a HIGHER tier number than the original, and
  only if the fresh search results clearly and specifically support it.
- If the fresh results are about a different project, are vague, are
  inconclusive, or don't clearly show further progress, keep the
  original tier — do not guess.
- Do not invent facts. Base updated_evidence only on what the search
  results actually say.

Return ONLY valid JSON:
{
  "detected_stage": <1|2|3|4 — the stage YOU determined from Q1-Q4 above>,
  "tier_changed": <true|false>,
  "new_tier": <1|2|3|4>,
  "updated_evidence": <ONE short sentence, your own words, only filled
    in if tier_changed is true>,
  "source_index": <the bracketed number [N] of the search result that
    supports updated_evidence — required if tier_changed is true,
    otherwise null>,
  "reasoning": <one short phrase explaining the decision either way>
}
""".strip()


def verify_current_status(lead: dict) -> dict | None:
    """
    Runs a fresh Tavily search for the lead's venue and asks the LLM
    to check whether the Stage 2 tier is still accurate. Returns a
    dict with the verification result, or None if the search/LLM call
    failed (caller should keep the original tier on None).
    """
    venue = lead.get("venue_name", "")
    team = lead.get("team", "")
    # Deliberately NOT anchored to one stage-word (e.g. just "funding") —
    # a project that's already under construction often doesn't mention
    # "funding" at all (e.g. a "West Tower tops out" article). Cover all
    # four stages' typical keywords so the search isn't biased toward
    # only detecting early-stage news.
    current_year = datetime.now().year
    query = (
        f"{venue} {team} stadium funding approved architect groundbreaking "
        f"under construction opening {current_year}"
    ).strip()

    try:
        search_resp = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=4,
            topic="news",
            days=180,  # bias toward results from roughly the last 6 months
        )
    except Exception as e:
        print(f"         [TAVILY ERROR] {e} — keeping original tier", flush=True)
        return None

    results = search_resp.get("results", []) if isinstance(search_resp, dict) else []
    if not results:
        return None

    # Number each result so the LLM can tell us which one it actually
    # used — otherwise we'd update the evidence TEXT but leave the
    # lead's source/url pointing at the stale original GNews article,
    # which is misleading (evidence and link would disagree).
    fresh_context = "\n".join(
        f"[{i+1}] {r.get('title','')}: {(r.get('content','') or '')[:300]}"
        for i, r in enumerate(results)
    )
    result_urls = [r.get("url", "") for r in results]

    verify_payload = {
        "venue_name":       venue,
        "original_tier":    lead.get("signal_tier"),
        "original_evidence": lead.get("evidence", ""),
        "fresh_search_results": fresh_context,
    }

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL, max_tokens=300, temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": VERIFY_PROMPT},
                    {"role": "user", "content": json.dumps(verify_payload, ensure_ascii=True)},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            parsed = json.loads(raw)
            # Map the LLM's chosen result number back to a real URL.
            src_idx = parsed.get("source_index")
            if isinstance(src_idx, int) and 1 <= src_idx <= len(result_urls):
                parsed["updated_source_url"] = result_urls[src_idx - 1]
            else:
                parsed["updated_source_url"] = None
            return parsed
        except json.JSONDecodeError:
            continue
        except Exception as e:
            if "429" in str(e):
                time.sleep(20 * (attempt + 1)); continue
            print(f"         [VERIFY LLM ERROR] {e} — keeping original tier", flush=True)
            return None
    return None


def compute_score(tier: int, capacity, venue_status: str, likelihood) -> int:
    """
    Deterministic re-implementation of the SCORING FORMULA from
    DEEP_PROMPT. Used whenever Stage 3 changes the tier, so the score
    always stays mathematically consistent with the tier rather than
    trusting the LLM to redo the arithmetic.
    """
    base = {1: 60, 2: 45, 3: 30, 4: 15}.get(tier, 30)

    try:
        cap = float(capacity or 0)
    except (TypeError, ValueError):
        cap = 0
    if cap > 60000:   cap_bonus = 10
    elif cap > 40000: cap_bonus = 8
    elif cap > 20000: cap_bonus = 5
    else:             cap_bonus = 2

    confirmed_bonus = {"planned": 20, "under_construction": 10,
                        "confirmed_no_news": 15}.get(venue_status, 0)

    if likelihood in (None, ""):
        lk = 0.7  # reasonable default if likelihood is missing
    else:
        try:
            lk = float(likelihood) / 100
        except (TypeError, ValueError):
            lk = 0.7  # malformed value (e.g. "high") — same safe default

    return round((base + cap_bonus + confirmed_bonus) * lk)


def build_lead(signal: dict, cls: dict, analysis: dict | None) -> dict:
    t   = (analysis or {}).get("signal_tier") or cls.get("signal_tier")
    eng = (analysis or {}).get("engagement")  or cls.get("engagement","monitor")

    TIER_LABELS = {
        1:"Tier 1 — Early Rumor", 2:"Tier 2 — Funding Committed",
        3:"Tier 3 — Design Phase", 4:"Tier 4 — Procurement",
    }
    stakes = (analysis or {}).get("stakeholders",[])
    if t == 4: eng = "too_late"

    return {
        "venue_name":      signal.get("venue_name",""),
        "league":          signal.get("league",""),
        "team":            signal.get("team",""),
        "city":            signal.get("city",""),
        "state":           signal.get("state",""),
        "capacity":        signal.get("capacity",""),
        "venue_status":    signal.get("venue_status","existing"),
        "planned_year":    signal.get("planned_year",""),
        "signal_tier":     t,
        "tier_label":      (analysis or {}).get("tier_label") or TIER_LABELS.get(t,""),
        "score":           (analysis or {}).get("score",""),
        "likelihood":      (analysis or {}).get("likelihood",""),
        "project_type":    (analysis or {}).get("project_type",""),
        "whats_happening": (analysis or {}).get("whats_happening","") or cls.get("reason",""),
        "why_priority":    (analysis or {}).get("why_priority",""),
        "evidence":        (analysis or {}).get("evidence",""),
        "venue_confirmed": (analysis or {}).get("venue_confirmed", True),
        "stakeholders_raw":json.dumps(stakes),
        "source":          signal.get("url",""),
        "source_name":     signal.get("source",""),
        "published_at":    signal.get("published_at",""),
        "engagement":      eng,
        "feedback":        "",
        "notes":           "",
    }


# ---------------------------------------------------------------
# DETERMINISTIC PRIORITY OVERRIDE
#
# Wikipedia/league sources are ground truth for venue_status — a venue
# tagged "planned" or "under_construction" there IS happening, full stop.
# The LLM's tier/score is useful for ordering *within* a status group,
# but it should never be trusted to decide whether a confirmed project
# outranks an existing venue's news article.
# ---------------------------------------------------------------
STATUS_RANK = {
    "planned":            0,
    "under_construction": 1,
    "existing":           2,
}

def _lead_sort_key(r: dict):
    status_rank = STATUS_RANK.get(r.get("venue_status"), 2)
    tier  = r.get("signal_tier") or 99
    score = float(r.get("score", 0) or 0)
    return (status_rank, tier, -score)


def venue_mentioned(signal: dict) -> bool:
    # Synthetic "confirmed_no_news" signals always pass — venue name
    # is literally in the headline by construction.
    if signal.get("signal_type") == "confirmed_no_news":
        return True

    venue = (signal.get("venue_name","") or "").lower()
    team  = (signal.get("team","")       or "").lower()
    text  = " ".join([
        signal.get("headline","") or "",
        signal.get("description","") or "",
        signal.get("content","") or "",
    ]).lower()

    venue_words = [w for w in venue.split() if len(w)>4
                   and w not in {"arena","stadium","center","field","park","garden"}]
    if any(w in text for w in venue_words): return True
    if team:
        for t in team.split(";"):
            t = t.strip()
            if len(t) > 3 and t in text: return True
    return False


def run_reasoning(signals: list[dict]) -> tuple[list[dict], list[dict]]:
    for i, s in enumerate(signals): s["_idx"] = i

    pre_filtered = [s for s in signals if venue_mentioned(s)]
    skipped      = len(signals) - len(pre_filtered)
    print(f"  Pre-filter: {len(pre_filtered)} kept, {skipped} skipped", flush=True)

    classified = batch_classify(pre_filtered)

    relevant_count = sum(1 for c in classified.values() if c.get("relevant",True))
    print(f"  Relevant signals    : {relevant_count}", flush=True)

    seen_leads = {}
    for s in pre_filtered:
        idx = s["_idx"]
        cls = classified.get(idx, {
            "relevant":True,"signal_tier":1,"engagement":"monitor","reason":""
        })

        is_confirmed_project = s.get("venue_status") in ("planned","under_construction") \
                                or s.get("signal_type") == "confirmed_no_news"

        # SAFEGUARD: confirmed projects (Wikipedia/league source) can never
        # be excluded by a Stage-1 LLM "not relevant" call.
        if is_confirmed_project and not cls.get("relevant", True):
            cls = {**cls, "relevant": True,
                   "signal_tier": cls.get("signal_tier") or
                                  (3 if s.get("venue_status")=="under_construction" else 1),
                   "engagement": cls.get("engagement") or "engage_now",
                   "reason": "confirmed project (league/Wikipedia source) — forced relevant"}

        if not cls.get("relevant",True): continue

        key    = s["venue_name"].lower().strip()
        s_tier = cls.get("signal_tier") or 0
        existing_tier = (seen_leads[key].get("signal_tier") or 0) if key in seen_leads else -1
        if s_tier <= existing_tier: continue

        lead = build_lead(s, cls, None)
        lead["_signal"] = s
        seen_leads[key] = lead

    all_leads = list(seen_leads.values())
    print(f"  All Leads (pre-deep): {len(all_leads)} unique venues", flush=True)

    print(f"\n[STEP 3B] Deep analysis for {len(all_leads)} leads...", flush=True)
    dropped_not_confirmed = []

    for i, lead in enumerate(all_leads, 1):
        signal = lead.pop("_signal", None)
        is_confirmed_project = lead.get("venue_status") in ("planned","under_construction")
        print(f"  [{i:02d}/{len(all_leads)}] {lead['venue_name'][:45]}"
              f" | cap={lead.get('capacity',0)} | status={lead.get('venue_status','')}", flush=True)

        if signal:
            analysis = deep_analyze(signal)
            if analysis:
                s1_tier = classified.get(signal.get("_idx",0),{}).get("signal_tier")
                s2_tier = analysis.get("signal_tier")
                if s1_tier and s2_tier and s1_tier != s2_tier:
                    print(f"         ⚠️  TIER MISMATCH: T{s1_tier}→T{s2_tier} "
                          f"(evidence: {analysis.get('evidence','')[:80]})", flush=True)

                updated = build_lead(signal,
                                     classified.get(signal.get("_idx",0),{}),
                                     analysis)
                lead.update({k:v for k,v in updated.items() if v not in (None,"")})

                # GATEKEEPING: existing venues must be LLM-confirmed as
                # actually about this specific venue's own project.
                # Confirmed projects (planned/under_construction) are
                # NEVER dropped here — they're true regardless of article.
                if not is_confirmed_project and analysis.get("venue_confirmed") is False:
                    print(f"         ❌ DROPPED — not confirmed about this venue "
                          f"(evidence: {analysis.get('evidence','')[:80]})", flush=True)
                    dropped_not_confirmed.append(lead["venue_name"])
                    lead["_drop"] = True

                print(f"         → T{lead.get('signal_tier')} | "
                      f"score={lead.get('score')} | cap={lead.get('capacity')}", flush=True)
        time.sleep(0.5)

    # Remove dropped (not-confirmed existing venue) leads
    all_leads = [l for l in all_leads if not l.get("_drop")]
    for lead in all_leads:
        lead.pop("_signal", None)
        lead.pop("_drop", None)

    if dropped_not_confirmed:
        print(f"\n  Dropped (not venue-specific): {len(dropped_not_confirmed)}", flush=True)

    # -----------------------------------------------------------
    # STAGE 3: Tavily current-status cross-check, on every surviving
    # lead. Runs after the drop-check (no point verifying leads we're
    # about to discard) and before sorting (a tier change affects rank).
    # -----------------------------------------------------------
    if ENABLE_TAVILY_VERIFICATION:
        print(f"\n[STEP 3C] Verifying current status for {len(all_leads)} leads via Tavily...", flush=True)
        tier_updates = 0
        for i, lead in enumerate(all_leads, 1):
            print(f"  [{i:02d}/{len(all_leads)}] {lead['venue_name'][:45]}", end="", flush=True)
            verification = verify_current_status(lead)
            if verification and verification.get("tier_changed"):
                old_tier = lead.get("signal_tier")
                new_tier = verification.get("new_tier")
                # Don't fully trust the LLM to honor the "forward only"
                # instruction from the prompt — enforce it in code too,
                # same philosophy as STATUS_RANK/_lead_sort_key above.
                valid_new_tier = (
                    isinstance(new_tier, int)
                    and new_tier in (1, 2, 3, 4)
                    and isinstance(old_tier, int)
                    and new_tier > old_tier
                )
                if valid_new_tier:
                    TIER_LABELS = {
                        1: "Tier 1 — Early Rumor", 2: "Tier 2 — Funding Committed",
                        3: "Tier 3 — Design Phase", 4: "Tier 4 — Procurement",
                    }
                    lead["signal_tier"] = new_tier
                    lead["tier_label"] = TIER_LABELS.get(new_tier, lead.get("tier_label"))
                    lead["evidence"] = verification.get("updated_evidence") or lead.get("evidence")
                    # Keep the source link consistent with the evidence —
                    # otherwise the URL still points at the stale article
                    # that produced the OLD tier, contradicting the new
                    # evidence text right next to it.
                    new_url = verification.get("updated_source_url")
                    if new_url:
                        lead["source"] = new_url
                        lead["source_name"] = "Tavily (verified)"
                    lead["score"] = compute_score(
                        new_tier, lead.get("capacity"),
                        lead.get("venue_status", "existing"), lead.get("likelihood"),
                    )
                    if new_tier == 4:
                        lead["engagement"] = "too_late"
                    tier_updates += 1
                    print(f"  ⚠️  T{old_tier}→T{new_tier} ({verification.get('reasoning','')[:60]})", flush=True)
                else:
                    print("  (no change)", flush=True)
            else:
                print("  (no change)", flush=True)
            time.sleep(0.3)
        print(f"  Stage 3 tier updates: {tier_updates}/{len(all_leads)}", flush=True)

    all_leads.sort(key=_lead_sort_key)
    for i, r in enumerate(all_leads, 1): r["rank"] = i

    act_now = [l for l in all_leads if l.get("engagement")=="engage_now"]
    act_now.sort(key=_lead_sort_key)
    for i, r in enumerate(act_now, 1): r["act_now_rank"] = i

    confirmed_in_leads = sum(1 for l in all_leads
                             if l.get("venue_status") in ("planned","under_construction"))
    print(f"\n  All Leads total     : {len(all_leads)}", flush=True)
    print(f"  Confirmed projects  : {confirmed_in_leads} (planned/under_construction)", flush=True)
    print(f"  Act Now (subset)    : {len(act_now)}", flush=True)
    return all_leads, act_now