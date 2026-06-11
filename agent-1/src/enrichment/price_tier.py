# agent-1/src/enrichment/price_tier.py
from src.core.config import PRICE_TIER_MAPPING

def get_price_tier(current_brand):

    if not current_brand:
        return ""

    return PRICE_TIER_MAPPING.get(
        current_brand,
        ""
    )
