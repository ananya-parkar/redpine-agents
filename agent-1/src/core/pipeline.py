# agent-1/src/core/pipeline.py
from datetime import datetime
from src.collectors.google_maps import geocode_location, nearby_hotels, place_details
from src.analysis.heuristic_scoring import distress_score
from src.enrichment.enrichment import enrich_priority_hotel
from src.utils.utils import extract_hotel_name, build_base_row
from src.utils.entity_builder import build_hotel_entity
from src.analysis.signals import build_signals
from src.utils.serialization import serialize_entity
from src.llm.reasoning_agent import analyze_hotel
from src.analysis.ranking_engine import calculate_final_lead_score
from src.analysis.review_intelligence import extract_review_themes
from src.analysis.property_filters import passes_filters
from src.enrichment.price_tier import get_price_tier
from src.collectors.grid_search import generate_grid_points


def process_location(item, loc_index, total_locations):
    print(
        f"\n[LOCATION {loc_index}/{total_locations}] Processing: "
        f"{item['location']} | radius_miles={item['radius_miles']}",
        flush=True
    )

    lat, lng = geocode_location(item["location"])
    print(f"\n[GEOCODE] {item['location']} -> latitude={lat}, longitude={lng}", flush=True)

    geocode_results = [{
        "location": item["location"],
        "radius_miles": item["radius_miles"],
        "latitude": lat,
        "longitude": lng
    }]

    all_hotels = []
    seen_place_ids = set()

    grid_points = generate_grid_points(lat, lng, item["radius_miles"])

    for point_lat, point_lng in grid_points:

        hotels = nearby_hotels(point_lat, point_lng, item["radius_miles"])

        for hotel in hotels:
            place_id = hotel.get("id")
            if place_id in seen_place_ids:
                continue

            seen_place_ids.add(place_id)
            all_hotels.append(hotel)

    print(f"\n[NEARBY SEARCH] Found {len(all_hotels)} hotel(s)", flush=True)
    seen = set()
    deduped_hotels = []

    for hotel in all_hotels:
        key = (
            hotel.get("displayName", {})
                .get("text", "")
                .replace("&", "and")
                .lower()
                .strip()
        )

        if key in seen:
            continue

        seen.add(key)
        deduped_hotels.append(hotel)

    hotels = deduped_hotels

    nearby_results = [{
        "search_location": item["location"],
        "radius_miles": item["radius_miles"],
        "hotel_count": len(hotels),
        "hotels": hotels
    }]

    details_results = []
    rows = []

    for hotel_index, hotel in enumerate(hotels, start=1):
        row, hotel_details = process_hotel(item, hotel, hotel_index, len(hotels))
        if row:
            rows.append(row)
        if hotel_details:
            details_results.append(hotel_details)

    return {
        "geocode_results": geocode_results,
        "nearby_results": nearby_results,
        "details_results": details_results,
        "rows": rows,
    }


