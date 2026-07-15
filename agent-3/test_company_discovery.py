# agent-3/test_company_discovery.py
from discovery.company_discovery import discover_companies

companies = discover_companies(
    geography="Michigan",
    industry="Any",
    ownership_preference="Family Owned",
    min_years=10,
    revenue_range="$10M-$50M",
    founder_age="60+",
)

print()

for company in companies:
    print(company)