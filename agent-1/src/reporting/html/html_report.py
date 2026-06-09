# agent-1/src/reporting/html/html_report.py
from pathlib import Path
import html, json

SIGNAL_EXPLANATIONS = {
    "review_decline": {
        True: "Average review ratings are trending downward.",
        False: "No meaningful rating decline detected."
    },

    "review_volume_decline": {
        True: "Guest review activity has decreased significantly.",
        False: "Review activity remains stable."
    },

    "complaint_increase": {
        True: "Guest complaints have increased over time.",
        False: "Complaint levels remain stable."
    },

    "renovation_needed": {
        True: "Reviews indicate aging facilities or maintenance concerns.",
        False: "No significant renovation concerns identified."
    },

    "old_property": {
        True: "Property age exceeds configured age threshold.",
        False: "Property age does not indicate elevated risk."
    },

    "franchise_loss": {
        True: "Hotel appears to have lost a prior franchise affiliation.",
        False: "No evidence of franchise loss."
    },

    "franchise_affiliated": {
        True: "Property is currently affiliated with a major hospitality brand.",
        False: "No active franchise affiliation detected."
    },

    "cmbs_watchlist": {
        True: "Property loan appears on CMBS watchlist.",
        False: "No CMBS watchlist indicators found."
    },

    "cmbs_special_servicing": {
        True: "Property loan transferred to special servicing.",
        False: "No special servicing indicators detected."
    },

    "cmbs_delinquent": {
        True: "Potential loan delinquency indicators detected.",
        False: "No delinquency indicators detected."
    },

    "long_term_owner": {
        True: "Ownership tenure exceeds configured threshold.",
        False: "Ownership tenure does not indicate seller fatigue."
    },
    "sentiment_decline": {
        True: "Negative guest sentiment is increasing.",
        False: "Guest sentiment remains stable."
    },
    "review_rating_delta": "Difference between recent and historical average review ratings.",
    "physical_condition_score": "Composite score derived from renovation and property condition indicators.",
    "former_brand": "Previously identified franchise affiliation.",
    "current_brand": "Current franchise affiliation.",
    "brand_status": "Current franchise relationship status.",
    "ownership_length_years": "Estimated ownership duration in years.",
    "distress_score": "Rule-based distress score generated from review, operational and property signals.",
    "review_activity_trend": "Business-friendly classification of review activity.",
    "positive_reviews_recent": "Positive reviews identified in the recent review period.",
    "negative_reviews_recent": "Negative reviews identified in the recent review period.",
    "positive_reviews_prior": "Positive reviews identified in the prior review period.",
    "negative_reviews_prior": "Negative reviews identified in the prior review period.",
    "sentiment_trend": "Business-friendly sentiment classification.",
}

def build_hotel_card(entity):
    hotel_name = entity.get("hotel_name", "Unknown Hotel")
    llm = entity.get("llm_analysis", {})
    signals = entity.get("signals", {})
    owner = entity.get("owner_data", {})
    franchise = entity.get("franchise_data", {})
    cmbs = entity.get("cmbs_data", {})
    heuristic = entity.get("heuristic_scores", {})
    reviews = entity.get("reviews", [])[:3]
    review_themes = entity.get("review_themes", {})

    theme_rows = ""
    if not review_themes:
        theme_rows = """
        <tr>
            <td colspan="2">
                No dominant complaint themes detected.
            </td>
        </tr>
        """
    else:
        for theme, pct in sorted(review_themes.items(), key=lambda x: x[1], reverse=True):
            theme_rows += f"""
            <tr>
                <td>{theme.title()}</td>
                <td>{pct}%</td>
            </tr>
            """


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
        explanation_data = SIGNAL_EXPLANATIONS.get(key)
        if isinstance(explanation_data, dict):
            explanation = explanation_data.get(bool(value), "No explanation available.")
        else:
            explanation = explanation_data or "No explanation available."
        
        if key == "review_rating_delta":

            if value < 0:
                explanation = (
                    f"Average guest rating declined by "
                    f"{abs(value):.2f} points."
                )

            elif value > 0:
                explanation = (
                    f"Average guest rating improved by "
                    f"{value:.2f} points."
                )
            
            else:
                explanation = (
                    "Average guest rating remained unchanged."
                )

        if key == "ownership_length_years" and value:
            explanation = (
                f"Property has been owned for "
                f"{value} years."
            )

        if key == "physical_condition_score":
            explanation = (
                f"Physical condition score is {value}. "
                "Higher values indicate stronger renovation signals."
            )

        if key == "distress_score":
            explanation = (
                f"Rule-based distress score is {value}."
            )
        
        display_value = value
        if display_value in ("", None):
            display_value = "N/A"
            
        distress_signals += f"""
        <tr>
            <td>{html.escape(str(key))}</td>
            <td>{html.escape(str(display_value))}</td>
            <td>{html.escape(explanation)}</td>
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

    final_score = entity.get("final_lead_score", 0)
    if final_score >= 80:
        distress_category = "HIGH DISTRESS"
    elif final_score >= 50:
        distress_category = "MODERATE DISTRESS"
    else:
        distress_category = "LOW DISTRESS"

    return f"""
    <div class="hotel-card">

        <h1>{html.escape(hotel_name)}</h1>

        <div class="score">
            Final Opportunity Score:
            {entity.get("final_lead_score", 0)}
        </div>

        <div class="action">
            {distress_category}
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
            <tr>
                <th>Signal</th>
                <th>Value</th>
                <th>Explanation</th>
            </tr>
            {distress_signals}
        </table>

        <h2>Distress Reasons</h2>

        <ul>
            {distress_reason_html}
        </ul>

        <h2>Ownership Intelligence</h2>

        <table>
            <tr><td>Owner</td><td>{html.escape(owner.get("owner_name") or "N/A")}</td></tr>
            <tr><td>Ownership Length</td><td>{html.escape(str(owner.get("ownership_length_years") or "N/A"))}</td></tr>
            <tr><td>Mailing Address</td><td>{html.escape(owner.get("mailing_address") or "N/A")}</td></tr>
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

        <h2>Review Intelligence</h2>
            <table>
                <tr>
                    <th>Complaint Theme</th>
                    <th>Share</th>
                </tr>
                {theme_rows}
            </table>
        
        <h2>Review Trend Intelligence</h2>
            <table>
                <tr>
                    <td>Review Activity Trend</td>
                    <td>{signals.get("review_activity_trend","N/A")}</td>
                </tr>

                <tr>
                    <td>Sentiment Trend</td>
                    <td>{signals.get("sentiment_trend","N/A")}</td>
                </tr>

                <tr>
                    <td>Recent Positive Reviews</td>
                    <td>{signals.get("positive_reviews_recent","N/A")}</td>
                </tr>

                <tr>
                    <td>Recent Negative Reviews</td>
                    <td>{signals.get("negative_reviews_recent","N/A")}</td>
                </tr>

                <tr>
                    <td>Prior Positive Reviews</td>
                    <td>{signals.get("positive_reviews_prior","N/A")}</td>
                </tr>

                <tr>
                    <td>Prior Negative Reviews</td>
                    <td>{signals.get("negative_reviews_prior","N/A")}</td>
                </tr>
            </table>

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
        margin-top: 10px;
    }}
    td {{
        border: 1px solid #ddd;
        padding: 10px;
    }}
    th {{
        border: 1px solid #ddd;
        padding: 10px;
        background: #1e3a8a;
        color: white;
        text-align: left;
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