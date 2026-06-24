import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)


# ---------------------------------------------------
# API KEYS
# ---------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL")
GNEWS_API_KEY  = os.getenv("GNEWS_API_KEY", "")
TOP_N_FOR_LLM  = 100
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY", "")
SEARCHAPI_KEY = os.getenv("SEARCHAPI_KEY", "")
TAVILY_API_KEY=os.getenv("TAVILY_API_KEY","")
# ---------------------------------------------------
# PIPELINE CONFIG
# ---------------------------------------------------
TOP_N_FOR_LLM = 20
OUTPUT_FILE   = Path("outputs/stadium_leads8.xlsx")

# ---------------------------------------------------
# KEYWORDS — used by both news and govt signal collectors
# ---------------------------------------------------
KEYWORDS = [
    "renovation", "expansion", "upgrade", "modernization",
    "new construction", "new stadium", "new arena", "rebuild",
    "redevelopment", "overhaul", "master plan", "feasibility study",
    "mixed-use", "approved", "funding", "bond", "referendum",
    "capital improvement", "city council", "public financing",
    "budget allocation", "tax increment", "legislation",
    "architect", "design firm", "general contractor", "awarded contract",
    "HOK", "Populous", "AECOM", "Gensler", "HKS",
    "Turner Construction", "Mortenson", "Hunt Construction", "Clark Construction",
    "RFP", "RFQ", "bid", "procurement", "solicitation",
    "convention center", "exhibit hall", "ballroom expansion",
]

# Government-document-specific keywords — added for city council feed only
# These appear in ordinances and agenda items, not typically in news.
GOVT_KEYWORDS = [
    "ordinance", "resolution", "bond ordinance", "capital plan",
    "capital improvement plan", "CIP", "appropriation", "general obligation",
    "revenue bond", "tax increment financing", "TIF", "public hearing",
    "stadium authority", "arena authority", "sports authority",
    "facility improvement", "venue improvement",
    "naming rights", "lease agreement", "development agreement",
    "ground lease", "construction contract", "design contract",
    "architectural services", "construction manager"
]

TIER_KEYWORDS = {
    1: [
        "renovation", "expansion", "new stadium", "new arena", "upgrade",
        "construction plans", "redevelopment", "feasibility study",
        "master plan", "modernization", "overhaul", "rebuild", "mixed-use"
    ],
    2: [
        "bond", "referendum", "approved", "funding approved",
        "budget allocation", "city council", "capital improvement",
        "public financing", "tax increment", "legislation", "appropriation",
        "ordinance", "resolution", "general obligation", "revenue bond",
        "CIP", "capital plan", "bond ordinance"
    ],
    3: [
        "architect", "design firm", "general contractor", "HOK", "Populous",
        "AECOM", "Gensler", "HKS", "Turner Construction", "Mortenson",
        "Hunt Construction", "Clark Construction", "awarded contract",
        "design contract", "design team", "architectural services"
    ],
    4: [
        "RFP", "RFQ", "request for proposal", "request for qualifications",
        "bid", "procurement", "solicitation", "invitation to bid"
    ]
}

CONSTRUCTION_INTENT = (
    "renovation OR expansion OR construction OR upgrade OR "
    "funding OR bond OR rebuild OR architect"
)

TIER_LABELS = {
    1: "Tier 1 — Early Rumor",
    2: "Tier 2 — Funding Committed",
    3: "Tier 3 — Design Phase",
    4: "Tier 4 — Procurement"
}

