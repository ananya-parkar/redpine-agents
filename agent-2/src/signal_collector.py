import time
import requests
from datetime import datetime, timezone, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import NEWSAPI_KEY

# ---------------------------------------------------
# SIGNAL COLLECTOR  (NewsAPI /v2/everything)
#
# MIGRATED FROM GNews → NewsAPI.org. Only the HTTP layer changed
# (endpoint, key param, rate-limit codes); all the pipeline logic —
# priority ordering, query building, circuit breaker, confirmed_no_news
# synthetic signals, recency filtering — is IDENTICAL to before.
#
# KEY DESIGN:
#   Priority order:
#     1. planned/under_construction venues FIRST
#        (Table 1 + 2 from Wikipedia — we KNOW construction is happening)
#     2. existing venues by capacity (largest first)
#
#   Query: "Venue Name" OR "Team Name" + construction keywords
#   For planned venues: search WITHOUT extra construction keywords
#     (they're already planned — just find latest news about them)
#
#   CIRCUIT BREAKER: search_news() returns None (not []) specifically
#   when NewsAPI itself is refusing requests (429 rate limit / quota,
#   or 401 bad key, or retries exhausted) — distinct from a venue that
#   legitimately has no news. collect_signals() counts CONSECUTIVE None
#   results and stops early (default: 4 in a row) rather than burning
#   through the rest of the batch against a dead/exhausted API key.
#
# NEWSAPI NOTES vs GNews:
#   - endpoint  : /v2/everything  (was gnews.io/api/v4/search)
#   - key param : apiKey          (was token)
#   - max param : pageSize        (was max)
#   - sort param: sortBy          (was sortby)
#   - NO country= filter on /everything (GNews had country=us). We keep
#     language=en; US-relevance is already enforced downstream by the
#     LLM reasoning stage (it rejects non-US venues).
#   - rate limit shows as HTTP 429 (free tier = 100 requests/day),
#     often with JSON {"status":"error","code":"rateLimited"}.
# ---------------------------------------------------

NEWSAPI_URL    = "https://newsapi.org/v2/everything"
RECENCY_DAYS   = 90
# -----------------------------------
# TEMP LIMIT (free API)
#
# 90 -> demo mode
# None -> production mode (all venues) — set this once client provides
#         a paid NEWSAPI_KEY
# 500 -> custom limit
# -----------------------------------

DAILY_LIMIT = 90
REQUEST_DELAY  = 1.5
MAX_RETRIES    = 3

# Circuit breaker: how many CONSECUTIVE venues can fail due to NewsAPI
# itself (429 quota / rate limit / exhausted retries) before we stop
# trying entirely for the rest of this run.
MAX_API_LIMIT_FAILURES = 4

CONSTRUCTION_Q = (
    "renovation OR expansion OR construction OR upgrade OR "
    "funding OR bond OR rebuild OR architect OR RFP OR referendum OR groundbreaking"
)

def make_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0,
                  status_forcelist=[429,500,502,503,504],
                  allowed_methods=["GET"])
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

SESSION = make_session()




def _clean_venue_for_query(name: str) -> str:
    """
    Shorten long venue names for news queries.
    'Steve Spurrier-Florida Field at Ben Hill Griffin Stadium'
      → 'Ben Hill Griffin Stadium'  (take last meaningful part)
    'Donald W. Reynolds Razorback Stadium, Frank Broyles Field'
      → 'Razorback Stadium'  (take first stadium-like part)
    """
    # Split on " at " — take the part after "at" (usually the real stadium name)
    if " at " in name:
        name = name.split(" at ")[-1].strip()

    # Split on "," — take first part
    if "," in name:
        name = name.split(",")[0].strip()

    # If still too long (>50 chars), take last 2 words that sound like a stadium
    if len(name) > 50:
        words = name.split()
        # Find the stadium/field/arena keyword and take 2 words before + it
        for i, w in enumerate(words):
            if w.lower() in {"stadium","field","arena","park","dome","center","coliseum","bowl"}:
                start = max(0, i-2)
                name = " ".join(words[start:i+1])
                break
        else:
            name = " ".join(words[-3:])  # last 3 words

    return name.strip()


