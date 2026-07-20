import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from config import KEYWORDS
import os
from dotenv import load_dotenv
load_dotenv(override=True)

# ---------------------------------------------------
# CITY COUNCIL MONITOR — Tier 2 Signal Source
#
# City council agendas = best source for Tier 2 signals:
#   bond votes, budget approvals, capital improvement
#   programs, stadium authority decisions.
#
# SOURCE A — LegiStar API (primary)
#   Free, no key. Covers 100+ US cities.
#   Returns agenda items from last 30 days.
#   Filter for venue name + funding/construction keywords.
#
# SOURCE B — Google News RSS (fallback)
#   For cities not on LegiStar.
#   Searches "{venue} city council bond funding approved"
#
# signal_tier = None — LLM assigns tier in reasoning_agent
#
# BUG FIX (this version):
#   RSS fallback previously never actually ran for cities whose
#   LegiStar client_id was invalid/unreachable — `rss_cities =
#   rss_cities | failed` was computed but never fed into
#   get_rss_signals(), which was instead called with
#   `legistar_cities - set()` (== legistar_cities). That meant every
#   city listed in LEGISTAR_CITIES was skipped from RSS regardless of
#   whether its LegiStar call actually succeeded — silently dropping
#   government/funding signals for any city with a bad/nonexistent
#   LegiStar client code (Chicago, Dallas, Houston, Charlotte, etc. all
#   return HTTP 500 for an invalid client — LegiStar has no 404 for
#   this, so a bad client code looks identical to a real server error).
#   Fixed in get_city_council_signals(): `rss_skip = legistar_cities -
#   failed`, so only cities that ACTUALLY succeeded on LegiStar are
#   skipped from the RSS pass.
#
# LOGGING CLEANUP (this version):
#   fetch_legistar()/get_legistar_signals() no longer print one ERROR
#   line per failing city. Failures are collected silently and reported
#   as a single summary line ("[LEGISTAR] N/32 cities returned usable
#   signals" + one line listing which cities fell back to RSS).
# ---------------------------------------------------

LEGISTAR_BASE = os.getenv("LEGISTAR_BASE")
GNEWS_RSS     = os.getenv("GNEWS_RSS")
LOOKBACK_DAYS = 30

# LegiStar client IDs for major US cities with venues
LEGISTAR_CITIES = {
    "new york":       "nyc",
    "los angeles":    "lacity",
    "chicago":        "chicago",
    "houston":        "houston",
    "phoenix":        "phoenix",
    "philadelphia":   "philadelphia",
    "san antonio":    "sanantonio",
    "dallas":         "dallas",
    "san francisco":  "sfgov",
    "seattle":        "seattle",
    "denver":         "denver",
    "boston":         "boston",
    "nashville":      "nashville",
    "portland":       "portland",
    "las vegas":      "lasvegas",
    "memphis":        "memphis",
    "louisville":     "louisville",
    "milwaukee":      "milwaukee",
    "sacramento":     "sacramento",
    "kansas city":    "kansascity",
    "indianapolis":   "indianapolis",
    "columbus":       "columbus",
    "charlotte":      "charlotte",
    "raleigh":        "raleigh",
    "minneapolis":    "minneapolis",
    "pittsburgh":     "pittsburgh",
    "cincinnati":     "cincinnati",
    "cleveland":      "cleveland",
    "tampa":          "tampa",
    "orlando":        "orlando",
    "buffalo":        "buffalo",
    "richmond":       "richmond",
    "san jose":       "sanjose",
    "san diego":      "sandiego",
    "oakland":        "oakland",
    "fort worth":     "fortworth",
    "arlington":      "arlington",
    "miami":          "miami",
    "st. paul":       "stpaul",
    "oklahoma city":  "oklahomacity",
    "salt lake city": "saltlakecity",
    "new orleans":    "neworleans",
    "jacksonville":   "jacksonville",
    "detroit":        "detroit",
    "baltimore":      "baltimore",
    "washington":     "dc",
    "hartford":       "hartford",
    "newark":         "newark",
    "plano":          "plano",
    "glendale":       "glendale",
    "inglewood":      "inglewood",
    "santa clara":    "santaclara",
    "green bay":      "greenbay",
}

# Venue-related terms to match in agenda items
VENUE_TERMS = [
    "stadium","arena","ballpark","coliseum","amphitheater",
    "convention center","civic center","sports complex","fieldhouse"
]

# Funding/construction keywords for filtering
GOVT_KEYWORDS = [
    "bond","funding","appropriation","capital improvement","renovation",
    "construction","referendum","stadium authority","naming rights",
    "lease","financing","infrastructure","public financing",
    "budget allocation","CIP","certificate of participation","TIF",
    "tax increment","revenue bond","general obligation"
]

ALL_KEYWORDS = list(set(KEYWORDS + GOVT_KEYWORDS))


