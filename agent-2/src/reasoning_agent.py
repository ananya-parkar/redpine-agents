import re
import json
import time
from datetime import datetime
from llm_client import call_llm_json, call_llm_web_search_json
from tuning_prompt import build_tuning_block
from db_writer import get_active_tuning_triggers

# Stage 3 (current-status verification) uses Claude's own web search —
# no Tavily/SearchAPI vendor account needed. Set to False to skip Stage 3
# entirely (e.g. to save web-search cost on a test run).
ENABLE_WEB_SEARCH_VERIFICATION = True

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
#   original article never gets updated. Stage 3 has Claude run a fresh
#   web search per lead and reconcile the ORIGINAL article's
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


def batch_classify(signals: list[dict], tuning_block: str = "") -> dict:
    print(f"\n[STEP 3A] Batch classifying {len(signals)} headlines...", flush=True)
    classified = {}
    batches = [signals[i:i+10] for i in range(0, len(signals), 10)]
    system_prompt = BATCH_PROMPT + tuning_block

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

        try:
            parsed = call_llm_json(
                system=system_prompt,
                user_content=("Classify these headlines:\n" +
                              json.dumps(payload, ensure_ascii=True)),
                max_tokens=800, temperature=0.0,
            )
            items = parsed.get("results", parsed) if isinstance(parsed, dict) else parsed
            if isinstance(items, list):
                for item in items:
                    classified[item["idx"]] = item
        except Exception as e:
            print(f"    [BATCH ERROR] batch {b_idx}: {e}", flush=True)
            for p in payload:
                classified[p["idx"]] = {
                    "idx":p["idx"],"relevant":False,
                    "signal_tier":None,"engagement":"not_relevant",
                    "reason":"classification-error"
                }
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
  "likelihood": <0-100 — see LIKELIHOOD RUBRIC below>,
  "project_type": <"New Construction"|"Major Renovation"|"Minor Upgrade"|"Expansion"|"Repurposing">,
  "whats_happening": <max 2 sentences — factual description>,
  "why_priority": <max 1-2 sentences — why this matters for railing/platform business>,
  "stakeholders": [
    {"name": <exact name from article only>, "type": <"Architect"|"GC"|"Owner"|"City Official"|"Other">}
  ],
  "engagement": <"engage_now"|"monitor"|"too_late">
}