def build_query(venue_name: str, team: str, is_planned: bool) -> str:
    """
    Build news search query.
    Cleans long/special venue names before querying.
    """
    clean_name    = _clean_venue_for_query(venue_name)
    primary_team  = team.split(";")[0].strip() if team else ""

    # Use team name only if venue name is still too generic after cleaning
    # or if no clean name found
    if not clean_name or len(clean_name) < 5:
        clean_name = primary_team

    if is_planned:
        if primary_team and primary_team != clean_name:
            return f'("{clean_name}" OR "{primary_team}")'
        return f'"{clean_name}"'
    else:
        if primary_team and primary_team != clean_name:
            return f'("{clean_name}" OR "{primary_team}") ({CONSTRUCTION_Q})'
        return f'"{clean_name}" ({CONSTRUCTION_Q})'


def search_news(venue_name: str, team: str = "",
                is_planned: bool = False) -> list[dict] | None:
    """
    Query NewsAPI /v2/everything for a venue.

    Returns:
      list[dict]  — articles found (may be an empty list — that's a
                     normal, legitimate "no news for this venue" result)
      None        — NewsAPI itself refused the request (429 rate limit /
                     daily quota, 401 bad key, or all retries exhausted
                     on repeated 429s). Callers should treat this
                     differently from an empty list — it means the API
                     key, not the venue, is the problem.
    """
    from_date = (datetime.now() - timedelta(days=RECENCY_DAYS)
                 ).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = build_query(venue_name, team, is_planned)
    params = {
        "q":        query,
        "language": "en",
        "pageSize": 10,               # was GNews "max": 10
        "from":     from_date,
        "sortBy":   "publishedAt",    # was GNews "sortby"
        "apiKey":   NEWSAPI_KEY,      # was GNews "token"
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = SESSION.get(NEWSAPI_URL, params=params, timeout=20)
            if r.status_code == 429:
                # NewsAPI free tier: 100 req/day. 429 = rate/quota limit.
                print(f"    [NEWSAPI 429] Rate limit / daily quota reached", flush=True)
                return None  # API-level problem, not "no articles"
            if r.status_code == 401:
                print(f"    [NEWSAPI 401] Invalid or missing API key", flush=True)
                return None
            if r.status_code == 426:
                # NewsAPI returns 426 when a free key requests articles
                # older than the plan allows — treat as API-level.
                print(f"    [NEWSAPI 426] Date range not allowed on this plan", flush=True)
                return None
            r.raise_for_status()
            data = r.json()
            # NewsAPI wraps errors in a 200-ish body too sometimes:
            if data.get("status") == "error":
                code = data.get("code", "")
                if code in ("rateLimited", "maximumResultsReached",
                            "apiKeyExhausted", "apiKeyDisabled"):
                    print(f"    [NEWSAPI ERROR] {code}", flush=True)
                    return None
                print(f"    [NEWSAPI ERROR] {code}: {data.get('message','')}", flush=True)
                return []
            return data.get("articles", [])
        except requests.exceptions.Timeout:
            time.sleep(5)
        except Exception as e:
            print(f"    [NEWSAPI ERROR] {venue_name}: {e}", flush=True)
            # The urllib3 Retry adapter (status_forcelist=[429,...]) also
            # raises here once ITS internal retries are exhausted — that
            # shows up as "Max retries exceeded ... 429 error responses".
            # Treat that the same as an explicit 429: API-level, not venue-level.
            if "429" in str(e) or "Max retries exceeded" in str(e):
                return None
            return []
    # Loop ended without returning — MAX_RETRIES attempts all hit 429
    print(f"    [NEWSAPI] All retries exhausted for {venue_name} — likely rate limited", flush=True)
    return None


def collect_signals(venues: list[dict]) -> list[dict]:
    print(f"\n[STEP 2A] Collecting NewsAPI signals (last {RECENCY_DAYS} days)...", flush=True)
    total = len(venues)

    # Priority order:
    # 1. under_construction first  (Tier 3-4, procurement window)
    # 2. planned second            (Tier 1-2, engage_now window)
    # 3. existing venues by capacity
    STATUS_PRIORITY = {"under_construction": 0, "planned": 1, "existing": 2}
    sorted_venues = sorted(
        venues,
        key=lambda v: (
            STATUS_PRIORITY.get(v.get("status","existing"), 2),
            -(v.get("capacity", 0) or 0),
        )
    )

    # -----------------------------------
    # Demo mode → process first N venues
    # Production → process all venues
    # -----------------------------------

    if DAILY_LIMIT:
        batch = sorted_venues[:DAILY_LIMIT]
    else:
        batch = sorted_venues

    

    under_const = sum(1 for v in batch if v.get("status")=="under_construction")
    planned     = sum(1 for v in batch if v.get("status")=="planned")
    print(f"  Total venues        : {total}", flush=True)
    print(f"  Processing          : {len(batch)} venues", flush=True)
    print(f"  Under construction  : {under_const} (searched first, T3-4)", flush=True)
    print(f"  Planned/proposed    : {planned} (searched second, T1-2)", flush=True)

    signals   = []
    cutoff    = datetime.now(timezone.utc) - timedelta(days=RECENCY_DAYS)
    no_signal = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    api_limit_failures = 0

    for idx, v in enumerate(batch):
        vname      = v["venue_name"]
        team       = v.get("team", "") or ""
        is_planned = v.get("status","existing") in ("planned","under_construction")
        capacity   = v.get("capacity", 0) or 0

        try:
            articles = search_news(vname, team, is_planned)
        except Exception as e:
            print(f"    [SEARCH FAILED] {vname}: {e}", flush=True)

            consecutive_failures += 1

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(
                    f"\n[STOPPING] {MAX_CONSECUTIVE_FAILURES} consecutive failures detected.",
                    flush=True
                )
                break

            continue

        # CIRCUIT BREAKER: NewsAPI itself is refusing requests (quota/rate
        # limit), not "this venue has no news". Count consecutive
        # occurrences and stop trying the rest of the batch once the
        # threshold is hit — no point burning requests against a dead key.
        if articles is None:
            api_limit_failures += 1
            print(f"    [API LIMIT] {vname} — {api_limit_failures}/{MAX_API_LIMIT_FAILURES}", flush=True)
            if api_limit_failures >= MAX_API_LIMIT_FAILURES:
                remaining = len(batch) - idx - 1
                print(f"\n[STOPPING] NewsAPI quota/rate-limit hit "
                      f"{MAX_API_LIMIT_FAILURES} times in a row — "
                      f"skipping remaining {remaining} venues this run.", flush=True)
                break
            time.sleep(REQUEST_DELAY)
            continue
        else:
            api_limit_failures = 0  # any real response resets this — even []

        if not articles:
            
            # CONFIRMED projects (planned/under_construction) ALWAYS become
            # a lead, even with zero news coverage. We know they're real
            # from Wikipedia/league data — absence of news shouldn't drop
            # a guaranteed opportunity.
            if v.get("status") in ("planned","under_construction"):
                signals.append({
                    "venue_name":   vname,
                    "league":       v.get("league",""),
                    "team":         team,
                    "city":         v.get("city",""),
                    "state":        v.get("state",""),
                    "capacity":     capacity,
                    "venue_status": v.get("status","existing"),
                    "planned_year": v.get("planned_year",""),
                    "headline":     f"{vname} — confirmed {v.get('status').replace('_',' ')} project (no public news coverage yet)",
                    "description":  "",
                    "content":      "",
                    "source":       "League/Wikipedia source",
                    "url":          "",
                    "published_at": "",
                    "scraped_at":   datetime.now(timezone.utc).isoformat(),
                    "signal_type":  "confirmed_no_news",
                })
            no_signal += 1
            time.sleep(REQUEST_DELAY); continue
        consecutive_failures = 0
        kept = 0
        for article in articles:
            if kept >= 2: break
            title = article.get("title","") or ""
            desc  = article.get("description","") or ""
            if not title: continue

            pub_str = article.get("publishedAt","")
            if pub_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace("Z","+00:00"))
                    if pub_dt < cutoff: continue
                except Exception: pass

            signals.append({
                "venue_name":   vname,
                "league":       v.get("league",""),
                "team":         team,
                "city":         v.get("city",""),
                "state":        v.get("state",""),
                "capacity":     capacity,
                "venue_status": v.get("status","existing"),
                "planned_year": v.get("planned_year",""),
                "headline":     title,
                "description":  desc,
                "content":      (article.get("content","") or "")[:500],
                "source":       article.get("source",{}).get("name",""),
                "url":          article.get("url",""),
                "published_at": pub_str,
                "scraped_at":   datetime.now(timezone.utc).isoformat(),
                "signal_type":  "news",
            })
            kept += 1

        if kept == 0: no_signal += 1
        time.sleep(REQUEST_DELAY)


    venues_with = len(set(s["venue_name"] for s in signals))
    print(f"  Venues with signals : {venues_with}", flush=True)
    print(f"  Venues no signal    : {no_signal}", flush=True)
    print(f"  Total signals       : {len(signals)}", flush=True)
    return signals