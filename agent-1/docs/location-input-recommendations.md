# Location Input Enhancement Recommendations

**Project:** Redpine Agents — Agent 1  
**Audience:** Developers  
**Date:** May 28, 2026  
**Status:** Proposal

---

## Executive Summary

Agent 1 currently reads search areas from a pipe-delimited text file (`agent-1/inputs/locations.txt`) and geocodes free-text location strings via Google Maps. This works for developers but is fragile for non-technical users.

This document proposes phased improvements: better input formats, validation before runs, smarter geocoding, and optional UI replacements for the flat file.

---

## Current State

### Input format

```
Orlando International Drive, Florida | 3
```

Format: `location | radius_km`

Optional parser fields (not used by pipeline today): `min_rooms`, `max_rooms`, `year_built_range`, `price_tier`

### Relevant code

| File | Role |
|------|------|
| `agent-1/inputs/locations.txt` | Active input |
| `agent-1/inputs/sample/locations_sample.txt` | Example with comments |
| `agent-1/src/io_utils.py` | Parses pipe-delimited lines |
| `agent-1/src/google_maps.py` | Geocodes location string; uses first result only |
| `agent-1/src/main.py` | Loads locations and runs pipeline |

### Current flow

1. Parse `locations.txt`
2. Geocode each location string → lat/lng (first Google result wins)
3. Search nearby hotels within `radius_km`
4. Score and enrich each hotel

---

## Problems for Non-Technical Users

| Problem | Impact |
|---------|--------|
| Pipe syntax (`\|`) | Easy to omit, typo, or use commas instead |
| Radius in kilometers | US users typically think in miles |
| Free-text location strings | Ambiguous geocoding ("Downtown Miami" vs "Miami, FL") |
| No pre-run validation | Errors surface mid-run after API calls |
| First geocode result only | Wrong neighborhood/city searched silently |
| Duplicate entries | Sample file repeats locations; input dedupe not implemented |
| Unused optional fields | Parser supports extra columns but pipeline ignores them |

---

## Recommendations Overview

| Phase | Effort | Impact | Focus |
|-------|--------|--------|-------|
| **Phase A** | Low | High | Better file format, validation, geocode cache |
| **Phase B** | Medium | High | Map preview UI, place ID / Maps URL support |
| **Phase C** | Higher | Strategic | Polygon/ZIP search, Google Sheets, dashboard |

---

## Phase A — Low Effort, High Payoff

### A1. Replace pipe-delimited TXT with CSV or Excel

**Proposal:** Use `locations.csv` or `locations.xlsx` with explicit columns.

**Suggested schema:**

| Column | Required | Example | Notes |
|--------|----------|---------|-------|
| `name` | Yes | Orlando I-Drive corridor | Human-readable label |
| `city` | Yes | Orlando | |
| `state` | Yes | FL | Dropdown validation in Excel |
| `radius` | Yes | 2 | Numeric |
| `radius_unit` | No | miles | Default `miles`; support `km` |
| `enabled` | No | yes | Skip row if `no` without deleting |
| `notes` | No | Tourist hotel strip | Free text |

**Example row:**

```csv
name,city,state,radius,radius_unit,enabled,notes
Orlando I-Drive corridor,Orlando,FL,2,miles,yes,Main tourist hotel strip
```

**Why:** Opens in Excel/Google Sheets; no special syntax; column headers document fields.

**Implementation notes:**
- Update `io_utils.py` to read CSV (keep TXT parser as fallback if desired)
- Assemble geocode query: `"{name or area}, {city}, {state}"`
- Convert miles → km internally for Google Places API

---

### A2. Add a `validate-locations` command

**Proposal:** CLI command or `--dry-run` flag that validates input before a full agent run.

**Checks:**
- Required columns present
- Radius is numeric and within sane bounds (e.g. 0.5–50 miles)
- Each row geocodes successfully
- Flag low-confidence geocode results
- Detect duplicate locations
- Warn on disabled vs enabled row counts

**Output:** Console report and/or `location_preview.html` showing:

```
✓ Orlando I-Drive corridor → International Drive, Orlando, FL 32819 (ROOFTOP)
⚠ Downtown Miami → Miami, FL (APPROXIMATE — verify on map)
✗ Bad Row → Could not geocode
```

**Why:** Non-tech users get a green/red checklist before API spend.

---

### A3. Cache resolved coordinates

**Proposal:** After successful geocode, persist to `locations_resolved.json` (or extra CSV columns).

**Cached fields:**

```json
{
  "label": "Orlando I-Drive corridor",
  "input": "International Drive, Orlando, FL",
  "lat": 28.443,
  "lng": -81.468,
  "formatted_address": "International Drive, Orlando, FL, USA",
  "geocode_confidence": "ROOFTOP",
  "verified_at": "2026-05-28"
}
```

**Behavior:**
- If `lat`/`lng` present and `re_resolve` is false → skip geocoding
- User edits label and radius only; coordinates stay stable
- Optional `--re-resolve` flag to refresh from text

**Why:** Prevents repeat failures from minor text changes; makes runs deterministic.

---

### A4. Deduplicate input locations

**Proposal:** Before processing, dedupe by normalized `(city, state, lat, lng)` or geocoded address.

**Why:** Sample file contains duplicate rows (e.g. Mid-Beach, South Beach). Avoids redundant API calls and duplicate hotel processing.

---

### A5. Ship named market presets

**Proposal:** Curated bundles under `agent-1/inputs/markets/`:

