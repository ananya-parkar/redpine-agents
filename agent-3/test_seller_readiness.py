# agent-3/test_seller_readiness.py
from collection.company_profile import profile_company
from scoring.seller_readiness import calculate_seller_readiness

profile = profile_company(
    "Kadey-Krogen Yachts"
)

score = calculate_seller_readiness(profile)

print(profile)
print(score)