# ---------------------------------------------------
# KNOWN FIRMS REGISTRY
# ---------------------------------------------------
FIRMS = [
    # Architects
    {"lookup": "populous",           "full_name": "Populous",                    "type": "architect", "website": "populous.com"},
    {"lookup": "hok",                "full_name": "HOK",                         "type": "architect", "website": "hok.com"},
    {"lookup": "hks",                "full_name": "HKS Architects",              "type": "architect", "website": "hksinc.com"},
    {"lookup": "aecom",              "full_name": "AECOM",                       "type": "architect", "website": "aecom.com"},
    {"lookup": "gensler",            "full_name": "Gensler",                     "type": "architect", "website": "gensler.com"},
    {"lookup": "rossetti",           "full_name": "Rossetti",                    "type": "architect", "website": "rossetti.com"},
    {"lookup": "360 architecture",   "full_name": "360 Architecture (Populous)", "type": "architect", "website": "populous.com"},
    # GCs
    {"lookup": "turner",             "full_name": "Turner Construction",         "type": "gc",        "website": "turnerconstruction.com"},
    {"lookup": "mortenson",          "full_name": "Mortenson Construction",      "type": "gc",        "website": "mortenson.com"},
    {"lookup": "hunt construction",  "full_name": "Hunt / AECOM Hunt",           "type": "gc",        "website": "aecom.com/hunt"},
    {"lookup": "clark construction", "full_name": "Clark Construction Group",    "type": "gc",        "website": "clarkconstruction.com"},
    {"lookup": "barton malow",       "full_name": "Barton Malow",                "type": "gc",        "website": "bartonmalow.com"},
    {"lookup": "skanska",            "full_name": "Skanska USA",                 "type": "gc",        "website": "skanska.com"},
    {"lookup": "whiting-turner",     "full_name": "Whiting-Turner",              "type": "gc",        "website": "whiting-turner.com"},
]

# ---------------------------------------------------
# CITY COUNCIL MONITORING — LEGISTAR CITY MAPPINGS
#
# LegiStar is a free city council REST API (no key needed).
# Maps lowercase city name → LegiStar client ID.
# Verify a city: https://webapi.legistar.com/v1/{client}/Matters
# Add more client IDs as you encounter new venue cities.
# ---------------------------------------------------
LEGISTAR_CITIES = {
    "new york":      "nyc",
    "chicago":       "chicago",
    "los angeles":   "lacity",
    "seattle":       "seattle",
    "denver":        "denver",
    "boston":        "boston",
    "nashville":     "nashville",
    "phoenix":       "phoenix",
    "dallas":        "dallas",
    "atlanta":       "atlanta",
    "indianapolis":  "indianapolis",
    "portland":      "portland",
    "minneapolis":   "minneapolis",
    "cleveland":     "cleveland",
    "pittsburgh":    "pittsburgh",
    "columbus":      "columbus",
    "charlotte":     "charlotte",
    "baltimore":     "baltimore",
    "san francisco": "sanfrancisco",
    "oakland":       "oakland",
    "kansas city":   "kansascity",
    "tampa":         "tampa",
    "sacramento":    "sacramento",
    "buffalo":       "buffalo",
    "orlando":       "orlando",
    "raleigh":       "raleigh",
    "miami":         "miami",
    "detroit":       "detroit",
    "milwaukee":     "milwaukee",
    "cincinnati":    "cincinnati",
    "memphis":       "memphis",
    "louisville":    "louisville",
    "san jose":      "sanjose",
    "san diego":     "sandiego",
}

