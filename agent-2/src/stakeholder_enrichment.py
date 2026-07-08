import re
import json
import time
import requests
from urllib.parse import urlparse
from llm_client import call_llm_json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import SEARCHAPI_KEY
from tuning_prompt import build_tuning_block
from db_writer import get_active_tuning_triggers

# ---------------------------------------------------
# STAKEHOLDER ENRICHMENT — SearchAPI only
#
# WHY SearchAPI NOT article text:
#   Articles cover the news event, not the full project team.
#   SearchAPI lets us specifically hunt for:
#     - "[venue] architect"
#     - "[venue] general contractor"
#     - "[venue] construction company"
#     - "[venue] facilities director"
#     - "[venue] procurement officer"
#
# WEBSITE: extracted from the search result URL whose domain matches
#   the stakeholder's organization name (e.g. "Gensler" → gensler.com
#   found among the result URLs) — not guessed, only if present.
#
# EMAIL: a dedicated follow-up SearchAPI query per organization
#   ("{org} contact email"), regex-scanned for an email address in
#   the returned snippets. Left blank if nothing concrete is found —
#   never fabricated (e.g. never invented as info@domain.com).
#
# Runs for ALL relevant leads (engage_now + monitor)
#
# CIRCUIT BREAKER: searchapi_query() returns None (not []) when
# SearchAPI itself fails (429 rate limit, network error) — distinct
# from a query that legitimately found zero results. enrich_stakeholders()
# counts CONSECUTIVE leads where EVERY query failed at the API level
# and stops early (default: 4 in a row) rather than burning through
# the rest of the leads against a dead/exhausted key.
# ---------------------------------------------------

SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"
EMAIL_REGEX   = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Generic domains that are never an organization's own website
GENERIC_DOMAINS = {
    "wikipedia.org","linkedin.com","facebook.com","twitter.com","x.com",
    "instagram.com","youtube.com","bing.com","google.com","yelp.com",
    "indeed.com","glassdoor.com","crunchbase.com","bloomberg.com",
    "espn.com","si.com","nytimes.com","forbes.com",
}

# How many CONSECUTIVE leads can have every SearchAPI query fail at the
# API level (429 / network error) before we stop enrichment entirely
# for the rest of this run.
MAX_API_LIMIT_FAILURES = 4

def make_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0,
                  status_forcelist=[429,500,502,503,504],
                  allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    return s

SESSION = make_session()

SEARCH_TEMPLATES = [
    "{venue} {team} architect",
    "{venue} {team} general contractor construction company",
    "{venue} facilities director procurement",
    "{venue} stadium construction project manager",
    "{city} {team} stadium developer owner",
]

EXTRACT_PROMPT = """
You are extracting stakeholder contacts from search results about a stadium/arena project.

Extract ONLY people and companies explicitly named in the search results below.
Do NOT invent names. Do NOT guess.

Return ONLY valid JSON:
{
  "stakeholders": [
    {
      "name": <exact name from search results>,
      "type": <"Architect"|"GC"|"Developer"|"Owner"|"City Official"|"Facilities Director"|"Procurement"|"Other">,
      "organization": <company/org name if mentioned>,
      "title": <job title if mentioned>,
      "relevance": <"high"|"medium"|"low">
    }
  ]
}

Rules:
- Only names that appear in the text below
- Skip generic company names without a person (unless they're the GC/Architect firm)
- Prioritize: Architects, GCs, Facilities Directors, Procurement officers
- Include firm names for Architect and GC even without a person name
""".strip()


def searchapi_query(query: str) -> list[dict] | None:
    """
    Returns:
      list[dict]  — results found (may be an empty list — that's a
                     normal, legitimate "nothing matched this query"
                     result)
      None        — SearchAPI itself failed (429 rate limit, the
                     urllib3 Retry adapter exhausting its retries on
                     repeated 429s, a network error, etc). Callers
                     should treat this differently from an empty list
                     — it means the API/key is the problem, not the query.
    """
    if not SEARCHAPI_KEY:
        return []
    try:
        r = SESSION.get(SEARCHAPI_URL, params={
            "engine":  "google",
            "q":       query,
            "num":     5,
            "api_key": SEARCHAPI_KEY,
        }, timeout=15)
        if r.status_code == 429:
            print(f"      [SEARCHAPI] 429 rate limited", flush=True)
            return None
        r.raise_for_status()
        results = r.json().get("organic_results", [])
        return [{"title":x.get("title",""),
                 "snippet":x.get("snippet",""),
                 "url":x.get("link","")}
                for x in results]
    except Exception as e:
        print(f"      [SEARCHAPI] {e}", flush=True)
        # This is also where the urllib3 Retry adapter's exhausted-429
        # error lands (e.g. "Max retries exceeded ... too many 429 error
        # responses") — treat it the same as an explicit 429 above.
        return None