LIKELIHOOD RUBRIC — likelihood = probability THIS project is real and will
actually proceed (NOT how far along it is; that's the tier). Use the
article's concreteness:
  85-100 = under construction / funding secured / official groundbreaking
  65-84  = funding or budget officially approved, or a firm public commitment
  45-64  = proposed with real momentum (feasibility study, official body
           discussing it, named backers)
  25-44  = early rumor or single speculative source, no official backing
  0-24   = vague possibility, offhand mention, heavily hedged
Give a specific number from the article's evidence — do not default to a
round 50 out of habit.

NOTE ON ENGAGEMENT & SCORE: you may fill these in, but the pipeline
RE-DERIVES both deterministically from tier + likelihood afterwards
(Tier 4 → too_late; Tier 1-3 with likelihood ≥ 50 → engage_now; else
monitor). So focus your effort on getting TIER and LIKELIHOOD right —
those two drive everything downstream.

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

SCORING FORMULA (score = project MERIT, used for ranking only — engagement
is derived separately, so do NOT fold timing into the score):
  Base by Tier:    T1=60, T2=45, T3=30, T4=15
    (Score must decrease monotonically from T1 to T4 — never score a
    later tier higher than an earlier one.)
  Capacity bonus:  >60k cap = +10, >40k = +8, >20k = +5, else = +2
  Confirmed project bonus:
    venue_status = "planned"            → +20
    venue_status = "under_construction" → +10
    venue_status = "confirmed_no_news"  → +15
  Sum the above = raw. Then apply likelihood:
    final = raw * (0.6 + 0.4 * likelihood/100)
    (likelihood shaves at most 40% off — it never zeroes a strong lead)
  Clamp final to the 0-100 range and round to an integer.

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


def deep_analyze(signal: dict, tuning_block: str = "") -> dict | None:
    full_text = signal.get("content","") or ""
    if not full_text and signal.get("url"):
        full_text = fetch_full_article(signal["url"])
    system_prompt = DEEP_PROMPT + tuning_block

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
    for attempt in range(2):
        try:
            return call_llm_json(
                system=system_prompt,
                user_content=json.dumps(payload, ensure_ascii=True),
                max_tokens=1100, temperature=0.1,
            )
        except json.JSONDecodeError as e:
            print(f"    [JSON ERROR] {e} — retrying with shorter content", flush=True)
            payload["article_body"] = payload["article_body"][:1200]
            continue
        except Exception as e:
            print(f"    [LLM ERROR] {e}", flush=True)
            return None
    return None


# ---------------------------------------------------------------
# STAGE 3 — Claude web-search current-status cross-check
#
# The Stage 2 tier is only as fresh as the single article it read.
# This stage searches for the venue's CURRENT status independent of
# that article and asks the LLM to reconcile the two — but biased to
# only ever move the tier FORWARD (stages don't reverse), to avoid a
# noisy/ambiguous search result accidentally downgrading a correct
# tier.
# ---------------------------------------------------------------

VERIFY_PROMPT = """
You are reconciling a stadium/arena construction lead's tier against the
CURRENT real-world status, because the original article may be months old
and the project may have progressed since.

Use the web_search tool to look up the venue's latest construction status
(the user message includes a search hint). Then check what you find
against ALL FOUR stages explicitly — do not stop at the first one that
seems to match:
  Q1: Is it still early discussion/rumor, with NO funding committed?  → Tier 1
  Q2: Has funding/budget/bond been approved or committed?            → Tier 2
  Q3: Has an architect or general contractor been named/hired?       → Tier 3
  Q4: Has construction physically started (groundbreaking, crews on
      site, structural milestones), OR is there a confirmed opening
      date within ~2 years?                                          → Tier 4
Pick the stage indicated by what you find, even if it skips past the
original tier by more than one level (e.g. original=Tier 1 but fresh
results show active construction → Tier 4 is correct, don't cap the jump
at Tier 2).

TIER DEFINITIONS (1=earliest/highest value, 4=latest/lowest value):
1 = renovation/expansion discussed, no funding yet
2 = funding/bond/budget approved
3 = architect or GC explicitly named and hired
4 = construction started / RFP posted / opens within 2 years

RULES:
- Construction stages only move FORWARD over time (1→2→3→4), never
  backward. Only propose a HIGHER tier number than the original, and
  only if your search results clearly and specifically support it.
- If your results are about a different project, are vague, are
  inconclusive, or don't clearly show further progress, keep the
  original tier — do not guess.
- Do not invent facts. Base updated_evidence only on what your search
  results actually say.

Return ONLY valid JSON:
{
  "detected_stage": <1|2|3|4 — the stage YOU determined from Q1-Q4 above>,
  "tier_changed": <true|false>,
  "new_tier": <1|2|3|4>,
  "updated_evidence": <ONE short sentence, your own words, only filled
    in if tier_changed is true>,
  "source_url": <the URL of the search result that supports
    updated_evidence — required if tier_changed is true, otherwise null>,
  "reasoning": <one short phrase explaining the decision either way>
}
""".strip()


def verify_current_status(lead: dict) -> dict | None:
    """
    Uses Claude's OWN web search (Anthropic built-in) to look up the
    venue's current construction status and reconcile it against the
    Stage-2 tier. Claude searches and reasons in one shot (this replaced
    the old Tavily integration). Returns a dict with the verification result,
    or None if the call failed (caller keeps the original tier on None).
    """
    venue = lead.get("venue_name", "")
    team = lead.get("team", "")
    current_year = datetime.now().year

    # Claude does the searching itself now, so instead of pre-fetched
    # results we hand it the venue + the search intent and let it decide
    # what to query. Keep the same 4-stage framing so it isn't biased
    # toward only early-stage news.
    verify_payload = {
        "venue_name":       venue,
        "team":             team,
        "original_tier":    lead.get("signal_tier"),
        "original_evidence": lead.get("evidence", ""),
        "search_hint": (
            f"Search the web for the CURRENT status of the '{venue}' "
            f"{team} stadium/arena construction project as of {current_year}: "
            f"funding approval, architect/GC hired, groundbreaking, active "
            f"construction, or opening date. Prefer results from the last "
            f"6 months."
        ),
    }

    try:
        parsed = call_llm_web_search_json(
            system=VERIFY_PROMPT,
            user_content=json.dumps(verify_payload, ensure_ascii=True),
            max_tokens=1200, temperature=0.0,
            max_uses=3,   # up to 3 searches per lead — keeps cost bounded
        )
        # Claude cites its own source URL in the JSON now (updated_source_url),
        # so no separate result-index → URL mapping is needed.
        if "updated_source_url" not in parsed:
            parsed["updated_source_url"] = parsed.get("source_url") or None
        return parsed
    except Exception as e:
        print(f"         [VERIFY WEB-SEARCH ERROR] {e} — keeping original tier", flush=True)
        return None


# ---------------------------------------------------------------
# RESCUE — existing venue whose fetched article turned out to be irrelevant
#
# When an EXISTING venue's news article is about something unrelated (a
# coaching hire, a lawsuit, a game recap), venue_confirmed comes back false
# and the lead would normally be dropped. But the bad article doesn't mean
# there's no real project — it just means NewsAPI handed us the wrong story.
# Before dropping, we do ONE web search to check whether this venue actually
# has a current construction/renovation/funding project. If yes → keep the
# lead with fresh tier/evidence from the search. If nothing real turns up →
# drop it (now confirmed there's genuinely no project, not just a bad article).
# ---------------------------------------------------------------

RESCUE_PROMPT = """
You are checking whether a specific EXISTING US stadium/arena has a CURRENT,
MAJOR, ACTIVE construction/renovation project — because the news article we
first pulled for it turned out to be unrelated (about a game, a player, a
lawsuit, etc.).

Use the web_search tool to look for a REAL, SIGNIFICANT project on THIS venue
itself. The bar is HIGH — this is for a company that sells railings and
structural platforms, so only a substantial building project matters.

COUNTS as a project (has_project = true):
  - a major renovation or expansion (tens of millions+, structural work)
  - a new/replacement stadium for this venue/team
  - funding/bond APPROVED for such a project, or an architect/GC hired for it,
    within roughly the last 12-18 months and still going forward

Does NOT count (has_project = false) — be strict, these are the common traps:
  - routine maintenance, turf/scoreboard/seat swaps, minor upgrades
  - a project that already OPENED / was COMPLETED (it's over, not a lead)
  - naming-rights deals, sponsorships, beer sales, NIL/fundraising, ticket news
  - district / land / hotel development NEAR the venue but not the venue itself
  - vague "we'd like to upgrade someday" quotes with no funding or plan
  - anything you can only support with an old (2+ years) article

If you are not confident there is a real, current, MAJOR project, answer
has_project = false. A false "no project" is far better than reviving a dead
or trivial one — those just clutter the client's list.

Return ONLY valid JSON:
{
  "has_project": <true|false — real, current, MAJOR project on THIS venue>,
  "signal_tier": <1|2|3|4 — only if has_project is true, else null>,
  "evidence": <ONE short sentence in your own words stating the specific
    project fact you found — only if has_project is true>,
  "source_url": <URL of the search result supporting it, or null>,
  "reasoning": <one short phrase either way>
}
""".strip()


# Phrases that reveal the LLM was describing a WRONG/unrelated article rather
# than the actual project. If any of these show up in a surviving lead's
# whats_happening or evidence, that text is garbage and must be replaced —
# otherwise the client reads "the article is about a player trade" right next
# to a real Act Now lead.
_BAD_ARTICLE_PHRASES = (
    "article is about", "article covers", "article discusses",
    "does not mention", "not mention", "unrelated to", "no mention of",
    "no relevance to", "no connection to", "has no relevance",
    "does not discuss", "not relevant to", "is about the", "recap unrelated",
)


def _looks_like_bad_article_text(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(p in t for p in _BAD_ARTICLE_PHRASES)


def _clean_lead_narrative(lead: dict) -> None:
    """
    Final safety net for a SURVIVING lead: make sure neither whats_happening
    nor evidence still contains 'this article is actually about X' text.

    Priority for a replacement:
      1. If the OTHER field (evidence/whats_happening) is clean, mirror it.
      2. Otherwise fall back to an honest confirmed-project line.

    This catches the case where Stage 3 refreshed `evidence` from a web search
    but left the old bad-article `whats_happening` in place (and vice-versa),
    which is exactly how Broncos/Plano/South Philly ended up with a real
    evidence line but a 'the article discusses a player trade' summary.
    """
    wh = (lead.get("whats_happening") or "").strip()
    ev = (lead.get("evidence") or "").strip()
    wh_bad = _looks_like_bad_article_text(wh)
    ev_bad = _looks_like_bad_article_text(ev)

    if not wh_bad and not ev_bad:
        return  # both clean, nothing to do

    status_txt = (lead.get("venue_status", "") or "existing").replace("_", " ")
    fallback = (f"{lead.get('venue_name','This venue')} — confirmed "
                f"{status_txt} project (details being verified).")

    # Fix whats_happening
    if wh_bad:
        lead["whats_happening"] = ev if not ev_bad and ev else fallback
    # Fix evidence
    if ev_bad:
        lead["evidence"] = wh if not wh_bad and wh else (
            "Confirmed via league/Wikipedia source — "
            "no relevant news article found yet.")


# Minor, non-structural work that isn't a railing/platform opportunity.
_TRIVIAL_MARKERS = (
    "sewer", "culvert", "drainage", "sanitary",
    "videoboard", "video board", "scoreboard", "jumbotron",
    "led ", "lighting", "sound system", "audio", "speaker",
    "wifi", "wi-fi", "turf", "playing surface", "grass field",
    "seat replacement", "seating replacement", "paint", "signage",
)
# Signs the project IS substantial/structural — if any of these are present,
# it is NOT trivial even if it also mentions a videoboard etc. Guards against
# dropping big renovations that happen to list minor items among their scope
# (e.g. Neyland's $337M job mentions restrooms; Rose Bowl's $80M campaign).
_SUBSTANTIAL_MARKERS = (
    "expansion", "expand", "new stadium", "replacement", "rebuild",
    "reconstruct", "renovation", "grandstand", "seating bowl", "deck",
    "concourse", "suite", "club level", "end zone", "tower",
    "structural", "premium seating", "luxury", "multipurpose facility",
)


def _is_trivial_project(whats_happening: str, evidence: str) -> bool:
    """
    True if the only project described is minor/non-structural (a sewer line,
    a scoreboard swap, LED/audio/wifi upgrades) with no sign of substantial
    structural work. Used to drop existing-venue leads that technically had a
    'project' but nothing a railing/platform vendor could sell into.

    A large dollar figure ($50M+) or any _SUBSTANTIAL_MARKER overrides the
    trivial flag — big projects often list minor items within a larger scope.
    """
    text = f"{whats_happening} {evidence}".lower()
    if not text.strip():
        return False

    if any(m in text for m in _SUBSTANTIAL_MARKERS):
        return False

    # Big money → not trivial. Catch "$285 million", "$47.14 million", "$2+ billion".
    import re as _re
    for m in _re.finditer(r"\$\s*([\d,.]+)\s*(million|billion|m|b)\b", text):
        try:
            amt = float(m.group(1).replace(",", ""))
            unit = m.group(2)
            millions = amt * (1000 if unit in ("billion", "b") else 1)
            if millions >= 50:      # $50M+ is a real project, not a scoreboard
                return False
        except ValueError:
            pass

    # No substantial signal, no big money — trivial only if it actually
    # matches a minor-work marker (otherwise leave it alone; don't drop
    # things we simply can't classify).
    return any(m in text for m in _TRIVIAL_MARKERS)


def rescue_dropped_venue(lead: dict) -> dict | None:
    """
    One web search to decide whether a would-be-dropped existing venue
    actually has a real project. Returns the parsed dict, or None on
    failure (caller should fall back to dropping the lead).
    """
    venue = lead.get("venue_name", "")
    team  = lead.get("team", "")
    current_year = datetime.now().year
    payload = {
        "venue_name": venue,
        "team":       team,
        "search_hint": (
            f"Does '{venue}' ({team}) have any current stadium/arena "
            f"renovation, expansion, or new-construction project as of "
            f"{current_year}? Look for funding/bond approval, an architect "
            f"or general contractor hired, groundbreaking, or active "
            f"construction on the venue itself."
        ),
    }
    try:
        parsed = call_llm_web_search_json(
            system=RESCUE_PROMPT,
            user_content=json.dumps(payload, ensure_ascii=True),
            max_tokens=1000, temperature=0.0,
            max_uses=3,
        )
        return parsed if isinstance(parsed, dict) else None
    except Exception as e:
        print(f"         [RESCUE ERROR] {e} — will drop", flush=True)
        return None


def compute_score(tier: int, capacity, venue_status: str, likelihood) -> int:
    """
    Deterministic re-implementation of the SCORING FORMULA. Used whenever
    a tier or capacity changes, so the score stays mathematically
    consistent rather than trusting the LLM to redo the arithmetic.

    IMPORTANT — score is PURE PROJECT MERIT and no longer includes any
    engagement/timing term. It measures how valuable the opportunity is
    (earlier tier + bigger venue + confirmed project, tempered by how
    likely the project is real), and is used ONLY for RANKING within a
    group. Whether a lead is engage_now / monitor / too_late is decided
    separately by derive_engagement() below — deriving engagement from
    score and score from engagement at the same time would be circular.

    SOFTENED LIKELIHOOD: the old `* (likelihood/100)` cut up to 100% off
    the score, so even strong leads landed in the 20s-40s and 100 was
    unreachable. We use `0.6 + 0.4*(likelihood/100)`, so likelihood can
    shave at most 40% — scores use the full 0-100 range.
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

    raw = base + cap_bonus + confirmed_bonus
    softened = 0.6 + 0.4 * lk   # likelihood shaves at most 40%, never 100%
    return max(0, min(100, round(raw * softened)))


# ---------------------------------------------------------------
# DETERMINISTIC ENGAGEMENT + LIKELIHOOD
#
# Engagement (engage_now / monitor / too_late) used to come straight from
# the LLM, and it was inconsistent — e.g. a Tier 1 lead at 80% likelihood
# got "monitor" while a Tier 2 at 70% got "engage_now", with no logic tying
# the two together. Because the client's whole Act Now list depends on it,
# we now DERIVE it in code, the same way tier/score are enforced.
#
# Business rule (from the client's doc — Tier 1 is the HIGHEST value, since
# the venue hasn't locked in an architect/GC yet, so there's the best chance
# of winning the work):
#   Tier 4                          → too_late   (construction started; we're late)
#   Tier 1/2/3 AND likelihood ≥ 50% → engage_now (real, actionable project)
#   Tier 1/2/3 AND likelihood < 50% → monitor    (too speculative to act on yet)
#
# Ordering (Tier 1 shows at the TOP of Act Now) is handled separately by
# _lead_sort_key, which already sorts by tier ascending — so as soon as the
# Tier 1 leads become engage_now, they naturally rise to the top.
# ---------------------------------------------------------------

ENGAGE_LIKELIHOOD_MIN = 50   # Tier 1-3 leads at/above this become engage_now

# Minimum likelihood we'll accept for a project we ALREADY KNOW is real from
# Wikipedia/league data, regardless of what the LLM guessed from a (possibly
# bad/empty) news article.
#
# IMPORTANT — being on Wikipedia's "planned" list is NOT itself a reason to
# floor the likelihood. A brand-new proposed stadium with no funding yet
# (Tier 1) is genuinely a lower-odds rumor, and should be allowed to stay
# low → "monitor" (e.g. New White Sox). What justifies a floor is COMMITMENT:
#   - the TIER shows commitment (T2 = funding approved, T3 = architect hired), or
#   - the venue is physically UNDER CONSTRUCTION (can't get more real).
# So there's no blanket "planned" floor — only these:
CONFIRMED_LIKELIHOOD_FLOOR = {
    "under_construction":  90,   # already being built → near-certain
}
# Tier-based floor — a tier that itself implies commitment can't be lowballed
# by a bad article. T1 (merely discussed) deliberately has NO floor.
TIER_LIKELIHOOD_FLOOR = {2: 65, 3: 80, 4: 90}


def derive_likelihood(tier: int, venue_status: str, llm_likelihood) -> int:
    """
    Return a clean 0-100 likelihood.

    Order of trust:
      1. Start from the LLM's number if it gave a sane one (it can read
         nuance from a good article — multiple sources, official commitment).
      2. If the LLM gave nothing/garbage, fall back to a tier/status default.
      3. THEN apply floors: if we independently know the project is real
         (confirmed venue_status) or the tier implies commitment (T2 funding,
         T3 architect), the likelihood can't sink below the floor — even if
         the LLM lowballed it off a bad/empty article.

    Why step 3 matters: New Broncos Stadium is a Tier 2, officially-funded,
    planned NFL stadium. If the fetched article was weak, the LLM might say
    "30%". Without a floor that 30% would push a real, funded project into
    "monitor" and out of Act Now — exactly the bug we saw.
    """
    lk = None
    if llm_likelihood not in (None, ""):
        try:
            lk = int(float(llm_likelihood))
        except (TypeError, ValueError):
            lk = None

    if lk is None or not (0 <= lk <= 100):
        # LLM gave nothing usable — tier/status default.
        base = {1: 55, 2: 75, 3: 85, 4: 95}.get(tier, 60)
        if venue_status in ("planned", "under_construction", "confirmed_no_news"):
            base = min(100, base + 5)
        lk = base

    # Apply floors from what we independently know to be true.
    floor = 0
    floor = max(floor, CONFIRMED_LIKELIHOOD_FLOOR.get(venue_status, 0))
    floor = max(floor, TIER_LIKELIHOOD_FLOOR.get(tier, 0))
    return max(lk, floor)


def derive_engagement(tier: int, likelihood: int) -> str:
    """Deterministic engagement from tier + likelihood (see block comment)."""
    if not tier:
        return "monitor"
    if tier >= 4:
        return "too_late"
    return "engage_now" if (likelihood or 0) >= ENGAGE_LIKELIHOOD_MIN else "monitor"


def build_lead(signal: dict, cls: dict, analysis: dict | None) -> dict:
    t   = (analysis or {}).get("signal_tier") or cls.get("signal_tier")

    TIER_LABELS = {
        1:"Tier 1 — Early Rumor", 2:"Tier 2 — Funding Committed",
        3:"Tier 3 — Design Phase", 4:"Tier 4 — Procurement",
    }
    stakes = (analysis or {}).get("stakeholders",[])

    # Likelihood + engagement are now DERIVED, not taken from the LLM.
    raw_lk = (analysis or {}).get("likelihood")
    likelihood = derive_likelihood(t, signal.get("venue_status","existing"), raw_lk)
    eng = derive_engagement(t, likelihood)

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
        "likelihood":      likelihood,
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

    # Build the "known false positive patterns" block once per run, from
    # whatever tuning triggers are currently unresolved in the DB. Only
    # triggers whose root cause maps to a "reasoning"-scoped rule (see
    # tuning_prompt.py) are included here — issues rooted in non-LLM
    # data (Wikipedia/Wikidata fields, dedup logic) are intentionally
    # left out, since no prompt instruction can change those.
    active_triggers = get_active_tuning_triggers()
    reasoning_tuning_block = build_tuning_block(active_triggers, scope="reasoning")
    if reasoning_tuning_block:
        print(f"  [TUNING] Injecting {reasoning_tuning_block.count('Pattern:')} "
              f"known false-positive pattern(s) into LLM prompts", flush=True)

    pre_filtered = [s for s in signals if venue_mentioned(s)]
    skipped      = len(signals) - len(pre_filtered)
    print(f"  Pre-filter: {len(pre_filtered)} kept, {skipped} skipped", flush=True)

    classified = batch_classify(pre_filtered, tuning_block=reasoning_tuning_block)

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
            analysis = deep_analyze(signal, tuning_block=reasoning_tuning_block)
            if analysis:
                article_is_bad = analysis.get("venue_confirmed") is False

                s1_tier = classified.get(signal.get("_idx",0),{}).get("signal_tier")
                s2_tier = analysis.get("signal_tier")
                # Only surface a "tier changed on re-read" note when the lead
                # is actually SURVIVING. If the article turned out to be about
                # something unrelated (venue_confirmed=false), the tier number
                # is meaningless — the lead is being dropped or its article
                # discarded — so a "T4→T1" line there just looks like a scary
                # (but fake) backward tier jump. Suppress it in that case.
                if s1_tier and s2_tier and s1_tier != s2_tier and not article_is_bad:
                    print(f"         ⚠️  TIER RE-READ: T{s1_tier}→T{s2_tier} "
                          f"(evidence: {analysis.get('evidence','')[:80]})", flush=True)

                updated = build_lead(signal,
                                     classified.get(signal.get("_idx",0),{}),
                                     analysis)
                lead.update({k:v for k,v in updated.items() if v not in (None,"")})

                # GATEKEEPING: existing venues must be LLM-confirmed as
                # actually about this specific venue's own project.
                # Confirmed projects (planned/under_construction) are
                # NEVER dropped here — they're true regardless of article.
                #
                # RESCUE FIRST: before dropping an existing venue because its
                # article was irrelevant, do one web search to see if the
                # venue actually has a real project (NewsAPI just handed us
                # the wrong story). Keep it if a real project turns up; drop
                # only if the search also finds nothing.
                if not is_confirmed_project and article_is_bad:
                    print(f"         · article not about venue — web-searching "
                          f"for a real project...", flush=True)
                    rescue = rescue_dropped_venue(lead)

                    if (rescue and rescue.get("has_project")
                            and rescue.get("signal_tier") in (1, 2, 3)):
                        # Only T1/T2/T3 are worth rescuing. A T4 result means
                        # construction has already started / procurement is
                        # done — we'd be too late to win the railing work, so
                        # a rescued T4 adds no value and just clutters the
                        # list (this is what flooded the sheet with 22
                        # identical "T4 / too_late" existing venues). Treat a
                        # T4 rescue the same as "no project found" → drop.
                        r_tier = rescue.get("signal_tier")
                        lead["signal_tier"] = r_tier
                        TIER_LABELS = {
                            1:"Tier 1 — Early Rumor", 2:"Tier 2 — Funding Committed",
                            3:"Tier 3 — Design Phase", 4:"Tier 4 — Procurement",
                        }
                        lead["tier_label"] = TIER_LABELS.get(r_tier, lead.get("tier_label"))
                        lead["evidence"] = rescue.get("evidence") or lead.get("evidence")
                        lead["whats_happening"] = rescue.get("evidence") or lead.get("whats_happening")
                        r_url = rescue.get("source_url")
                        lead["source"] = r_url or ""
                        lead["source_name"] = "Web search (rescued)"
                        print(f"         ✅ RESCUED — real project found: T{r_tier} "
                              f"({(rescue.get('evidence') or '')[:60]})", flush=True)
                    else:
                        reason = "no real project found"
                        if rescue and rescue.get("signal_tier") == 4:
                            reason = "only a T4 (already too late) — not worth pursuing"
                        print(f"         ❌ DROPPED — {reason}", flush=True)
                        dropped_not_confirmed.append(lead["venue_name"])
                        lead["_drop"] = True

                # BAD ARTICLE ON A CONFIRMED PROJECT:
                # A planned / under_construction venue is never dropped (we
                # know it's real from Wikipedia/league data). But if the news
                # article we happened to fetch turned out to be unrelated
                # (a coaching change, a lawsuit, a game recap), we must NOT
                # keep that article's link/evidence on the lead — otherwise
                # the client clicks "source" and lands on a baseball box
                # score. Scrub the article-derived fields back to the honest
                # "confirmed, no relevant news" state. Stage 3's web search
                # may still fill in real current evidence afterwards.
                if is_confirmed_project and article_is_bad and not lead.get("_drop"):
                    print(f"         ⚠️  article irrelevant — keeping confirmed "
                          f"lead, clearing bad source", flush=True)
                    status_txt = lead.get("venue_status","").replace("_"," ")
                    lead["evidence"] = ("Confirmed via league/Wikipedia source — "
                                        "no relevant news article found yet.")
                    lead["whats_happening"] = (f"{lead['venue_name']} — confirmed "
                                               f"{status_txt} project.")
                    lead["source"] = ""
                    lead["source_name"] = "League/Wikipedia source"

                # Deterministically re-derive likelihood → engagement →
                # score, in that order, rather than trusting the LLM's own
                # values. build_lead already did this, but the update()
                # above may have merged a fresh tier from the analysis, so
                # we recompute here to stay consistent with the final tier.
                if not lead.get("_drop"):
                    # TRIVIAL-PROJECT DROP: an existing venue whose only
                    # "project" is minor works — a sewer/culvert line, a
                    # videoboard/scoreboard swap, LED/audio/wifi upgrades,
                    # turf or seating refresh — is not a railing/structural
                    # opportunity. These slip past the rescue filter because
                    # their own news article WAS about the venue (so
                    # venue_confirmed=true, no rescue), they're just not
                    # substantial. Drop existing-venue leads like this.
                    if (lead.get("venue_status","existing") == "existing"
                            and _is_trivial_project(
                                lead.get("whats_happening",""),
                                lead.get("evidence",""))):
                        print(f"         ❌ DROPPED — only a minor/non-structural "
                              f"project (sewer/videoboard/upgrade)", flush=True)
                        dropped_not_confirmed.append(lead["venue_name"])
                        lead["_drop"] = True

                if not lead.get("_drop"):
                    final_tier = lead.get("signal_tier") or 1
                    lead["likelihood"] = derive_likelihood(
                        final_tier, lead.get("venue_status", "existing"),
                        lead.get("likelihood"))
                    lead["engagement"] = derive_engagement(
                        final_tier, lead["likelihood"])
                    lead["score"] = compute_score(
                        final_tier,
                        lead.get("capacity"),
                        lead.get("venue_status", "existing"),
                        lead.get("likelihood"),
                    )

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
    # STAGE 3: Claude web-search current-status cross-check, on every surviving
    # lead. Runs after the drop-check (no point verifying leads we're
    # about to discard) and before sorting (a tier change affects rank).
    # -----------------------------------------------------------
    if ENABLE_WEB_SEARCH_VERIFICATION:
        print(f"\n[STEP 3C] Verifying current status for {len(all_leads)} leads via Claude web search...", flush=True)
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
                        lead["source_name"] = "Web search (verified)"
                    # Tier moved forward → re-derive likelihood, engagement,
                    # and score for the new tier (same deterministic path as
                    # the deep-analysis loop). A jump to Tier 4 becomes
                    # too_late automatically via derive_engagement.
                    lead["likelihood"] = derive_likelihood(
                        new_tier, lead.get("venue_status", "existing"),
                        lead.get("likelihood"))
                    lead["engagement"] = derive_engagement(new_tier, lead["likelihood"])
                    lead["score"] = compute_score(
                        new_tier, lead.get("capacity"),
                        lead.get("venue_status", "existing"), lead.get("likelihood"),
                    )
                    tier_updates += 1
                    print(f"  ⚠️  T{old_tier}→T{new_tier} ({verification.get('reasoning','')[:60]})", flush=True)
                else:
                    print("  (no change)", flush=True)
            else:
                print("  (no change)", flush=True)
            time.sleep(0.3)
        print(f"  Stage 3 tier updates: {tier_updates}/{len(all_leads)}", flush=True)

    # FINAL NARRATIVE CLEANUP — after all tier/evidence updates (deep loop,
    # rescue, Stage 3), scrub any lead whose whats_happening / evidence still
    # carries "this article is actually about something else" text. Runs on
    # every survivor so a client never sees a real Act Now lead described as
    # "the article discusses a player trade".
    cleaned = 0
    for lead in all_leads:
        before = (lead.get("whats_happening",""), lead.get("evidence",""))
        _clean_lead_narrative(lead)
        if (lead.get("whats_happening",""), lead.get("evidence","")) != before:
            cleaned += 1
    if cleaned:
        print(f"  Narrative cleanup   : fixed {cleaned} lead(s) with stale "
              f"bad-article text", flush=True)

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