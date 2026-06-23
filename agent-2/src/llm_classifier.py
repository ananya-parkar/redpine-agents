# ---------------------------------------------------
# LLM BATCH CLASSIFIER  — Stage 1 of LLM involvement
#
# Called BEFORE heuristic scoring. Sends all collected
# signals to LLM in batches of 10. LLM decides:
#   - Is this actually about venue construction?
#   - What tier is it (1-4)?
#
# This replaces keyword-based tier assignment entirely.
# Only relevant signals pass through to scoring + reasoning.
# ---------------------------------------------------

import json
import time
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

CLASSIFY_PROMPT = """
Classify each sports venue construction signal below.
Return ONLY a valid JSON array — one entry per signal, same order.
No preamble, no markdown.

[
  {
    "idx": <same index as input>,
    "relevant": <true if about actual venue construction/renovation, false otherwise>,
    "tier": <1|2|3|4>,
    "tier_label": <"Tier 1 — Early Rumor"|"Tier 2 — Funding Committed"|"Tier 3 — Design Phase"|"Tier 4 — Procurement">
  }
]

TIER DEFINITIONS:
1 = Early Rumor       — discussed/rumored, no funding confirmed
2 = Funding Committed — bonds approved, budget allocated, deal signed
3 = Design Phase      — architect or GC named, pre-construction
4 = Procurement       — construction started, nearly complete, or already open

SET relevant=false if:
- Article is about land/area NEAR the venue, not the venue itself
- Article is about a concert, game, or sports event
- Project already completed or opened before 2025
- Article just mentions venue in passing (not about construction)
- Team relocation rumors with no construction details

SET tier=4 + relevant=true if:
- Project has been under construction 2+ years
- Stadium opening in 2025-2027 (already in construction)
""".strip()


def batch_classify(signals: list[dict], batch_size: int = 10) -> list[dict]:
    """
    Send signals in batches to LLM for quick tier + relevance classification.
    Returns only relevant signals with LLM-assigned tiers.
    """
    if not signals:
        return []

    print(f"\n[STEP 2C] LLM batch classification ({len(signals)} signals)...", flush=True)
    classified = {}   # idx → {relevant, tier, tier_label}

    batches = [signals[i:i+batch_size] for i in range(0, len(signals), batch_size)]

    for b_idx, batch in enumerate(batches):
        # Build compact batch payload
        batch_payload = []
        for s in batch:
            batch_payload.append({
                "idx":          s.get("_batch_idx"),
                "venue":        s.get("venue_name", ""),
                "headline":     s.get("headline", ""),
                "description":  (s.get("description", "") or "")[:200],
                "published_at": s.get("published_at", "")[:10],
            })

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    temperature=0.0,
                    max_tokens=800,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": CLASSIFY_PROMPT},
                        {"role": "user",   "content":
                            "Classify these signals:\n" +
                            json.dumps(batch_payload, ensure_ascii=True)}
                    ]
                )
                raw  = resp.choices[0].message.content.strip()
                # Response might be {"results": [...]} or just [...]
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    results = next(iter(parsed.values()))  # grab first value
                else:
                    results = parsed

                for item in results:
                    classified[item["idx"]] = {
                        "relevant":   item.get("relevant", True),
                        "tier":       item.get("tier", 1),
                        "tier_label": item.get("tier_label", "Tier 1 — Early Rumor"),
                    }
                break   # success

            except Exception as e:
                err = str(e)
                if "429" in err or "rate_limit" in err.lower():
                    wait = 60 * (attempt + 1)
                    print(f"\n  [RATE LIMIT] Waiting {wait}s...", flush=True)
                    time.sleep(wait)
                    continue
                print(f"\n  [CLASSIFY ERROR] batch {b_idx}: {e}", flush=True)
                # On error — mark all in batch as relevant, tier=1 (safe default)
                for s in batch:
                    classified[s["_batch_idx"]] = {"relevant": True, "tier": 1,
                                                    "tier_label": "Tier 1 — Early Rumor"}
                break

        time.sleep(0.5)   # brief pause between batches

        done = (b_idx + 1) * batch_size
        print(f"  Classified {min(done, len(signals))}/{len(signals)}", end="\r", flush=True)

    # Apply classifications back to signals
    relevant_signals = []
    removed = 0
    for s in signals:
        cls = classified.get(s.get("_batch_idx"), {"relevant": True, "tier": 1,
                                                    "tier_label": "Tier 1 — Early Rumor"})
        if not cls["relevant"]:
            removed += 1
            continue
        s["signal_tier"]  = cls["tier"]
        s["tier_label"]   = cls["tier_label"]
        relevant_signals.append(s)

    print(f"\n  Relevant signals   : {len(relevant_signals)}", flush=True)
    print(f"  Filtered by LLM    : {removed} (not venue construction)", flush=True)
    return relevant_signals


def classify_signals(signals: list[dict]) -> list[dict]:
    """Add batch index, classify, return relevant signals with tiers."""
    for i, s in enumerate(signals):
        s["_batch_idx"] = i
    return batch_classify(signals)