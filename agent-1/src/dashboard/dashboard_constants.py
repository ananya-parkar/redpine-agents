#agent-1/src/dashboard/dashboard_constants.py
DARK_HEADER   = "1A2744"
GREEN_PRIMARY = "0B5D4A"
WHITE         = "FFFFFF"
TEXT_DARK     = "1E293B"
TEXT_MED      = "475569"

CARD_DEFS = [
    ("total_hotels","Total Hotels","EEF7EE","1A4731"),
    ("high_opportunity","High Opportunity","F3F0FF","4C1D95"),
    ("deep_distress","Deep Distress","FFF0F0","991B1B"),
    ("long_term_owners","Long-Term Owners","EEF7F7","0F766E"),
    ("avg_opportunity_score","Avg Opportunity","EEF3FF","1E3A8A"),
]

STATUS_COLORS = {
    "New":          ("DCFCE7", "166534"),
    "Pursuing":     ("FEF9C3", "854D0E"),
    "Passed":       ("FEE2E2", "991B1B"),
    "Monitoring":   ("DBEAFE", "1E40AF"),
    "Underwriting": ("F3E8FF", "6B21A8"),
}

# Chart series colors matching mockup
DIST_COLORS = [
    "B03A2E",
    "D2691E",
    "D4A437",
    "3A7D44",
    "2E6DA4"
]
SIG_COLORS = [
    "B03A2E",   # Declining Reviews
    "D2691E",   # Franchise Loss
    "D4A437",   # Aging Property
    "3A7D44",   # Owner Fatigue
    "2C7A7B"    # CMBS Distress
]

MKT_COLORS = [
    "111827",
    "1F2937",
    "166534",
    "4D8B5B",
    "93C5A1"
]
FRAN_COLORS  = ["1B4332", "3498DB"]
LEAD_STATUS_COLORS = [
    "2E6B3F",  # New
    "D4A437",  # Pursuing
    "B03A2E",  # Passed
    "2E73C5",  # Monitoring
    "1F3A93",  # Underwriting
]