def process_hotel(item, hotel, hotel_index, total_hotels):
    raw_hotel_name = extract_hotel_name(hotel)
    place_id = hotel.get("id")

    BAD_NAME_KEYWORDS = [
        "llc",
        "llp",
        "inc",
        "corporation",
        "holdings",
        "properties"
    ]

    hotel_name_check = (raw_hotel_name or "").lower()

    if any(k in hotel_name_check for k in BAD_NAME_KEYWORDS):
        print(
            f"    [SKIP] Non-hotel business entity: {raw_hotel_name}",
            flush=True
        )
        return {}, None

    rating_count = hotel.get("userRatingCount", 0)

    hotel_details = fetch_hotel_details(hotel, place_id)
    rating_count = hotel_details.get("userRatingCount", 0)
    if rating_count < 10:
        print(
            f"    [SKIP] Too few reviews: {raw_hotel_name}",
            flush=True
        )
        return {}, None

    print(
        f"\n  [HOTEL {hotel_index}/{total_hotels}] {raw_hotel_name or 'Unnamed Hotel'}",
        flush=True
    )
    print(f"    [PLACE ID] {place_id}", flush=True)

    entity = build_hotel_entity(
        hotel_details,
        source_location=item["location"],
        radius_miles=item["radius_miles"]
    )
    score_data = distress_score(hotel_details)
    entity.heuristic_scores = score_data

    entity.review_themes = extract_review_themes(entity.reviews)
    print(f"    [REVIEW THEMES] {entity.review_themes}", flush=True)

    score = score_data["distress_score"]
    reasons = score_data["distress_reasons"]
    hotel_name = extract_hotel_name(hotel_details)
    if not hotel_name or hotel_name.strip().lower() in [
        "hotel",
        "motel",
        "lodging"
    ]:
        print("    [SKIP] Invalid hotel name", flush=True)
        return {}, None

    print(
        f"    [SCORING] score={score} | "
        f"trend_score={score_data['review_trend_score']} | "
        f"reasons={reasons[:3] if reasons else ['No distress signals found']}",
        flush=True
    )

    row = build_base_row(
        search_location=item["location"],
        radius_miles=item["radius_miles"],
        hotel_name=hotel_name,
        hotel_details=hotel_details,
        score_data=score_data,
    )

    if score >= 4:
        enrichment = enrich_priority_hotel(
            hotel_name=hotel_name or raw_hotel_name,
            address=hotel_details.get("formattedAddress", ""),
            reviews=entity.reviews
        )

        row.update(enrichment)
        row["price_tier"] = get_price_tier(
            enrichment.get("current_brand")
        )
        
        # row["cmbs_watchlist"] = enrichment.get(
        #     "cmbs_watchlist_flag",
        #     False
        # )

        # row["cmbs_delinquent"] = enrichment.get(
        #     "cmbs_delinquency_flag",
        #     False
        # )

        # row["cmbs_special_servicing"] = enrichment.get(
        #     "cmbs_special_servicing_flag",
        #     False
        # )

        print(
            "[FILTER CHECK]",
            hotel_name,
            "built=",
            row.get("attom_year_built"),
            "year_filter=",
            item.get("year_built_range"),
            "price_tier=",
            row.get("price_tier"),
            "requested=",
            item.get("price_tier")
        )

        if not passes_filters(row, item):
            print("    [FILTERED]")
            return {}, None
        
        entity.owner_data = {
            "owner_name": enrichment.get("owner_name"),
            "owner_company": enrichment.get("owner_company"),
            "mailing_address": enrichment.get("mailing_address"),
            "owner_phone": enrichment.get("owner_phone"),
            "ownership_since": enrichment.get("ownership_since"),
            "ownership_length_years": enrichment.get("ownership_length_years"),
            "attom_year_built": enrichment.get("attom_year_built"),
            "is_older_than_20_years": enrichment.get("is_older_than_20_years"),
            "room_count": enrichment.get("room_count"),
        }

        # entity.cmbs_data = {
        #     "cmbs_loan_status": enrichment.get("cmbs_loan_status"),
        #     "cmbs_delinquency_flag": enrichment.get("cmbs_delinquency_flag"),
        #     "cmbs_watchlist_flag": enrichment.get("cmbs_watchlist_flag"),
        #     "cmbs_special_servicing_flag": enrichment.get("cmbs_special_servicing_flag"),
        # }

        entity.franchise_data = {
            "franchise_affiliated": enrichment.get("franchise_affiliated"),
            "current_brand": enrichment.get("current_brand"),
            "former_brand": enrichment.get("former_brand"),
            "brand_status": enrichment.get("brand_status"),
            "franchise_confidence": enrichment.get("franchise_confidence"),
            "recent_distress_news": enrichment.get("recent_distress_news"),
            "ownership_context": enrichment.get("ownership_context"),
        }

    entity.signals = build_signals(entity)
    final_lead_score = 0

    if score >= 4:
        print("    [LLM] Running reasoning agent...", flush=True)

        try:
            entity.llm_analysis = analyze_hotel(entity)

            final_lead_score = calculate_final_lead_score(entity)

            print(
                f"    [LLM] opportunity_score="
                f"{entity.llm_analysis.get('opportunity_score')}",
                flush=True
            )

        except Exception as e:
            print(f"    [LLM] Failed: {e}", flush=True)

            entity.llm_analysis = {
                "error": True,
                "failure_reason": str(e)
            }

            final_lead_score = score * 4

    else:
        entity.llm_analysis = {}

    row["signals"] = entity.signals
    print(f"    [SIGNALS] {entity.signals}", flush=True)
    
    row["review_themes"] = entity.review_themes
    row["llm_analysis"] = entity.llm_analysis
    row["final_lead_score"] = final_lead_score if score >= 4 else score * 4
    row["entity"] = serialize_entity(entity)

    lead_reason_parts = []
    signals = entity.signals

    if signals.get("franchise_loss"):
        lead_reason_parts.append(f"Lost {signals.get('former_brand')} affiliation")

    if signals.get("review_decline"):
        lead_reason_parts.append("Declining reviews")

    if signals.get("complaint_increase"):
        lead_reason_parts.append("Complaint increase")

    if signals.get("old_property"):
        lead_reason_parts.append("Aging property")

    if signals.get("long_term_owner"):
        lead_reason_parts.append("Long-term ownership")

    # if signals.get("cmbs_special_servicing"):
    #     lead_reason_parts.append("Special servicing")

    # if signals.get("cmbs_delinquent"):
    #     lead_reason_parts.append("CMBS delinquency")

    row["lead_reason"] = "; ".join(lead_reason_parts[:3])

    sources = ["Google Places"]
    if entity.owner_data.get("owner_name"):
        sources.append("ATTOM")

    if entity.franchise_data.get("franchise_affiliated"):
        sources.append("Claude Web Search")

    # if entity.cmbs_data.get("cmbs_loan_status"):
    #     sources.append("SEC EDGAR")

    row["source_provenance"] = " | ".join(sources)

    row["entity"] = serialize_entity(entity)

    row["created_at"] = datetime.utcnow().isoformat()
    row["place_id"] = place_id

    return row, hotel_details


def fetch_hotel_details(hotel, place_id):
    hotel_details = hotel

    if not place_id:
        print("    [DETAILS] Skipped: no place_id found", flush=True)
        return hotel_details

    try:
        print("    [DETAILS] Fetching place details...", flush=True)
        hotel_details = place_details(place_id)
        print("    [DETAILS] Success", flush=True)
        return hotel_details
    except Exception as e:
        print(f"    [DETAILS] Failed: {e}", flush=True)
        return hotel | {"details_error": str(e)}