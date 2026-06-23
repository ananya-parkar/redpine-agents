import os
import sys
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from venue_fetcher          import get_venues
from signal_collector       import collect_signals
from city_council_monitor   import get_city_council_signals
from reasoning_agent        import run_reasoning
from stakeholder_enrichment import enrich_stakeholders
from excel_builder          import save_excel
from email_builder          import build_daily_email
from email_sender           import send_daily_report
from feedback_reader        import run as run_feedback_reader
from run_paths              import get_todays_output_file
from db_writer               import (
    init_db, db_available,
    upsert_signals, upsert_leads,
    get_archived_venues, get_pursuing_venues,
    get_bad_data_patterns, log_tuning_trigger,
    get_all_leads_for_excel, get_tier_alerts,
    purge_old_pii,
)
EMAIL_TO = os.getenv("EMAIL_TO", "")


def main():
    print("\n" + "="*60)
    print("  AGENT 2 — STADIUM CONSTRUCTION LEAD GEN")
    print("="*60)

    run_date = date.today()
    # Today's dated output file — runs/stadium_leads_YYYY-MM-DD.xlsx.
    # Each run gets its own file (instead of overwriting one fixed
    # path) so the client can compare any two days' workbooks side by
    # side. feedback_reader.py separately finds whichever PREVIOUS
    # dated file was most recently created (see run_paths.py) — that's
    # the one Matthew/Anshi actually had a chance to edit.
    output_file = get_todays_output_file()
    print(f"  Today's output   : {output_file}", flush=True)

    # ── Init DB ───────────────────────────────────────────────
    if db_available():
        init_db()

        # ── STEP 0: Process feedback from the PREVIOUS Excel ──
        # Reads whatever Pursuing/Archive/Bad Data/Passed/Watch values
        # Matthew/Anshi entered in last run's downloaded "All Leads"
        # sheet (whatever the latest dated file in runs/ is, before
        # save_excel() at STEP 6) and writes them into the DB. Must run
        # BEFORE get_archived_venues()/get_pursuing_venues() below —
        # otherwise this run would use yesterday's archived/pursuing
        # sets instead of today's. Wrapped in try/except so a missing
        # Excel file, a malformed feedback value, or any other reader
        # issue never blocks the actual pipeline run.
        print("\n[STEP 0] Reading feedback from previous run's Excel...", flush=True)
        try:
            run_feedback_reader()
        except Exception as e:
            print(f"  [WARN] Feedback reader failed: {e}", flush=True)

        archived = get_archived_venues()
        pursuing = get_pursuing_venues()
    else:
        print("  [WARN] DB not reachable — running without persistence", flush=True)
        archived, pursuing = set(), set()

    # ── STEP 1: Venues ───────────────────────────────────────
    # pd.read_html → Wikipedia tables (current + planned + under construction)
    # city/state directly from location column — no Google Maps
    venues = get_venues()

    if archived:
        before = len(venues)
        venues = [v for v in venues if v["venue_name"].lower() not in archived]
        print(f"  Archived filter: {before} → {len(venues)}", flush=True)

    # Summary by status
    existing     = sum(1 for v in venues if v.get("status")=="existing")
    planned      = sum(1 for v in venues if v.get("status")=="planned")
    under_const  = sum(1 for v in venues if v.get("status")=="under_construction")
    print(f"  Existing        : {existing}", flush=True)
    print(f"  Under const     : {under_const} (Tier 3-4 signals)", flush=True)
    print(f"  Planned         : {planned} (Tier 1-2 signals)", flush=True)

    # ── STEP 2A: GNews signals ───────────────────────────────
    # Planned + under_construction venues searched first (priority)
    # Broad query for planned (no construction keywords needed)
    # Existing venues: venue+team + construction keywords
    news_signals = collect_signals(venues)

    # ── STEP 2B: Govt signals ────────────────────────────────
    # Only check cities for: planned + under_construction + venues with GNews signal
    news_signal_venues = {s["venue_name"] for s in news_signals}
    govt_signals = get_city_council_signals(venues, news_signal_venues)

    # Combine + deduplicate by (venue, headline)
    combined = news_signals + govt_signals
    seen_keys, signals = set(), []
    for s in combined:
        key = (s.get("venue_name","").lower(), s.get("headline","").lower()[:80])
        if key not in seen_keys:
            seen_keys.add(key); signals.append(s)

    print(f"\n  News signals         : {len(news_signals)}", flush=True)
    print(f"  Govt signals         : {len(govt_signals)}", flush=True)
    print(f"  Combined (deduped)   : {len(signals)}", flush=True)

    # Save raw signals to DB
    if db_available():
        upsert_signals(news_signals, signal_type="news")
        upsert_signals(govt_signals, signal_type="government")

    if not signals:
        print("\n[WARN] No signals found. Check GNEWS_API_KEY.")
        return

    # ── STEP 3: LLM reasoning ────────────────────────────────
    # Stage 1: batch classify — planned venues get Tier 2+ minimum
    # Stage 2: deep analyze — capacity bonus in scoring
    all_leads, act_now = run_reasoning(signals)

    # Pursuing score boost (+15)
    if pursuing:
        for lead in all_leads:
            if lead["venue_name"].lower() in pursuing:
                lead["score"] = min(100, (lead.get("score") or 0) + 15)
                print(f"  [BOOST] {lead['venue_name']} +15 (Pursuing)", flush=True)

    if not all_leads:
        print("\n[WARN] No relevant leads found.")
        save_excel(venues, [], [], [], str(output_file), run_date=run_date)
        return

    # ── STEP 4: Stakeholders (SearchAPI only) ─────────────────
    # Targeted searches: "[venue] architect", "[venue] GC" etc.
    # Runs for engage_now + monitor leads only
    all_leads, act_now, stakeholder_rows = enrich_stakeholders(all_leads, act_now)

    # ── STEP 5: Save to DB ────────────────────────────────────
    new_leads_list = []
    if db_available():
        stats = upsert_leads(all_leads)
        print(f"\n  [DB] inserted:{stats['inserted']} "
              f"tier_changed:{stats['tier_changed']} "
              f"updated:{stats['updated']} "
              f"errors:{stats['errors']}", flush=True)

        # New leads this run (for email)
        new_leads_list = all_leads[:stats.get("inserted", 0)]

        # Bad data pattern detection
        patterns = get_bad_data_patterns()
        if patterns:
            for p in patterns:
                print(f"  [TUNING] '{p['root_cause']}' × {p['occurrences']}", flush=True)
                log_tuning_trigger(
                    p["root_cause"], p["occurrences"],
                    p["affected_venues"],
                    f"Review prompts — '{p['root_cause']}' causing bad data"
                )

        purged = purge_old_pii()
        if purged:
            print(f"  [DB] PII purged: {purged} old leads", flush=True)

    # ── STEP 6: Excel ─────────────────────────────────────────
    # Dashboard loads from PostgreSQL (historical 90 days)
    # All Leads / Act Now / Stakeholders from current run
    save_excel(venues, all_leads, act_now, stakeholder_rows,
               str(output_file), run_date=run_date)

    # ── STEP 7: Email ─────────────────────────────────────────
    if EMAIL_TO and db_available():
        print(f"\n[STEP 7] Sending email to {EMAIL_TO}...", flush=True)
        try:
            ranked_leads = get_all_leads_for_excel()
            tier_alerts  = get_tier_alerts()
            subject, body = build_daily_email(
                ranked_leads  = ranked_leads,
                new_leads     = new_leads_list,
                tier_alerts   = tier_alerts,
            )
            send_daily_report(
                receiver_email  = EMAIL_TO,
                subject         = subject,
                body            = body,
                attachment_path = str(output_file),
            )
        except Exception as e:
            print(f"  [EMAIL ERROR] {e}", flush=True)
    elif not EMAIL_TO:
        print("\n[STEP 7] Skipping email — EMAIL_TO not set in .env", flush=True)

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "="*60)
    print("  PIPELINE COMPLETE")
    print(f"  Run date         : {run_date}")
    print(f"  Total venues     : {len(venues)}")
    print(f"  News signals     : {len(news_signals)}")
    print(f"  Govt signals     : {len(govt_signals)}")
    print(f"  All Leads        : {len(all_leads)}")
    print(f"  Act Now          : {len(act_now)} (subset)")
    print(f"  Stakeholders     : {len(stakeholder_rows)}")
    print(f"  Output           : {output_file}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()