# agent-3/scoring/seller_readiness.py
from datetime import datetime
import re

def calculate_years_in_business(founded_year):
    try:
        return datetime.now().year - int(founded_year)
    except:
        return 0


def score_founder_led(value):
    if value == "Yes":
        return 15
    return 0

def score_founder_age(age):
    if not age or age == "Unknown":
        return 0

    match = re.search(r"\d+", str(age))
    if not match:
        return 0

    age = int(match.group())

    if age >= 70:
        return 40
    elif age >= 60:
        return 30
    elif age >= 50:
        return 15

    return 0

def score_years_in_business(years):
    try:
        years = int(years)
    except:
        return 0

    if years >= 40:
        return 35
    elif years >= 30:
        return 30
    elif years >= 20:
        return 20
    elif years >= 10:
        return 10

    return 0

def score_family_owned(value):
    if value == "Yes":
        return 25
    return 0

def score_ownership_tenure(years):
    match = re.search(r"\d+", str(years))
    if not match:
        return 0

    years = int(match.group())

    if years >= 40:
        return 25
    elif years >= 30:
        return 20
    elif years >= 20:
        return 15
    elif years >= 10:
        return 10

    return 0

def calculate_seller_readiness(profile):
    if profile.get("company_type") == "Public":
        years = profile.get("years_in_business")
        try:
            years = int(years)
        except (TypeError, ValueError):
            years = calculate_years_in_business(
                profile.get("founded_year")
            )
        
        return {
            "years_in_business": years,
            "seller_readiness_score": 0,
            "score_breakdown": {
                "company_type": "Public"
            }
        }
    
    years = profile.get("years_in_business")

    try:
        years = int(years)
    except (TypeError, ValueError):
        years = calculate_years_in_business(
            profile.get("founded_year")
        )
        
    age_score = score_founder_age(profile.get("founder_age_estimate"))
    years_score = score_years_in_business(years)
    family_score = score_family_owned(profile.get("family_owned"))
    founder_led_score = score_founder_led(profile.get("founder_led"))
    ownership_tenure_score = score_ownership_tenure(profile.get("ownership_tenure_years"))
    total_score = (age_score + years_score + family_score + founder_led_score + ownership_tenure_score)
    return {
        "years_in_business": years,
        "seller_readiness_score": total_score,
        "score_breakdown": {
            "founder_age_score": age_score,
            "years_in_business_score": years_score,
            "family_owned_score": family_score,
            "founder_led_score": founder_led_score,
            "ownership_tenure_score": ownership_tenure_score
        }
    }