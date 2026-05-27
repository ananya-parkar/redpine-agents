# agent-1/src/html_report.py
from pathlib import Path
import html, json


def build_hotel_card(entity):
    hotel_name = entity.get("hotel_name", "Unknown Hotel")
    llm = entity.get("llm_analysis", {})
    signals = entity.get("signals", {})
    owner = entity.get("owner_data", {})
    franchise = entity.get("franchise_data", {})
    cmbs = entity.get("cmbs_data", {})
    heuristic = entity.get("heuristic_scores", {})
    reviews = entity.get("reviews", [])[:3]

    review_html = ""
    for review in reviews:
        text = review.get("text", {}).get("text", "")
        rating = review.get("rating", "")
        review_html += f"""
        <div class="review">
            <b>Rating:</b> {rating}/5<br>
            {html.escape(text[:300])}
        </div>
        """

    distress_signals = ""
    for key, value in signals.items():
        distress_signals += f"""
        <tr>
            <td>{html.escape(str(key))}</td>
            <td>{html.escape(str(value))}</td>
        </tr>
        """

    distress_reasons = heuristic.get("distress_reasons", [])
    distress_reason_html = "".join([
        f"<li>{html.escape(reason)}</li>"
        for reason in distress_reasons
    ])

    review_summary = llm.get("review_summary", "")
    if isinstance(review_summary, dict):
        review_summary = json.dumps(review_summary, indent=2)

    review_summary = html.escape(str(review_summary))

    star_rating = llm.get("llm_star_rating", 0)
    filled_stars = int(round(star_rating))
    empty_stars = 5 - filled_stars
    stars_html = ("★" * filled_stars + "☆" * empty_stars)

    return f"""
    <div class="hotel-card">

        <h1>{html.escape(hotel_name)}</h1>

        <div class="score">
            Final Opportunity Score:
            {entity.get("final_lead_score", 0)}
        </div>

        <div class="star-rating">
            AI Acquisition Rating:
            {stars_html}
            ({star_rating}/5)
        </div>

        <h2>AI Investment Thesis</h2>

        <div class="thesis">
            {html.escape(llm.get("investment_thesis", ""))}
        </div>

        <h2>Hotel Information</h2>

        <table>
            <tr><td>Address</td><td>{html.escape(entity.get("address", ""))}</td></tr>
            <tr><td>Google Rating</td><td>{entity.get("rating", "")}</td></tr>
            <tr><td>Total Reviews</td><td>{entity.get("user_rating_count", "")}</td></tr>
            <tr><td>Google Maps</td><td><a href="{entity.get("google_maps_url", "#")}">Open Map</a></td></tr>
        </table>

        <h2>Operational Distress Signals</h2>

        <table>
            {distress_signals}
        </table>

        <h2>Distress Reasons</h2>

        <ul>
            {distress_reason_html}
        </ul>

        <h2>Ownership Intelligence</h2>

        <table>
            <tr><td>Owner</td><td>{html.escape(owner.get("owner_name", ""))}</td></tr>
            <tr><td>Ownership Length</td><td>{html.escape(str(owner.get("ownership_length_years", "")))}</td></tr>
            <tr><td>Mailing Address</td><td>{html.escape(owner.get("mailing_address", ""))}</td></tr>
        </table>

        <h2>Franchise Intelligence</h2>

        <table>
            <tr><td>Current Brand</td><td>{html.escape(franchise.get("current_brand", ""))}</td></tr>
            <tr><td>Former Brand</td><td>{html.escape(franchise.get("former_brand", ""))}</td></tr>
            <tr><td>Status</td><td>{html.escape(franchise.get("brand_status", ""))}</td></tr>
        </table>

        <h2>CMBS Distress</h2>

        <table>
            <tr><td>Loan Status</td><td>{html.escape(str(cmbs.get("cmbs_loan_status", "")))}</td></tr>
            <tr><td>Watchlist</td><td>{cmbs.get("cmbs_watchlist_flag", False)}</td></tr>
            <tr><td>Special Servicing</td><td>{cmbs.get("cmbs_special_servicing_flag", False)}</td></tr>
        </table>

        <h2>Recommended Action</h2>

        <div class="action">
            {html.escape(llm.get("recommended_action", ""))}
        </div>

        <h2>AI Review Summary</h2>

        <div class="thesis">
            {review_summary}
        </div>
    </div>
    """


def generate_html_report(path: Path, entities):
    cards = "\n".join([
        build_hotel_card(entity)
        for entity in entities
    ])

    html_content = f"""
    <html>
    <head>
    <title>Hotel Acquisition Intelligence Report</title>
    <style>
    body {{
        font-family: Arial;
        background: #f4f4f4;
        padding: 30px;
    }}
    .hotel-card {{
        background: white;
        padding: 25px;
        margin-bottom: 40px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }}
    h1 {{
        color: #1e3a8a;
    }}
    h2 {{
        margin-top: 25px;
        color: #374151;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
    }}
    td {{
        border: 1px solid #ddd;
        padding: 10px;
    }}
    .score {{
        font-size: 24px;
        font-weight: bold;
        color: #b91c1c;
        margin-bottom: 20px;
    }}
    .review {{
        background: #fafafa;
        padding: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #2563eb;
    }}
    .thesis {{
        background: #ccfbf1;
        padding: 15px;
        border-radius: 8px;
        color: #134e4a;
        border-left: 5px solid #14b8a6;
        line-height: 1.6;
    }}
    .action {{
        background: #dbeafe;
        padding: 15px;
        border-radius: 8px;
        font-weight: bold;
    }}
    .star-rating {{
        margin-top: 10px;
        margin-bottom: 20px;
        font-size: 24px;
        color: #f59e0b;
        font-weight: bold;
    }}
    </style>
    </head>
    <body>
    <h1>Hotel Acquisition Intelligence Report</h1>
    {cards}
    </body>
    </html>
    """
    path.write_text(
        html_content,
        encoding="utf-8"
    )