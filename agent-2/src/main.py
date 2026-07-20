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
from stale_lead_refresher   import refresh_stale_leads
from run_paths               import get_todays_output_file
from db_writer               import (
    init_db, db_available,
    upsert_signals, upsert_leads, upsert_stakeholders,
    get_archived_venues, get_pursuing_venues,
    get_leads_for_excel, get_stakeholders_for_excel,
    get_all_leads_for_excel, get_tier_alerts,
    purge_old_pii,
)
EMAIL_TO = os.getenv("EMAIL_TO", "")

# How far back the Excel sheets + Dashboard look.
#
# A stadium project lives for months and does NOT make the news every day.
# The sheets used to show ONLY the current run's leads, so a Tier 1/2 lead
# found last week silently vanished the moment it had no fresh article —
# even though it was still a live opportunity sitting in the DB (and still
# counted on the Dashboard, which DID read the DB — hence the mismatch).
# Everything the client sees now comes from the DB over this window.
EXCEL_LOOKBACK_DAYS = 30


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
    # city/state directly from location column
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

    # ── STEP 2A: News signals (NewsAPI) ──────────────────────
    # Planned + under_construction venues searched first (priority)
    # Broad query for planned (no construction keywords needed)
    # Existing venues: venue+team + construction keywords
    news_signals = collect_signals(venues)

    # ── STEP 2B: Govt signals ────────────────────────────────
    # Only check cities for: planned + under_construction + venues with a news signal
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
        print("\n[WARN] No signals found. Check NEWSAPI_KEY.")
        return

    # ── STEP 3: LLM reasoning ────────────────────────────────
    # Stage 1: batch classify
    # Stage 2: deep analyze (venue_confirmed gate)
    # Stage 3: Claude web-search verification (forward-only tier moves)
    run_leads, run_act_now = run_reasoning(signals)

    # Pursuing score boost (+15)
    if pursuing:
        for lead in run_leads:
            if lead["venue_name"].lower() in pursuing:
                lead["score"] = min(100, (lead.get("score") or 0) + 15)
                print(f"  [BOOST] {lead['venue_name']} +15 (Pursuing)", flush=True)

    # ── STEP 4: Stakeholders (Claude web search) ─────────────
    # Runs on THIS RUN's leads only (engage_now + monitor) so the
    # web-search cost stays bounded. Results are persisted at STEP 5, and
    # STEP 6 reads back every active lead's stakeholders — so a lead
    # enriched last week keeps its contacts even when it isn't re-enriched
    # today.
    if run_leads:
        run_leads, run_act_now, stakeholder_rows = enrich_stakeholders(
            run_leads, run_act_now)
    else:
        print("\n[WARN] No relevant leads found in this run.", flush=True)
        stakeholder_rows = []

    # ── STEP 5: Save to DB ────────────────────────────────────
    # upsert_leads: NEW venue → INSERT, SEEN before → UPDATE + log any
    # tier change. This is what keeps an older lead's tier current when
    # today's run re-detects it at a different stage.
    new_leads_list = []
    if db_available():
        stats = upsert_leads(run_leads)
        print(f"\n  [DB] inserted:{stats['inserted']} "
              f"tier_changed:{stats['tier_changed']} "
              f"updated:{stats['updated']} "
              f"errors:{stats['errors']}", flush=True)

        upsert_stakeholders(stakeholder_rows)

        # New leads this run, by actual inserted venue name (the old
        # `run_leads[:inserted]` slice just took the first N of the sorted
        # list, which are rarely the ones that were really new).
        inserted_names = set(stats.get("inserted_venues", []))
        new_leads_list = [l for l in run_leads
                          if l.get("venue_name") in inserted_names]

        # NOTE: bad-data pattern detection + tuning trigger logging is
        # handled at STEP 0 by feedback_reader.run() ->
        # check_and_log_tuning_triggers(), right after feedback is read
        # from the previous run's Excel.

        purged = purge_old_pii()
        if purged:
            print(f"  [DB] PII purged: {purged} old leads", flush=True)

    # ── STEP 5B: Refresh stale leads not seen in today's signals ──
    # run_leads only contains venues that got a FRESH news/govt signal
    # this run. Without this step, any OTHER active lead sitting in the
    # DB keeps whatever tier it was last assigned, even if the project
    # quietly progressed (funding approved, architect hired) with no new
    # article to trigger a re-check. This picks a rotating slice of the
    # rest of the active backlog (oldest-verified-first, capped at
    # REFRESH_LIMIT) and runs the same Stage-3 web-search verification on
    # them, persisting any tier changes — BEFORE Excel is built below, so
    # the workbook reflects the refreshed tiers too.
    refresh_stats = {"checked": 0, "updated": 0}
    if db_available():
        run_venue_names = {l.get("venue_name","") for l in run_leads}
        refresh_stats = refresh_stale_leads(run_venue_names)

    # ── STEP 6: Excel ─────────────────────────────────────────
    # Everything the client sees — Dashboard, All Leads, Act Now,
    # Stakeholders — comes from ONE source: the DB, over the last
    # EXCEL_LOOKBACK_DAYS. That means:
    #   • a lead found last week still shows (and still counts as Act Now)
    #     even if it had no news today
    #   • the Dashboard KPIs and the sheets can never disagree, because
    #     they're computed from the same list
    # If the DB is down we fall back to this run's leads so the pipeline
    # still produces a usable workbook.
    if db_available():
        excel_leads, excel_act_now = get_leads_for_excel(days=EXCEL_LOOKBACK_DAYS)
        excel_stakeholders         = get_stakeholders_for_excel(days=EXCEL_LOOKBACK_DAYS)
        if not excel_leads:   # empty DB (first ever run) — show this run
            excel_leads, excel_act_now = run_leads, run_act_now
            excel_stakeholders         = stakeholder_rows
    else:
        print("  [WARN] DB unavailable — Excel shows THIS RUN's leads only", flush=True)
        excel_leads, excel_act_now = run_leads, run_act_now
        excel_stakeholders         = stakeholder_rows

    save_excel(venues, excel_leads, excel_act_now, excel_stakeholders,
               str(output_file), run_date=run_date)

    # ── STEP 7: Email ─────────────────────────────────────────
    if EMAIL_TO and db_available():
        print(f"\n[STEP 7] Sending email to {EMAIL_TO}...", flush=True)
        try:
            tier_alerts = get_tier_alerts()
            subject, body = build_daily_email(
                ranked_leads  = excel_leads,   # same set the workbook shows
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
    print(f"  Leads this run   : {len(run_leads)} ({len(new_leads_list)} brand new)")
    print(f"  Stale refreshed  : {refresh_stats['checked']} checked, "
          f"{refresh_stats['updated']} tier change(s)")
    print(f"  Leads in workbook: {len(excel_leads)} (active, last {EXCEL_LOOKBACK_DAYS} days)")
    print(f"  Act Now          : {len(excel_act_now)}")
    print(f"  Stakeholders     : {len(excel_stakeholders)}")
    print(f"  Output           : {output_file}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()