def make_signal(venue: dict, headline: str, description: str,
                source: str, url: str, published_at: str,
                signal_source: str) -> dict | None:
    full_text = f"{headline} {description}"
    matched   = [kw for kw in ALL_KEYWORDS if kw.lower() in full_text.lower()]
    if not matched:
        return None

    return {
        "venue_name":       venue.get("venue_name",""),
        "league":           venue.get("league",""),
        "team":             venue.get("team",""),
        "city":             venue.get("city",""),
        "state":            venue.get("state",""),
        "capacity":         venue.get("capacity",""),
        "venue_status":     venue.get("status","existing"),
        "headline":         headline[:200],
        "description":      description[:500],
        "content":          "",
        "source":           f"{signal_source} · {source}",
        "url":              url,
        "published_at":     published_at,
        "scraped_at":       datetime.now(timezone.utc).isoformat(),
        "signal_tier":      None,   # LLM assigns
    }


def text_matches_venue(text: str, venue_name: str) -> bool:
    """
    Match strictly on the venue's own name. The previous version fell back
    to generic terms like "stadium"/"arena" when the name wasn't found,
    which caused unrelated agenda items (e.g. "stadium authority formed")
    to get attributed to whichever venue in that city happened to be
    iterated first — regardless of whether that venue was mentioned at all.
    """
    return venue_name.lower() in text.lower()


# ── LegiStar ─────────────────────────────────────────────────────

def fetch_legistar(client_id: str) -> list[dict] | None:
    """
    Returns:
      list[dict] — matters found (may be empty — a valid client with
                    genuinely no recent activity)
      None       — the client_id itself is invalid/unreachable (LegiStar
                    returns 500 for a bad client code instead of 404, so
                    we can't tell "no data" from "wrong city" any other
                    way). Callers should treat this as a permanent
                    failure for this client, not a transient one.
    """
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
    headers = {"User-Agent": "StadiumLeadGen/1.0"}
    base = f"{LEGISTAR_BASE}/{client_id}/Matters"

    try:
        url = (f"{base}?$filter=MatterLastModifiedUtc ge datetime'{since_str}'"
               f"&$top=200&$orderby=MatterLastModifiedUtc desc")
        r = requests.get(url, timeout=15, headers=headers)
        if r.status_code == 200:
            return r.json()
        # Fallback: simple query (some LegiStar instances reject the
        # $filter clause but work fine without it)
        r2 = requests.get(f"{base}?$top=200", timeout=15, headers=headers)
        if r2.status_code != 200:
            # Invalid/unreachable client — don't print here, the caller
            # aggregates these into one summary line instead of one
            # line per city.
            return None
        cutoff = since
        matters = []
        for m in r2.json():
            dt_str = m.get("MatterLastModifiedUtc","") or ""
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z","+00:00"))
                if dt >= cutoff: matters.append(m)
            except Exception:
                matters.append(m)
        return matters
    except Exception:
        # Network-level failure (timeout, DNS, etc.) — also treated as
        # "this client failed", same as an invalid client code. No
        # per-city print; summarized by the caller.
        return None


def get_legistar_signals(venues_by_city: dict) -> tuple[list[dict], set]:
    """
    Returns (signals, failed) where `failed` is the set of city keys
    whose LegiStar client_id is invalid/unreachable OR returned zero
    matches for our venues — these should fall back to RSS.
    """
    signals, failed = [], set()

    for city, city_venues in venues_by_city.items():
        client_id = LEGISTAR_CITIES.get(city)
        if not client_id:
            continue

        matters = fetch_legistar(client_id)

        if matters is None:
            # Invalid client / unreachable — always falls back to RSS
            failed.add(city)
            time.sleep(0.3)
            continue

        if not matters:
            # Valid client, just nothing in the lookback window
            failed.add(city)
            time.sleep(0.3)
            continue

        found = 0
        for matter in matters:
            title  = matter.get("MatterTitle","") or ""
            body   = matter.get("MatterBodyName","") or ""
            mtype  = matter.get("MatterTypeName","") or ""
            status = matter.get("MatterStatusName","") or ""
            file_n = matter.get("MatterFile","") or ""
            mod_dt = matter.get("MatterLastModifiedUtc","") or ""
            desc   = f"{mtype} · {body} · Status: {status} · File: {file_n}"

            for venue in city_venues:
                if not text_matches_venue(f"{title} {desc}", venue["venue_name"]):
                    continue
                try:
                    pub = datetime.fromisoformat(mod_dt.replace("Z","+00:00")).isoformat()
                except Exception:
                    pub = datetime.now(timezone.utc).isoformat()

                mid = matter.get("MatterId","")
                url = f"https://legistar.com/gateway.aspx?m=l&id={mid}" if mid else ""
                sig = make_signal(venue, title, desc,
                                  f"LegiStar / {city.title()} City Council",
                                  url, pub, "LegiStar")
                if sig:
                    signals.append(sig); found += 1; break

        if found == 0:
            failed.add(city)
        time.sleep(0.3)

    # ONE summary line instead of one ERROR line per city.
    ok_count = len(venues_by_city) - len(failed)
    print(f"    [LEGISTAR] {ok_count}/{len(venues_by_city)} cities returned "
          f"usable signals", flush=True)
    if failed:
        print(f"    [LEGISTAR] {len(failed)} city(ies) had no client match / "
              f"no data → falling back to RSS: {', '.join(sorted(failed))}",
              flush=True)

    return signals, failed


