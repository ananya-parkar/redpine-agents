# agent-3/scoring/seller_readiness.py
from datetime import datetime

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
    
    try:
        if isinstance(age,str) and "-" in age:
            age = int(age.split("-")[0])
        else:
            age = int(age)
        
        if age >= 70:
            return 40
        elif age >= 60:
            return 30
        elif age >= 50:
            return 15
    except:
        pass

    return 0

def score_years_in_business(years):
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

def calculate_seller_readiness(extracted):
    if extracted.get("company_type") == "Public":
        years = calculate_years_in_business(extracted.get("founded_year"))
        return {
            "years_in_business": years,
            "seller_readiness_score": 0,
            "score_breakdown": {
                "company_type": "Public"
            }
        }
    
    years = calculate_years_in_business(extracted.get("founded_year"))
    age_score = score_founder_age(extracted.get("founder_age_estimate"))
    years_score = score_years_in_business(years)
    family_score = score_family_owned(extracted.get("family_owned"))
    founder_led_score = score_founder_led(extracted.get("founder_led"))
    total_score = (age_score + years_score + family_score + founder_led_score)
    return {
        "years_in_business": years,
        "seller_readiness_score": total_score,
        "score_breakdown": {
            "founder_age_score": age_score,
            "years_in_business_score": years_score,
            "family_owned_score": family_score,
            "founder_led_score": founder_led_score,
        }
    }