def build_search_results(lead: dict) -> list[dict] | None:
    """
    Run targeted SearchAPI queries, return raw result list (not just text).

    Returns None if EVERY query for this lead failed at the API level
    (429 / network error) — distinct from a lead that legitimately has
    zero search results, so the caller can tell "SearchAPI is down" from
    "nothing exists for this venue".
    """
    venue = lead.get("venue_name","")
    team  = lead.get("team","").split(";")[0].strip()
    city  = lead.get("city","")

    all_results = []
    api_failures = 0
    for template in SEARCH_TEMPLATES:
        query = template.format(venue=venue, team=team, city=city).strip()
        results = searchapi_query(query)
        if results is None:
            api_failures += 1
        else:
            all_results.extend(results)
        time.sleep(0.5)

    if api_failures == len(SEARCH_TEMPLATES):
        return None
    return all_results


def _domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.replace("www.","")
    except Exception:
        return ""


def _org_words(org: str) -> list[str]:
    """Significant words from an org name, for matching against domains."""
    stop = {"inc","llc","co","company","corp","corporation","group",
            "architects","architecture","construction","contracting",
            "the","and","&","of","city","department","authority"}
    words = re.findall(r"[a-zA-Z]+", org.lower())
    return [w for w in words if w not in stop and len(w) > 2]


def find_website(org: str, results: list[dict]) -> str:
    """
    Find a result URL whose domain matches the organization name.
    Returns the URL (not just domain) if confident, else "".
    """
    if not org.strip(): return ""
    words = _org_words(org)
    if not words: return ""

    for r in results:
        domain = _domain_of(r.get("url",""))
        if not domain or domain in GENERIC_DOMAINS: continue
        # Match if any significant org word appears in the domain
        if any(w in domain for w in words):
            return r["url"]
    return ""


def find_contact_email(org: str) -> str:
    """
    Dedicated follow-up search for an organization's contact email.
    Returns an email address if found in snippets, else "" — never
    fabricated (no info@domain.com guessing).
    """
    if not org.strip() or not SEARCHAPI_KEY:
        return ""
    query   = f'"{org}" contact email'
    results = searchapi_query(query)
    if not results:
        return ""
    for r in results:
        text = f"{r.get('title','')} {r.get('snippet','')}"
        m = EMAIL_REGEX.search(text)
        if m:
            email = m.group(0)
            # Skip obviously generic/placeholder matches
            if not any(x in email.lower() for x in ("example.com","sentry.io","wixpress.com")):
                return email
    return ""


def extract_stakeholders(lead: dict, search_results: list[dict], tuning_block: str = "") -> list[dict]:
    """LLM extracts stakeholders from SearchAPI results."""
    if not search_results:
        return []
    try:
        context = "\n\n".join(
            f"TITLE: {r['title']}\nSNIPPET: {r['snippet']}\nURL: {r['url']}"
            for r in search_results
        )
        prompt_context = (
            f"Venue: {lead.get('venue_name','')}\n"
            f"Team: {lead.get('team','')}\n"
            f"City: {lead.get('city','')}, {lead.get('state','')}\n"
            f"League: {lead.get('league','')}\n"
            f"Project: {lead.get('whats_happening','')}\n\n"
            f"Search results:\n{context[:3000]}"
        )
        result = call_llm_json(
            system=EXTRACT_PROMPT + tuning_block,
            user_content=prompt_context,
            max_tokens=800, temperature=0.0,
        )
        stakes = result.get("stakeholders", [])
        return [s for s in stakes
                if s.get("name","").strip()
                and s.get("relevance","") != "low"]
    except Exception as e:
        print(f"      [LLM ERROR] {e}", flush=True)
        return []


