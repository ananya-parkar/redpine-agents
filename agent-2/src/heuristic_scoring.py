from datetime import datetime, timezone

# ---------------------------------------------------
# WHAT THIS FILE DOES
#
# Scores every signal on four axes and combines them
# into a single opportunity_score. The ranked output
# feeds the LLM — we only send the top N to save cost.
#
# AXES:
#   Tier score      (40 pts max) — Tier 1 = 40, Tier 4 = 10
#   Venue size      (35 pts max) — based on capacity
#   Recency         (25 pts max) — based on published_at date
#   Status bonus    (15 pts)     — venue is a planned / under-
#                                  construction build (confirmed
#                                  by Wikipedia). New builds are
#                                  prime railing/platform targets.
# ---------------------------------------------------

TIER_SCORE_MAP = {1: 40, 2: 30, 3: 20, 4: 10}

def score_tier(tier) -> int:
   try:
       return TIER_SCORE_MAP.get(int(tier), 0)
   except (ValueError, TypeError):
       return 0

def score_capacity(capacity) -> int:
   try:
       cap = int(str(capacity).replace(",", "").strip())
       if cap > 60000: return 35
       if cap > 40000: return 28
       if cap > 20000: return 18
       return 8
   except Exception:
       return 10   # unknown capacity — neutral default

def score_recency(published_at: str) -> int:
   try:
       pub_dt   = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
       days_ago = (datetime.now(timezone.utc) - pub_dt).days
       if days_ago <= 7:  return 25
       if days_ago <= 14: return 18
       if days_ago <= 30: return 10
       if days_ago <= 60: return 5
       return 1
   except Exception:
       return 0

def score_status(venue_status: str) -> int:
   # A planned / under-construction venue is a strong opportunity —
   # but only when a news signal also exists (this only runs on
   # signals that already passed the collector, so the article
   # confirms the project is live).
   if venue_status and venue_status != "existing":
       return 15
   return 0

def score_signals(signals: list[dict]) -> list[dict]:
   print("\n[STEP 3] Scoring signals...", flush=True)
   for s in signals:
       s["tier_score"]        = score_tier(s.get("signal_tier", 4))
       s["venue_size_score"]  = score_capacity(s.get("capacity", ""))
       s["recency_score"]     = score_recency(s.get("published_at", ""))
       s["status_bonus"]      = score_status(s.get("venue_status", "existing"))
       s["opportunity_score"] = (
           s["tier_score"]
           + s["venue_size_score"]
           + s["recency_score"]
           + s["status_bonus"]
       )
   signals.sort(key=lambda x: (-x["opportunity_score"], x.get("signal_tier") or 99))
   for i, s in enumerate(signals, 1):
       s["rank"] = i
   print(f"  Scored {len(signals)} signals", flush=True)
   return signals