```
markets/
  florida_tourism.csv
  texas_urban.csv
  airport_corridors.csv
```

Users copy a preset or select via CLI: `--market florida_tourism`

**Why:** Reduces "what should I type?" friction for common use cases.

---

## Phase B — Medium Effort

### B1. Simple web UI (Streamlit / Retool / internal React page)

**Features:**
- Google Places Autocomplete search box
- Map with draggable radius circle
- Radius slider in miles
- Save / enable / disable markets
- "Validate" and "Run Agent" buttons

**Why:** Non-tech users never edit a text file. Highest UX impact for ongoing use.

**Suggested stack (fastest):** Streamlit + Google Maps JS API or `streamlit-folium`

---

### B2. Support Google Maps URLs and Place IDs

**Input types:**

| Type | Example |
|------|---------|
| Lat/lng | `28.443, -81.468` |
| Google Maps URL | `https://maps.google.com/?q=28.443,-81.468` |
| Place ID | `ChIJ...` |

**Why:** Users can copy-paste from Google Maps instead of guessing geocoder phrasing.

---

### B3. Geocode disambiguation

**Current behavior:** Always uses `data["results"][0]`.

**Proposed behavior:**
- Score results by `location_type` (prefer `ROOFTOP`, `RANGE_INTERPOLATED`)
- If top result is `APPROXIMATE` or multiple results within similar bounds → warn or require confirmation in validation UI
- Validation UI shows 2–3 candidates on a map; user picks once; choice is cached

---

## Phase C — Strategic / Longer Term

### C1. Polygon or ZIP-based search

Point + radius misses edge cases in large irregular areas.

**Alternatives:**
- User draws polygon on map → search within bounds
- ZIP code list → geocode centroid + radius, or use ZIP boundaries
- County / CBSA picker → auto-generate search grid

**Note:** Google Places API already supports `locationRestriction` with circles; polygons may require grid of searches or different API usage.

---

### C2. Google Sheets as source of truth

Shared Google Sheet edited by business users; agent pulls via Sheets API on each run.

**Why:** Familiar tooling, access control, audit trail, no git required for ops team.

---

### C3. Multi-point grid search

For large regions (e.g. "Miami-Dade County"), auto-generate a grid of search points so hotels at radius edges aren't missed.

User selects region name only; system handles coverage math.

---

### C4. Seed-from-list mode

User uploads CSV of known hotel names/addresses (CoStar, STR, etc.). Agent enriches and scores directly — discovery optional.

**Why:** Acquisition teams often start from a property list, not a geography.

---

### C5. Natural language input (optional)

Chat-style input: *"Search hotels within 2 miles of Miami Beach and Fort Lauderdale airport."*

LLM parses to structured rows → validation preview → run.

**Requirement:** Always show structured preview before run; do not run directly from NL without confirmation.

---

## Better Search Strategies (Beyond Input Format)

| Strategy | Description | User-facing simplicity |
|----------|-------------|------------------------|
| ZIP-driven | `32819 \| 2 mi` | Very high |
| Hotel brand filter | "Wyndham + Choice in Orlando" | Medium |
| Comp-radius | Hotels within X mi of flagged seeds | High (map-based) |
| Saved search versions | Duplicate last month's config | High |
| KML / My Maps import | Draw regions in Google My Maps | High for map users |

---

## Recommended Implementation Order

### Sprint 1 (Phase A)
1. CSV input with miles default
2. `validate-locations` CLI
3. Geocode cache (`locations_resolved.json`)
4. Input deduplication

### Sprint 2 (Phase B)
5. Streamlit map UI with Autocomplete
6. Place ID / Maps URL parsing
7. Geocode confidence warnings

### Sprint 3 (Phase C — as needed)
8. ZIP or polygon search
9. Google Sheets integration
10. Market presets library

---

## Example: Before and After

### Today (fragile)

```
Orlando International Drive, Florida | 3
```

### Phase A (CSV)

```csv
name,city,state,radius,radius_unit,enabled,notes
Orlando I-Drive corridor,Orlando,FL,2,miles,yes,Main tourist hotel strip
```

### Phase A + cache (stable reruns)

```csv
name,city,state,lat,lng,radius,radius_unit,enabled,verified
Orlando I-Drive corridor,Orlando,FL,28.443,-81.468,2,miles,yes,yes
```

User edits `radius` and `enabled` only; lat/lng locked after first validation.

---

## Acceptance Criteria (Phase A)

- [ ] Non-tech user can add a row in Excel without syntax errors
- [ ] Validation command runs in <30s for typical market list (<20 locations)
- [ ] Failed geocodes reported with row number and suggested fix
- [ ] Duplicate locations detected before run
- [ ] Cached coordinates used on subsequent runs
- [ ] Miles accepted; converted correctly to km for Google API
- [ ] Backward compatible with existing `locations.txt` OR migration script provided

---

## Open Questions for Product

1. Should miles or km be the default for all users?
2. Is a CLI validation step enough, or is map UI required for v1?
3. Who owns the location list — ops in Sheets, or devs in git?
4. Should unused parser fields (`min_rooms`, `price_tier`) be wired into pipeline or removed from schema?
5. Max radius per search? (API cost and overlap scale with radius)

---

## References

- Input parser: `agent-1/src/io_utils.py`
- Geocoding: `agent-1/src/google_maps.py` (`geocode_location`)
- Nearby search: `agent-1/src/google_maps.py` (`nearby_hotels`)
- Entry point: `agent-1/src/main.py`
- Sample input: `agent-1/inputs/sample/locations_sample.txt`