def enrich_stakeholders(all_leads: list[dict],
                        act_now:   list[dict]) -> tuple[list, list, list]:
    """
    Enrich stakeholders via SearchAPI for engage_now + monitor leads.
    Returns updated all_leads, act_now, and flat stakeholder_rows list.
    """
    if not SEARCHAPI_KEY:
        print("\n[STEP 4] Skipping stakeholders — no SEARCHAPI_KEY", flush=True)
        return all_leads, act_now, []

    to_enrich = [l for l in all_leads
                 if l.get("engagement") in ("engage_now","monitor")]

    print(f"\n[STEP 4] Stakeholder enrichment via SearchAPI "
          f"({len(to_enrich)} leads)...", flush=True)

    # Same tuning-trigger mechanism as reasoning_agent.py, but scoped to
    # "stakeholder" — e.g. a "wrong owner" pattern flagged 3+ times by
    # Matthew/Anshi targets THIS prompt, not reasoning_agent.py's (those
    # are two separate LLM calls). See tuning_prompt.py for the scoping.
    active_triggers = get_active_tuning_triggers()
    stakeholder_tuning_block = build_tuning_block(active_triggers, scope="stakeholder")
    if stakeholder_tuning_block:
        print(f"  [TUNING] Injecting {stakeholder_tuning_block.count('Pattern:')} "
              f"known false-positive pattern(s) into stakeholder prompt", flush=True)

    stakeholder_rows = []
    api_limit_failures = 0

    for i, lead in enumerate(to_enrich, 1):
        vname = lead.get("venue_name","")
        eng   = lead.get("engagement","")
        print(f"  [{i:02d}/{len(to_enrich)}] {vname[:40]} [{eng}]", flush=True)

        search_results = build_search_results(lead)

        # CIRCUIT BREAKER: SearchAPI itself is failing for every query on
        # this lead (429/network) — not "this lead has no stakeholders".
        if search_results is None:
            api_limit_failures += 1
            print(f"      [API LIMIT] SearchAPI failing — "
                  f"{api_limit_failures}/{MAX_API_LIMIT_FAILURES}", flush=True)
            if api_limit_failures >= MAX_API_LIMIT_FAILURES:
                remaining = len(to_enrich) - i
                print(f"\n  [STOPPING] SearchAPI rate/quota limit hit "
                      f"{MAX_API_LIMIT_FAILURES} times in a row — "
                      f"skipping remaining {remaining} leads this run.", flush=True)
                break
            continue
        api_limit_failures = 0  # any real response resets this — even []

        if not search_results:
            print(f"      No search results", flush=True)
            continue

        stakes = extract_stakeholders(lead, search_results, tuning_block=stakeholder_tuning_block)
        print(f"      → {len(stakes)} stakeholders found", flush=True)

        if stakes:
            # Resolve website + email per unique organization (avoid
            # repeating the email search for the same org twice in one lead)
            org_cache = {}
            for s in stakes:
                org = (s.get("organization") or "").strip()
                if not org:
                    s["_website"] = ""; s["_email"] = ""
                    continue
                if org not in org_cache:
                    website = find_website(org, search_results)
                    email   = find_contact_email(org)
                    org_cache[org] = (website, email)
                    time.sleep(0.5)
                s["_website"], s["_email"] = org_cache[org]

            lead["stakeholders_raw"] = json.dumps(stakes)

            for s in stakes:
                stakeholder_rows.append({
                    "venue_name":      vname,
                    "league":          lead.get("league",""),
                    "team":            lead.get("team",""),
                    "signal_tier":     lead.get("signal_tier"),
                    "engagement":      eng,
                    "stakeholder_name":s.get("name",""),
                    "title":           s.get("title",""),
                    "organization":    s.get("organization",""),
                    "type":            s.get("type",""),
                    "website":         s.get("_website",""),
                    "contact_email":   s.get("_email",""),
                    "notes":           s.get("relevance",""),
                })

        time.sleep(1.0)

    found_website = sum(1 for r in stakeholder_rows if r["website"])
    found_email   = sum(1 for r in stakeholder_rows if r["contact_email"])
    print(f"\n  Total stakeholders  : {len(stakeholder_rows)}", flush=True)
    print(f"  With website        : {found_website}/{len(stakeholder_rows)}", flush=True)
    print(f"  With email          : {found_email}/{len(stakeholder_rows)}", flush=True)

    lead_map = {l["venue_name"]: l for l in all_leads}
    act_now  = [lead_map.get(l["venue_name"], l) for l in act_now]

    return all_leads, act_now, stakeholder_rows