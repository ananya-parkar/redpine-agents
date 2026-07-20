import time
from datetime import datetime

from reasoning_agent import (
    verify_current_status, derive_likelihood, derive_engagement, compute_score,
)
from db_writer import get_stale_leads_for_refresh, upsert_leads

# ---------------------------------------------------
# STALE LEAD REFRESHER
#
# THE GAP THIS FIXES:
#   run_reasoning() (and its Stage 3 web-search verification) only ever
#   runs on the SUBSET of leads that got a fresh NewsAPI/LegiStar signal
#   THIS run. A lead sitting in the DB from 3 weeks ago whose project
#   quietly progressed (funding got approved, an architect got hired)
#   but which had no NEW article this run never gets re-checked — its
#   tier/score/engagement stay frozen at whatever they were on the day
#   it was last detected, even though the Excel/Dashboard keeps showing
#   it as "current" (get_leads_for_excel reads all active leads from the
#   last 30 days, not just today's run).
#
# WHAT THIS DOES:
#   After today's run_reasoning() + upsert_leads() have completed, pick
#   up to REFRESH_LIMIT active (non-archived, non-too_late) leads that
#   were NOT part of today's detected leads, prioritized by whichever
#   were verified longest ago. Run the same verify_current_status() web
#   search used in Stage 3 on each, and persist any tier changes.
#
#   REFRESH_LIMIT keeps the added web-search cost bounded and rotates
#   through the whole active-lead backlog over multiple runs rather than
#   either hammering the same leads every day or never touching them.
#
# ALIAS-SYNC FIX (this version):
#   db_writer._row_to_lead() emits BOTH naming conventions for the same
#   field — e.g. "engagement" AND "engagement_action", "score" AND
#   "final_score", "likelihood" AND "project_likelihood" — both set to
#   the SAME (old) value when a lead is read back from the DB. When
#   upsert_leads() -> _normalize_lead() writes a lead back, it resolves
#   each field with `r.get("engagement_action") or r.get("engagement")`,
#   i.e. it prefers the *_action/final_*/project_* alias.
#
#   The earlier version of this file only updated the primary keys
#   ("engagement", "score", "likelihood") after a tier change — the
#   alias keys still held the OLD value carried over from the DB read.
#   Because of the "or" preference above, upsert_leads() would then
#   silently keep the STALE alias value instead of the freshly derived
#   one: the tier would update correctly in the DB, but score/likelihood
#   /engagement would NOT, even though a tier change should always
#   cascade into all three (derive_likelihood -> derive_engagement ->
#   compute_score are chained on purpose).
#
#   Fix: after recomputing likelihood/engagement/score, immediately
#   mirror them into the alias keys too, so both naming conventions
#   agree and upsert_leads() picks up the new values either way.
# ---------------------------------------------------

REFRESH_LIMIT = 15  # bump/lower this to trade off cost vs. how fast the backlog cycles


def refresh_stale_leads(run_venue_names: set) -> dict:
    """
    run_venue_names: venue_names already handled by today's run_reasoning()
                      output (i.e. the leads that DID get a fresh signal
                      this run) — these are excluded here to avoid
                      double-verifying the same lead twice in one run.

    Returns {"checked": int, "updated": int}
    """
    print(f"\n[STEP 3D] Refreshing stale DB leads not seen in today's signals...", flush=True)

    candidates = get_stale_leads_for_refresh(run_venue_names, limit=REFRESH_LIMIT)
    if not candidates:
        print("  No stale leads to refresh.", flush=True)
        return {"checked": 0, "updated": 0}

    print(f"  Checking {len(candidates)} lead(s) verified longest ago...", flush=True)

    updated_leads = []
    tier_updates  = 0

    TIER_LABELS = {
        1: "Tier 1 — Early Rumor", 2: "Tier 2 — Funding Committed",
        3: "Tier 3 — Design Phase", 4: "Tier 4 — Procurement",
    }

    for i, lead in enumerate(candidates, 1):
        print(f"  [{i:02d}/{len(candidates)}] {lead['venue_name'][:45]}", end="", flush=True)

        verification = verify_current_status(lead)

        if verification and verification.get("tier_changed"):
            old_tier = lead.get("signal_tier")
            new_tier = verification.get("new_tier")

            # Same forward-only guard as Stage 3 in reasoning_agent.py —
            # never trust the LLM alone to honor "tiers only move forward".
            valid_new_tier = (
                isinstance(new_tier, int) and new_tier in (1, 2, 3, 4)
                and isinstance(old_tier, int) and new_tier > old_tier
            )

            if valid_new_tier:
                lead["signal_tier"] = new_tier
                lead["tier_label"]  = TIER_LABELS.get(new_tier, lead.get("tier_label"))
                lead["evidence"]    = verification.get("updated_evidence") or lead.get("evidence")

                new_url = verification.get("updated_source_url")
                if new_url:
                    lead["source"]      = new_url
                    lead["source_name"] = "Web search (verified)"

                # Re-derive likelihood → engagement → score, same
                # deterministic path used everywhere else in the pipeline.
                lead["likelihood"] = derive_likelihood(
                    new_tier, lead.get("venue_status", "existing"), lead.get("likelihood"))
                lead["engagement"] = derive_engagement(new_tier, lead["likelihood"])
                lead["score"] = compute_score(
                    new_tier, lead.get("capacity"),
                    lead.get("venue_status", "existing"), lead.get("likelihood"))

                # ALIAS SYNC — see block comment at top of file. Without
                # this, upsert_leads()'s "or" fallback keeps the stale
                # engagement_action/final_score/project_likelihood values
                # that came from the DB read, and only signal_tier ends up
                # actually changing in the database.
                lead["engagement_action"]  = lead["engagement"]
                lead["final_score"]        = lead["score"]
                lead["project_likelihood"] = lead["likelihood"]

                updated_leads.append(lead)
                tier_updates += 1
                print(f"  ⚠️  T{old_tier}→T{new_tier} "
                      f"({verification.get('reasoning','')[:60]})", flush=True)
            else:
                print("  (no change)", flush=True)
        else:
            print("  (no change)", flush=True)

        time.sleep(0.3)

    if updated_leads:
        upsert_leads(updated_leads)
        print(f"  [DB] {tier_updates} stale lead(s) tier-updated and saved", flush=True)

    print(f"  Refreshed          : {len(candidates)} checked, "
          f"{tier_updates} tier change(s)", flush=True)
    return {"checked": len(candidates), "updated": tier_updates}