# ── Google News RSS fallback ──────────────────────────────────────

def fetch_gnews_rss(query: str) -> list[dict]:
    url = f"{GNEWS_RSS}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent":"StadiumLeadGen/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items = []
        for item in root.findall(".//item"):
            title = item.findtext("title","")
            link  = item.findtext("link","")
            desc  = item.findtext("description","")
            pub   = item.findtext("pubDate","")
            try:
                from email.utils import parsedate_to_datetime
                pub_iso = parsedate_to_datetime(pub).isoformat()
            except Exception:
                pub_iso = datetime.now(timezone.utc).isoformat()
            items.append({"title":title,"link":link,"description":desc,"published":pub_iso})
        return items
    except Exception as e:
        print(f"    [RSS ERROR] {e}", flush=True)
        return []


def get_rss_signals(venues_by_city, skip_cities):
    signals = []
    for city, city_venues in venues_by_city.items():
        if city in skip_cities: continue
        for venue in city_venues:
            query = (f'"{venue["venue_name"]}" '
                     f'("city council" OR "bond" OR "referendum" OR "funding" '
                     f'OR "stadium authority" OR "capital improvement" OR "approved")')
            items = fetch_gnews_rss(query)
            kept = 0
            for item in items:
                if kept >= 3: break     # cap per venue, same idea as NewsAPI
                sig = make_signal(venue, item["title"], item["description"],
                                  "Google News RSS", item["link"],
                                  item["published"], "Google News RSS")
                if sig:
                    signals.append(sig); kept += 1
            time.sleep(0.3)
    return signals
# ── Main entry ────────────────────────────────────────────────────

def get_city_council_signals(venues: list[dict],
                             news_signal_venues: set = None) -> list[dict]:
    """
    news_signal_venues: set of venue_names that got GNews signals in Step 2A
    Priority:
      1. under_construction + planned  → ALWAYS check (confirmed projects)
      2. existing with GNews signal    → check (showing activity)
      3. existing no GNews             → SKIP (no activity)
    """
    print("\n[STEP 2B] City council / government signals (LegiStar + RSS)...", flush=True)

    news_signal_venues = news_signal_venues or set()

    # Filter venues to check
    priority_venues = [
        v for v in venues
        if v.get("status") in ("planned","under_construction")   # always
        or v.get("venue_name") in news_signal_venues             # had GNews signal
    ]

    skipped = len(venues) - len(priority_venues)
    print(f"  Venues to check     : {len(priority_venues)} "
          f"(skipped {skipped} existing with no GNews signal)", flush=True)

    if not priority_venues:
        print("  No priority venues — skipping LegiStar", flush=True)
        return []

    # Group by city
    venues_by_city: dict[str, list] = {}
    for v in priority_venues:
        city_key = v.get("city","").lower().strip()
        if city_key:
            venues_by_city.setdefault(city_key, []).append(v)

    legistar_cities = {c for c in venues_by_city if c in LEGISTAR_CITIES}
    rss_only_cities = set(venues_by_city.keys()) - legistar_cities

    print(f"  Cities with LegiStar : {len(legistar_cities)}", flush=True)
    print(f"  Cities using RSS only: {len(rss_only_cities)}", flush=True)

    all_signals = []
    failed = set()   # always defined, even if legistar_cities is empty

    # LegiStar
    if legistar_cities:
        legistar_sigs, failed = get_legistar_signals(
            {c: venues_by_city[c] for c in legistar_cities}
        )
        all_signals.extend(legistar_sigs)
        print(f"  LegiStar signals     : {len(legistar_sigs)}", flush=True)

    # RSS fallback:
    #   - all cities that were never on LegiStar to begin with, PLUS
    #   - LegiStar cities that failed (invalid client / no data)
    #   Skip ONLY the LegiStar cities that actually succeeded.
    rss_skip = legistar_cities - failed
    rss_sigs = get_rss_signals(venues_by_city, rss_skip)
    all_signals.extend(rss_sigs)
    print(f"  RSS signals          : {len(rss_sigs)}", flush=True)
    print(f"  Govt signals total   : {len(all_signals)}", flush=True)
    return all_signals