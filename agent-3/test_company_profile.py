# agent-3/test_company_profile.py
from collection.company_profile import profile_company

profile = profile_company(
    company_name="Cascade Engineering",
    state="MI"
)

print(profile)