# ---------------------------------------------------
# SEED VENUES — fallback if Wikipedia scraping fails
# ---------------------------------------------------
SEED_VENUES = [
    # NFL
    {"venue_name": "Allegiant Stadium",          "league": "NFL",  "city": "Las Vegas",       "state": "NV", "capacity": 65000},
    {"venue_name": "AT&T Stadium",               "league": "NFL",  "city": "Arlington",       "state": "TX", "capacity": 80000},
    {"venue_name": "SoFi Stadium",               "league": "NFL",  "city": "Inglewood",       "state": "CA", "capacity": 70240},
    {"venue_name": "Lambeau Field",              "league": "NFL",  "city": "Green Bay",       "state": "WI", "capacity": 81441},
    {"venue_name": "Mercedes-Benz Stadium",      "league": "NFL",  "city": "Atlanta",         "state": "GA", "capacity": 71000},
    {"venue_name": "Levi's Stadium",             "league": "NFL",  "city": "Santa Clara",     "state": "CA", "capacity": 68500},
    {"venue_name": "Arrowhead Stadium",          "league": "NFL",  "city": "Kansas City",     "state": "MO", "capacity": 76416},
    {"venue_name": "Soldier Field",              "league": "NFL",  "city": "Chicago",         "state": "IL", "capacity": 61500},
    {"venue_name": "Highmark Stadium",           "league": "NFL",  "city": "Orchard Park",    "state": "NY", "capacity": 71608},
    {"venue_name": "Empower Field at Mile High", "league": "NFL",  "city": "Denver",          "state": "CO", "capacity": 76125},
    # NBA
    {"venue_name": "Madison Square Garden",      "league": "NBA",  "city": "New York",        "state": "NY", "capacity": 19812},
    {"venue_name": "Crypto.com Arena",           "league": "NBA",  "city": "Los Angeles",     "state": "CA", "capacity": 19079},
    {"venue_name": "Chase Center",               "league": "NBA",  "city": "San Francisco",   "state": "CA", "capacity": 18064},
    {"venue_name": "United Center",              "league": "NBA",  "city": "Chicago",         "state": "IL", "capacity": 20917},
    {"venue_name": "TD Garden",                  "league": "NBA",  "city": "Boston",          "state": "MA", "capacity": 19156},
    {"venue_name": "Kaseya Center",              "league": "NBA",  "city": "Miami",           "state": "FL", "capacity": 19600},
    {"venue_name": "Gainbridge Fieldhouse",      "league": "NBA",  "city": "Indianapolis",    "state": "IN", "capacity": 17923},
    # MLB
    {"venue_name": "Dodger Stadium",             "league": "MLB",  "city": "Los Angeles",     "state": "CA", "capacity": 56000},
    {"venue_name": "Fenway Park",                "league": "MLB",  "city": "Boston",          "state": "MA", "capacity": 37755},
    {"venue_name": "Wrigley Field",              "league": "MLB",  "city": "Chicago",         "state": "IL", "capacity": 41649},
    {"venue_name": "Yankee Stadium",             "league": "MLB",  "city": "New York",        "state": "NY", "capacity": 46537},
    {"venue_name": "Oracle Park",                "league": "MLB",  "city": "San Francisco",   "state": "CA", "capacity": 41915},
    {"venue_name": "Globe Life Field",           "league": "MLB",  "city": "Arlington",       "state": "TX", "capacity": 40518},
    # NHL
    {"venue_name": "Wells Fargo Center",         "league": "NHL",  "city": "Philadelphia",    "state": "PA", "capacity": 19543},
    {"venue_name": "Bell Centre",                "league": "NHL",  "city": "Montreal",        "state": "QC", "capacity": 21302},
    {"venue_name": "Rogers Place",               "league": "NHL",  "city": "Edmonton",        "state": "AB", "capacity": 18347},
    {"venue_name": "Little Caesars Arena",       "league": "NHL",  "city": "Detroit",         "state": "MI", "capacity": 19515},
    # MLS
    {"venue_name": "Geodis Park",                "league": "MLS",  "city": "Nashville",       "state": "TN", "capacity": 30000},
    {"venue_name": "Q2 Stadium",                 "league": "MLS",  "city": "Austin",          "state": "TX", "capacity": 20738},
    {"venue_name": "Lower.com Field",            "league": "MLS",  "city": "Columbus",        "state": "OH", "capacity": 20371},
    # NCAA
    {"venue_name": "Michigan Stadium",           "league": "NCAA", "city": "Ann Arbor",       "state": "MI", "capacity": 107601},
    {"venue_name": "Ohio Stadium",               "league": "NCAA", "city": "Columbus",        "state": "OH", "capacity": 102780},
    {"venue_name": "Kyle Field",                 "league": "NCAA", "city": "College Station", "state": "TX", "capacity": 102733},
    {"venue_name": "Neyland Stadium",            "league": "NCAA", "city": "Knoxville",       "state": "TN", "capacity": 101915},
    {"venue_name": "Tiger Stadium",              "league": "NCAA", "city": "Baton Rouge",     "state": "LA", "capacity": 102321},
    {"venue_name": "Bryant-Denny Stadium",       "league": "NCAA", "city": "Tuscaloosa",      "state": "AL", "capacity": 100077},
    # Convention Centers — capacity = max event attendance estimate
    {"venue_name": "McCormick Place",                          "league": "Convention Center", "city": "Chicago",       "state": "IL", "capacity": 45000},
    {"venue_name": "Walter E. Washington Convention Center",   "league": "Convention Center", "city": "Washington",    "state": "DC", "capacity": 25000},
    {"venue_name": "Las Vegas Convention Center",              "league": "Convention Center", "city": "Las Vegas",     "state": "NV", "capacity": 40000},
    {"venue_name": "Orange County Convention Center",          "league": "Convention Center", "city": "Orlando",       "state": "FL", "capacity": 35000},
    {"venue_name": "Georgia World Congress Center",            "league": "Convention Center", "city": "Atlanta",       "state": "GA", "capacity": 30000},
    {"venue_name": "Colorado Convention Center",               "league": "Convention Center", "city": "Denver",        "state": "CO", "capacity": 20000},
    {"venue_name": "Austin Convention Center",                 "league": "Convention Center", "city": "Austin",        "state": "TX", "capacity": 15000},
    {"venue_name": "Boston Convention and Exhibition Center",  "league": "Convention Center", "city": "Boston",        "state": "MA", "capacity": 20000},
    {"venue_name": "Jacob K. Javits Convention Center",        "league": "Convention Center", "city": "New York",      "state": "NY", "capacity": 35000},
    {"venue_name": "Los Angeles Convention Center",            "league": "Convention Center", "city": "Los Angeles",   "state": "CA", "capacity": 30000},
    {"venue_name": "San Diego Convention Center",              "league": "Convention Center", "city": "San Diego",     "state": "CA", "capacity": 20000},
    {"venue_name": "Phoenix Convention Center",                "league": "Convention Center", "city": "Phoenix",       "state": "AZ", "capacity": 25000},
    {"venue_name": "Seattle Convention Center",                "league": "Convention Center", "city": "Seattle",       "state": "WA", "capacity": 15000},
    {"venue_name": "Kay Bailey Hutchison Convention Center",   "league": "Convention Center", "city": "Dallas",        "state": "TX", "capacity": 20000},
    {"venue_name": "George R. Brown Convention Center",        "league": "Convention Center", "city": "Houston",       "state": "TX", "capacity": 25000},
    {"venue_name": "Ernest N. Morial Convention Center",       "league": "Convention Center", "city": "New Orleans",   "state": "LA", "capacity": 30000},
    {"venue_name": "Indiana Convention Center",                "league": "Convention Center", "city": "Indianapolis",  "state": "IN", "capacity": 20000},
    {"venue_name": "Music City Center",                        "league": "Convention Center", "city": "Nashville",     "state": "TN", "capacity": 18000},
    {"venue_name": "Miami Beach Convention Center",            "league": "Convention Center", "city": "Miami Beach",   "state": "FL", "capacity": 15000},
    {"venue_name": "David L. Lawrence Convention Center",      "league": "Convention Center", "city": "Pittsburgh",    "state": "PA", "capacity": 15000},
    {"venue_name": "Minneapolis Convention Center",            "league": "Convention Center", "city": "Minneapolis",   "state": "MN", "capacity": 20000},
    {"venue_name": "Kansas City Convention Center",            "league": "Convention Center", "city": "Kansas City",   "state": "MO", "capacity": 15000},
    {"venue_name": "Baltimore Convention Center",              "league": "Convention Center", "city": "Baltimore",     "state": "MD", "capacity": 12000},
    {"venue_name": "San Jose Convention Center",               "league": "Convention Center", "city": "San Jose",      "state": "CA", "capacity": 12000},
    {"venue_name": "Portland Oregon Convention Center",        "league": "Convention Center", "city": "Portland",      "state": "OR", "capacity": 15000},
]

# Wikipedia queries per league
WIKI_QUERIES = [
    ("NFL",               "List of current NFL stadiums"),
    ("NBA",               "List of NBA arenas"),
    ("MLB",               "List of current Major League Baseball stadiums"),
    ("NHL",               "List of NHL arenas"),
    ("MLS",               "List of Major League Soccer stadiums"),
    ("NCAA",              "List of NCAA Division I FBS football stadiums"),
    ("Convention Center", "List of convention centers in the United States"),
]