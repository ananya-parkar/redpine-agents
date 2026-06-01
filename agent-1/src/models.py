# agent-1/src/models.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class HotelEntity:
    # Core identity
    hotel_name: str
    address: str
    place_id: str

    # Geo
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Google metadata
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    business_status: Optional[str] = None
    google_maps_url: Optional[str] = None

    # Raw review data
    reviews: List[Dict] = field(default_factory=list)

    # Normalized signals
    signals: Dict = field(default_factory=dict)

    # Review Intelligence
    review_themes: Dict = field(default_factory=dict)

    # Heuristic scoring output
    heuristic_scores: Dict = field(default_factory=dict)

    # LLM-generated analysis
    llm_analysis: Dict = field(default_factory=dict)

    # External enrichment
    owner_data: Dict = field(default_factory=dict)
    cmbs_data: Dict = field(default_factory=dict)
    franchise_data: Dict = field(default_factory=dict)

    # Metadata
    source_location: Optional[str] = None
    radius_km: Optional[float] = None