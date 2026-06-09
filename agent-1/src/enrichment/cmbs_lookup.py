# agent-1/src/enrichment/cmbs_lookup.py
import re
import requests
from typing import Dict
from src.core.config import SEARCH_TIMEOUT


def default_cmbs_result() -> Dict:
    """Returns default CMBS structure when lookup is skipped or fails."""
    return {
        "cmbs_loan_status": "",
        "cmbs_delinquency_flag": False,
        "cmbs_watchlist_flag": False,
        "cmbs_special_servicing_flag": False,
        "cmbs_confidence": "Not Checked",
        "cmbs_evidence": ""
    }


def normalize_hotel_name(name: str) -> str:
    """Normalize hotel name for matching against CMBS filings."""
    if not name:
        return ""
    # Remove common suffixes/prefixes
    name = re.sub(r'\b(hotel|inn|suites?|lodge|motel)\b', '', name, flags=re.IGNORECASE)
    # Remove non-alphanumeric except spaces
    name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name


def search_edgar_cmbs(hotel_name: str, address: str = "") -> Dict:
    """
    Search SEC EDGAR for CMBS filings mentioning this property.
    
    This is a simplified prototype. Production version would:
    - Use SEC EDGAR API with structured queries
    - Parse XML exhibits from 8-K and 10-K filings
    - Match property addresses against loan collateral schedules
    - Extract servicer comments and loan status codes
    
    For now, this does basic text search for proof-of-concept.
    """
    
    # Extract city/state from address for targeted search
    location_hint = ""
    if address:
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            location_hint = f"{parts[-2]} {parts[-1]}"  # City, State
    
    normalized_name = normalize_hotel_name(hotel_name)
    
    # Build search queries
    queries = []
    if normalized_name:
        queries.append(f'"{hotel_name}" CMBS delinquent')
        queries.append(f'"{hotel_name}" special servicer')
        queries.append(f'"{hotel_name}" watchlist')
    
    if location_hint:
        queries.append(f'{hotel_name} {location_hint} CMBS')
    
    evidence = []
    delinquent = False
    watchlist = False
    special_servicing = False
    
    for query in queries[:2]:  # Limit to first 2 queries to avoid rate limiting
        try:
            # SEC EDGAR full-text search endpoint
            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                "action": "getcompany",
                "company": query,
                "type": "8-K",  # CMBS servicer reports are typically 8-K
                "dateb": "",
                "owner": "exclude",
                "count": "10"
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; HotelResearchBot/1.0; +http://example.com/bot)"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=SEARCH_TIMEOUT)
            response.raise_for_status()
            
            text = response.text.lower()
            
            # Simple keyword matching (production would parse XML exhibits)
            if "delinquent" in text or "delinquency" in text:
                delinquent = True
                evidence.append(f"EDGAR match: delinquency signal for '{query}'")
            
            if "watchlist" in text or "watch list" in text:
                watchlist = True
                evidence.append(f"EDGAR match: watchlist signal for '{query}'")
            
            if "special servic" in text:  # Matches "special servicer" or "special servicing"
                special_servicing = True
                evidence.append(f"EDGAR match: special servicing signal for '{query}'")
                
        except Exception as e:
            evidence.append(f"EDGAR search failed for '{query}': {str(e)}")
    
    # Determine loan status and confidence
    if special_servicing:
        loan_status = "Special Servicing"
        confidence = "High"
    elif delinquent:
        loan_status = "Delinquent"
        confidence = "Medium"
    elif watchlist:
        loan_status = "Watchlist"
        confidence = "Low"
    else:
        loan_status = "Not Found"
        confidence = "Low"
    
    return {
        "cmbs_loan_status": loan_status,
        "cmbs_delinquency_flag": delinquent,
        "cmbs_watchlist_flag": watchlist,
        "cmbs_special_servicing_flag": special_servicing,
        "cmbs_confidence": confidence,
        "cmbs_evidence": " | ".join(evidence) if evidence else "No CMBS signals detected"
    }


def detect_cmbs_signals(hotel_name: str, address: str = "") -> Dict:
    """
    Main entry point for CMBS lookup.
    Only call this for priority hotels with franchise loss signals.
    """
    if not hotel_name:
        return {
            **default_cmbs_result(),
            "cmbs_evidence": "No hotel name provided"
        }
    
    try:
        print("    [CMBS] Searching SEC EDGAR for loan distress signals...", flush=True)
        result = search_edgar_cmbs(hotel_name, address)
        
        print(
            f"    [CMBS] status={result['cmbs_loan_status']} | "
            f"delinquent={result['cmbs_delinquency_flag']} | "
            f"watchlist={result['cmbs_watchlist_flag']} | "
            f"special_servicing={result['cmbs_special_servicing_flag']}",
            flush=True
        )
        
        return result
        
    except Exception as e:
        print(f"    [CMBS] Failed: {e}", flush=True)
        return {
            **default_cmbs_result(),
            "cmbs_confidence": "Error",
            "cmbs_evidence": f"CMBS lookup failed: {str(e)}"
        }
