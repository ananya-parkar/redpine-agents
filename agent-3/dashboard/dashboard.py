# agent-3/dashboard/dashboard.py
"""
Layer 7 - Dashboard Excel Generator
"""
import os
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList

load_dotenv(override=True)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB_AGENT3", "redpine_agent3"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

FONT_NAME = "Calibri"
NAVY = "1B2A4A"
NAVY_FILL = PatternFill("solid", start_color=NAVY, end_color=NAVY)
WHITE_FONT = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=18)
WHITE_SUBFONT = Font(name=FONT_NAME, color="D1D9E6", italic=True, size=10)
WHITE_SMALL = Font(name=FONT_NAME, color="FFFFFF", size=10)
INVISIBLE_FONT = Font(name=FONT_NAME, size=9, color="FFFFFF")

CARD_BLUE = PatternFill("solid", start_color="DCE9F9", end_color="DCE9F9")
CARD_GREEN = PatternFill("solid", start_color="DCEFD8", end_color="DCEFD8")
CARD_YELLOW = PatternFill("solid", start_color="FCF1C9", end_color="FCF1C9")
CARD_PURPLE = PatternFill("solid", start_color="E6DEF2", end_color="E6DEF2")
CARD_LIGHTBLUE = PatternFill("solid", start_color="DCEAF7", end_color="DCEAF7")

HEADER_FILL = PatternFill("solid", start_color=NAVY, end_color=NAVY)
HEADER_FONT = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=10)
BODY_FONT = Font(name=FONT_NAME, size=10)
BOLD_FONT = Font(name=FONT_NAME, size=10, bold=True)
SECTION_TITLE_FONT = Font(name=FONT_NAME, bold=True, size=12, color="1B2A4A")
THIN_BORDER = Border(bottom=Side(style="thin", color="E0E0E0"))

GREEN_FILL = PatternFill("solid", start_color="C6EFCE", end_color="C6EFCE")
YELLOW_FILL = PatternFill("solid", start_color="FFEB9C", end_color="FFEB9C")
RED_FILL = PatternFill("solid", start_color="FFC7CE", end_color="FFC7CE")
INSIGHT_FILL = PatternFill("solid", start_color="EFF3E6", end_color="EFF3E6")

STATUS_COLORS = {
    "New": "1F7A1F",
    "Pursuing": "1565C0",
    "Passed": "9E9E9E",
    "Bad Data": "C62828",
}

SCORE_BANDS = [("20-40", 20, 40), ("40-60", 40, 60), ("60-80", 60, 80), ("80-100", 80, 100)]
TOTAL_COLS = 20


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_all_candidates():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    c.id AS candidate_id,
                    c.company_name, c.state, c.industry, c.company_type,
                    c.founded_year, c.years_in_business, c.founder_name,
                    c.founder_led, c.family_owned, c.founder_age_estimate,
                    c.ownership_status, c.ownership_tenure_years,
                    c.seller_readiness_score, rs.status AS review_status,
                    rs.comments AS review_notes,
                    c.first_seen_date, c.last_seen_date,
                    e.why_selected, e.evidence_summary, e.one_line_reason, e.raw_evidence
                FROM candidates c
                LEFT JOIN review_status rs ON rs.candidate_id = c.id
                LEFT JOIN LATERAL (
                    SELECT * FROM evidence ev WHERE ev.candidate_id = c.id
                    ORDER BY ev.created_at DESC LIMIT 1
                ) e ON true
                ORDER BY c.seller_readiness_score DESC NULLS LAST
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def fetch_last_week_snapshot():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.pipeline_runs') IS NOT NULL AS exists")
            if not cur.fetchone()["exists"]:
                return None
            target_date = datetime.now().date() - timedelta(days=7)
            cur.execute(
                """
                SELECT * FROM pipeline_runs
                ORDER BY ABS(run_date - %s::date) ASC
                LIMIT 1
                """,
                (target_date,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def autosize_columns(ws, widths):
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def score_fill(score):
    if score is None:
        return None
    if score >= 70:
        return GREEN_FILL
    if score >= 40:
        return YELLOW_FILL
    return RED_FILL


def status_font(status):
    color = STATUS_COLORS.get(status, "424242")
    return Font(name=FONT_NAME, size=10, bold=True, color=color)


def delta_text(current, previous):
    if previous is None:
        return ""
    diff = current - previous
    if diff > 0:
        return f"\u2191 {diff}"
    if diff < 0:
        return f"\u2193 {abs(diff)}"
    return "\u2014 0"


def style_chart(chart):
    chart.y_axis.majorGridlines = None
    chart.x_axis.majorGridlines = None
    chart.y_axis.delete = True
    chart.x_axis.delete = False
    chart.graphical_properties = None


# ---------------------------------------------------------------------------
# Display-layer state normalization. NOTE: this is a patch, not the real
# fix - the real fix belongs upstream in signal_extractor.py. Keep this
# even after that lands; it's harmless on already-clean input and
# protects the dashboard from any inconsistency that slips through.
# ---------------------------------------------------------------------------
US_STATE_ABBREV_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def normalize_state_name(state):
    """
    Collapses abbreviation/full-name inconsistencies (e.g. "FL" and
    "Florida") so they group together in charts and counts instead of
    appearing as separate entries. Returns "Unknown" for blank/missing.
    """
    if not state or not str(state).strip():
        return "Unknown"
    state = str(state).strip()
    if state.upper() in US_STATE_ABBREV_TO_NAME:
        return US_STATE_ABBREV_TO_NAME[state.upper()]
    return state.title()


def build_dashboard_sheet(wb, candidates, last_week):
    ws = wb.create_sheet("Dashboard", 0)
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:F1")
    title_cell = ws["A1"]
    title_cell.value = "Business Acquisition Targeting Dashboard"
    title_cell.font = WHITE_FONT
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    ws.merge_cells("A2:F2")
    sub_cell = ws["A2"]
    sub_cell.value = "Surface family-owned, founder-led businesses that fit the acquisition profile"
    sub_cell.font = WHITE_SUBFONT
    sub_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    # --- Geography Covered ---
    _states_seen = sorted({
        normalize_state_name(c.get("state")) for c in candidates
        if c.get("state")
    } - {"Unknown"})

    ws.merge_cells("H1:I1")
    geo_label_cell = ws["H1"]
    geo_label_cell.value = "Geography:"
    geo_label_cell.font = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=10)
    geo_label_cell.alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells("H2:I2")
    geo_value_cell = ws["H2"]
    geo_value_cell.value = ", ".join(_states_seen) if _states_seen else "N/A"
    geo_value_cell.font = Font(name=FONT_NAME, color="FFFFFF", size=10)
    geo_value_cell.alignment = Alignment(horizontal="left", vertical="center")

    separator_border = Border(right=Side(style="thin", color="3D4A6B"))
    for row in (1, 2):
        ws.cell(row=row, column=9).border = separator_border

    ws["J1"].value = "Data as of:"
    ws["J1"].font = WHITE_SMALL
    ws["J1"].alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells("J2:K2")
    ws["J2"].value = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    ws["J2"].font = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=11)
    ws["J2"].alignment = Alignment(horizontal="left", vertical="center")

    # --- banner now ends at column K (was L) ---
    BANNER_COLS = 11  # K is column 11
    for row in range(1, 6):
        for col in range(1, BANNER_COLS + 1):
            ws.cell(row=row, column=col).fill = NAVY_FILL
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 18

    total_targets = len(candidates)
    new_this_week = sum(1 for c in candidates if c.get("first_seen_date") == datetime.now().date())
    shortlisted = sum(1 for c in candidates if c.get("review_status") == "Pursuing")
    in_review = sum(1 for c in candidates if c.get("review_status") == "New")
    reviewed = sum(1 for c in candidates if c.get("review_status") in ("Pursuing", "Passed", "Bad Data"))

    ws.row_dimensions[3].height = 4
    ws.row_dimensions[4].height = 24
    ws.row_dimensions[5].height = 4

    founder_led_count = sum(1 for c in candidates if c.get("founder_led") == "Yes")
    family_owned_count = sum(1 for c in candidates if c.get("family_owned") == "Yes")
    scored_only = [c.get("seller_readiness_score") for c in candidates if c.get("seller_readiness_score") is not None]
    highest_score = max(scored_only) if scored_only else 0

    pill_defs = [
    ("Founder-Led", founder_led_count, "2E7D8E"),
    ("Family-Owned", family_owned_count, "5B3A8E"), 
    ("Highest Score", highest_score, "1565C0"),
    ("New Today", new_this_week, "2E7D32"),
    ]
    # Pill widths sum to 11 (3+3+3+2) so the row ends at column K, matching
    # the rest of the banner - fixed: last pill narrowed from 3 to 2.
    pill_widths = [3, 3, 3, 2]
    start_col = 1
    for i, (label, count, color) in enumerate(pill_defs):
        width = pill_widths[i]
        end_col = start_col + width - 1
        ws.merge_cells(start_row=4, start_column=start_col, end_row=4, end_column=end_col)
        cell = ws.cell(row=4, column=start_col, value=f"  {label}:  {count}")
        cell.font = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=10)
        cell.fill = PatternFill("solid", start_color=color, end_color=color)
        cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        start_col = end_col + 1  # advance to the next pill's starting column

    kpi_defs = [
        ("\U0001F3AF Total Targets Found", total_targets, "All Time", CARD_BLUE, None),
        ("\u2795 New This Week", new_this_week, None, CARD_GREEN, "new_this_run"),
        ("\u2B50 Shortlisted", shortlisted, None, CARD_YELLOW, "shortlisted"),
        ("\U0001F4CB In Review", in_review, None, CARD_PURPLE, "in_review"),
        ("\u2705 Reviewed", reviewed, None, CARD_LIGHTBLUE, "reviewed"),
    ]

    card_row = 6
    card_height_rows = 4
    # Last card narrowed from width 3 to 2 so KPI row also ends at K.
    kpi_layout = [
        {"start_col": 1,  "width": 2},
        {"start_col": 3,  "width": 2},
        {"start_col": 5,  "width": 3},
        {"start_col": 8,  "width": 2},
        {"start_col": 10, "width": 2},
    ]

    for (label, value, static_caption, fill, lw_key), layout in zip(kpi_defs, kpi_layout):
        start_col = layout["start_col"]
        end_col = start_col + layout["width"] - 1

        for r in range(card_row, card_row + card_height_rows):
            ws.merge_cells(start_row=r, start_column=start_col, end_row=r, end_column=end_col)
            for c in range(start_col, end_col + 1):
                ws.cell(row=r, column=c).fill = fill

        ws.cell(row=card_row, column=start_col, value=label).font = Font(name=FONT_NAME, size=10, color="424242")
        ws.cell(row=card_row, column=start_col).alignment = Alignment(horizontal="left", indent=1, vertical="center")

        ws.cell(row=card_row + 1, column=start_col, value=value).font = Font(name=FONT_NAME, size=24, bold=True, color="1B2A4A")
        ws.cell(row=card_row + 1, column=start_col).alignment = Alignment(horizontal="left", indent=1, vertical="center")

        if static_caption:
            caption_text = static_caption
        elif last_week is not None and lw_key is not None:
            caption_text = f"vs Last Week: {delta_text(value, last_week.get(lw_key))}"
        else:
            caption_text = "vs Last Week: n/a (first run)"

        ws.cell(row=card_row + 2, column=start_col, value=caption_text).font = Font(name=FONT_NAME, size=9, italic=True, color="616161")
        ws.cell(row=card_row + 2, column=start_col).alignment = Alignment(horizontal="left", indent=1, vertical="center")

    ws.row_dimensions[card_row].height = 18
    ws.row_dimensions[card_row + 1].height = 30
    ws.row_dimensions[card_row + 2].height = 16
    ws.row_dimensions[card_row + 3].height = 8

    chart_data_row = card_row + card_height_rows + 1

    state_counts = {}
    for c in candidates:
        st = normalize_state_name(c.get("state"))
        state_counts[st] = state_counts.get(st, 0) + 1
    top_states = sorted(state_counts.items(), key=lambda x: -x[1])[:5]

    geo_header_row = chart_data_row
    ws.cell(row=geo_header_row, column=1, value="State").font = INVISIBLE_FONT
    ws.cell(row=geo_header_row, column=2, value="Count").font = INVISIBLE_FONT
    for i, (state, count) in enumerate(top_states, start=1):
        ws.cell(row=geo_header_row + i, column=1, value=state).font = INVISIBLE_FONT
        ws.cell(row=geo_header_row + i, column=2, value=count).font = INVISIBLE_FONT
    geo_last_row = geo_header_row + len(top_states)

    score_header_row = chart_data_row
    ws.cell(row=score_header_row, column=4, value="Band").font = INVISIBLE_FONT
    ws.cell(row=score_header_row, column=5, value="Count").font = INVISIBLE_FONT
    for i, (label, low, high) in enumerate(SCORE_BANDS, start=1):
        count = sum(1 for c in candidates if c.get("seller_readiness_score") is not None and low <= c["seller_readiness_score"] < high)
        ws.cell(row=score_header_row + i, column=4, value=label).font = INVISIBLE_FONT
        ws.cell(row=score_header_row + i, column=5, value=count).font = INVISIBLE_FONT
    score_last_row = score_header_row + len(SCORE_BANDS)

    industry_counts = {}
    for c in candidates:
        ind = c.get("industry") or "Unknown"
        ind = ind[:18] + "..." if len(ind) > 18 else ind
        industry_counts[ind] = industry_counts.get(ind, 0) + 1
    top_industries = sorted(industry_counts.items(), key=lambda x: -x[1])[:4]

    industry_header_row = chart_data_row
    ws.cell(row=industry_header_row, column=7, value="Industry").font = INVISIBLE_FONT
    ws.cell(row=industry_header_row, column=8, value="Count").font = INVISIBLE_FONT
    for i, (industry, count) in enumerate(top_industries, start=1):
        ws.cell(row=industry_header_row + i, column=7, value=industry).font = INVISIBLE_FONT
        ws.cell(row=industry_header_row + i, column=8, value=count).font = INVISIBLE_FONT
    industry_last_row = industry_header_row + len(top_industries)

    helper_block_last_row = max(geo_last_row, score_last_row, industry_last_row)
    for r in range(chart_data_row, helper_block_last_row + 1):
        ws.row_dimensions[r].height = 1

    pie = PieChart()
    pie.title = "TARGETS BY GEOGRAPHY"
    pie.legend.position="b"
    data = Reference(ws, min_col=2, min_row=geo_header_row, max_row=geo_last_row)
    cats = Reference(ws, min_col=1, min_row=geo_header_row + 1, max_row=geo_last_row)
    pie.add_data(data, titles_from_data=True)
    pie.set_categories(cats)
    pie.dataLabels = DataLabelList()
    pie.dataLabels.showPercent = True
    pie.dataLabels.showCatName = False
    pie.dataLabels.showSerName = False
    pie.dataLabels.showVal = False
    pie.dataLabels.showLegendKey = False
    pie.height = 7
    pie.width = 6
    ws.add_chart(pie, f"A{chart_data_row}")

    bar1 = BarChart()
    bar1.title = "SELLER READINESS SCORE DISTRIBUTION"
    bar1.style = 10
    bar1.legend = None
    bar1.gapWidth = 50
    data = Reference(ws, min_col=5, min_row=score_header_row, max_row=score_last_row)
    cats = Reference(ws, min_col=4, min_row=score_header_row + 1, max_row=score_last_row)
    bar1.add_data(data, titles_from_data=True)
    bar1.set_categories(cats)
    bar1.dataLabels = DataLabelList()
    bar1.dataLabels.showVal = True
    bar1.dataLabels.showCatName = False
    bar1.dataLabels.showSerName = False
    bar1.dataLabels.showLegendKey = False
    style_chart(bar1)
    bar1.height = 7
    bar1.width = 6
    ws.add_chart(bar1, f"C{chart_data_row}")

    bar2 = BarChart()
    bar2.type = "bar"
    bar2.title = "INDUSTRY BREAKDOWN"
    bar2.style = 11
    bar2.legend = None
    data = Reference(ws, min_col=8, min_row=industry_header_row, max_row=industry_last_row)
    cats = Reference(ws, min_col=7, min_row=industry_header_row + 1, max_row=industry_last_row)
    bar2.add_data(data, titles_from_data=True)
    bar2.set_categories(cats)
    bar2.dataLabels = DataLabelList()
    bar2.dataLabels.showVal = True
    bar2.y_axis.majorGridlines = None
    bar2.x_axis.majorGridlines = None

    bar2.y_axis.delete = True
    bar2.x_axis.delete = True
    bar2.dataLabels.showCatName = False
    bar2.dataLabels.showSerName = False
    bar2.dataLabels.showLegendKey = False
    style_chart(bar2)
    bar2.height = 7
    bar2.width = 7
    ws.add_chart(bar2, f"E{chart_data_row}")

    pct_founder_led = round(100 * sum(1 for c in candidates if c.get("founder_led") == "Yes") / total_targets, 0) if total_targets else 0
    pct_family_owned = round(100 * sum(1 for c in candidates if c.get("family_owned") == "Yes") / total_targets, 0) if total_targets else 0
    top_state_label = top_states[0][0] if top_states else "N/A"
    high_scorers = sum(1 for c in candidates if (c.get("seller_readiness_score") or 0) >= 80)
    top_industry = top_industries[0][0] if top_industries else "N/A"

    mini_cards = [
        ("📍 TOP GEOGRAPHY", top_state_label),
        ("⭐ HIGHEST SCORE", str(highest_score)),
        ("🏆 TOP INDUSTRY", top_industry),
    ]
    card_colors = [
    "E8F1FB",  # 📍 Top Geography (soft blue)
    "FFF4D6",  # ⭐ Highest Score (soft yellow)
    "EAF6EA",  # 🏆 Top Industry (soft green)
    ]
    card_start_rows = [11, 15, 19]

    for ((title, value), start_row, color) in zip(
        mini_cards,
        card_start_rows,
        card_colors
    ):

        if title == "🏆 TOP INDUSTRY":
            end_row = 22
        else:
            end_row = start_row + 2

        ws.merge_cells(
            start_row=start_row,
            start_column=8,     # H
            end_row=end_row,
            end_column=9        # I
        )

        cell = ws.cell(
            row=start_row,
            column=8
        )
        
        cell.value = f"{title}\n\n{value}"
        cell.font = Font(
        name=FONT_NAME,
        bold=True,
        size=11,
        color="1B2A4A"   # dark navy
        )
        cell.fill = PatternFill(
            "solid",
            start_color=color,
            end_color=color
        )


        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

        for r in range(start_row, end_row + 1):

            for c in range(8, 10):

                ws.cell(
                    row=r,
                    column=c
                ).border = Border(
                    left=Side(style="thin", color="D3D3D3"),
                    right=Side(style="thin", color="D3D3D3"),
                    top=Side(style="thin", color="D3D3D3"),
                    bottom=Side(style="thin", color="D3D3D3"),
                )
    insights_col = 10
    insights_row = chart_data_row
    insights_end_row = 22

    ws.merge_cells(start_row=insights_row, start_column=insights_col,
                    end_row=insights_row, end_column=insights_col + 1)
    heading_cell = ws.cell(row=insights_row, column=insights_col, value="Key Insights")
    heading_cell.font = Font(name=FONT_NAME, bold=True, size=11, color="FFFFFF")
    heading_cell.fill = HEADER_FILL
    heading_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[insights_row].height = 22

    insight_lines = [
        f"✓ Founder-Led: {pct_founder_led:.0f}%",
        f"🏠 Family-Owned: {pct_family_owned:.0f}%",
        f"📍 Top Geography: {top_state_label}",
        f"🆕 New Targets: {new_this_week}",
        f"⭐ High Scorers (80+): {high_scorers}",
    ]
        

    available_rows = insights_end_row - insights_row
    n = len(insight_lines)
    row_block = available_rows // n
    remainder = available_rows % n

    current_row = insights_row + 1
    for i, line in enumerate(insight_lines):
        this_block_size = row_block + (remainder if i == n - 1 else 0)
        block_start = current_row
        block_end = current_row + this_block_size - 1
        ws.merge_cells(start_row=block_start, start_column=insights_col,
                        end_row=block_end, end_column=insights_col + 1)
        cell = ws.cell(row=block_start, column=insights_col, value=f"\u2022 {line}")
        cell.font = Font(name=FONT_NAME, size=9)
        cell.alignment = Alignment(vertical="center", indent=1, wrap_text=True)
        for r in range(block_start, block_end + 1):
            ws.cell(row=r, column=insights_col).fill = INSIGHT_FILL
            ws.cell(row=r, column=insights_col + 1).fill = INSIGHT_FILL
            ws.row_dimensions[r].height = 16
        current_row = block_end + 1

    table_title_row = 24

    table_columns = [
        ("Rank", None, 6),
        ("Company Name", "company_name", 26),
        ("Founder Name", "founder_name", 20),
        ("Founder Age (Est.)", "founder_age_estimate", 14),
        ("Years in Business", "years_in_business", 14),
        ("State", "state", 10),
        ("Readiness Score", "seller_readiness_score", 13),
        ("Ownership Status", "ownership_status", 16),
        ("Status", "review_status", 12),
        ("Why Selected", "one_line_reason", 32),
        ("Ownership Tenure", "ownership_tenure_years", 14),
    ]
    header_row = table_title_row + 1
    for i, (label, _, _) in enumerate(table_columns, start=1):
        cell = ws.cell(row=header_row, column=i, value=label)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[header_row].height = 26

    sorted_candidates = sorted(
        candidates,
        key=lambda r: (r.get("seller_readiness_score") is None, -(r.get("seller_readiness_score") or 0)),
    )

    for idx, row in enumerate(sorted_candidates, start=1):
        r = header_row + idx
        rank_cell = ws.cell(row=r, column=1, value=idx)
        rank_cell.font = BOLD_FONT
        rank_cell.alignment = Alignment(horizontal="center", vertical="center")
        for c, (_, key, _) in enumerate(table_columns[1:], start=2):
            value = row.get(key)
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            if key in ("years_in_business", "seller_readiness_score"):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(
                    wrap_text=(key in ("one_line_reason", "founder_name", "company_name")),
                    vertical="center"
                )
            if key == "seller_readiness_score":
                fill = score_fill(value)
                if fill:
                    cell.fill = fill
                cell.font = BOLD_FONT
            if key == "review_status":
                cell.font = status_font(value)

    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(table_columns))}{header_row}"

    autosize_columns(ws, [w for _, _, w in table_columns] + [12] * (TOTAL_COLS - len(table_columns)))

    return ws


DB_COLUMNS = [
    ("Company Name", "company_name", 28), ("State", "state", 12),
    ("Industry", "industry", 18), ("Company Type", "company_type", 14),
    ("Founded Year", "founded_year", 12), ("Years in Business", "years_in_business", 14),
    ("Founder Name", "founder_name", 20), ("Founder Led", "founder_led", 12),
    ("Family Owned", "family_owned", 12), ("Founder Age Est.", "founder_age_estimate", 14),
    ("Seller Readiness Score", "seller_readiness_score", 16), ("Review Status", "review_status", 14),
    ("First Seen", "first_seen_date", 14), ("Last Seen", "last_seen_date", 14),
]


def build_companies_db_sheet(wb, candidates):
    ws = wb.create_sheet("Companies_DB")
    num_cols = len(DB_COLUMNS)
    for i, (label, _, _) in enumerate(DB_COLUMNS, start=1):
        cell = ws.cell(row=1, column=i, value=label)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for r, row in enumerate(candidates, start=2):
        for c, (_, key, _) in enumerate(DB_COLUMNS, start=1):
            cell = ws.cell(row=r, column=c, value=row.get(key))
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            if key == "seller_readiness_score":
                fill = score_fill(row.get(key))
                if fill:
                    cell.fill = fill
    autosize_columns(ws, [w for _, _, w in DB_COLUMNS])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(num_cols)}1"
    return ws


TOP_N = 10

from openpyxl.worksheet.datavalidation import DataValidation
FEEDBACK_OPTIONS = ["New", "Pursuing", "Passed", "Bad Data"]


def build_top_companies_sheet(wb, candidates):
    ws = wb.create_sheet("Top_Companies")
    scored = [c for c in candidates if c.get("seller_readiness_score") is not None]
    top = sorted(scored, key=lambda r: -r["seller_readiness_score"])[:TOP_N]

    columns = [
        ("Rank", None, 6),
        ("Company Name", "company_name", 26),
        ("Score", "seller_readiness_score", 10),
        ("State", "state", 10),
        ("Why Selected", "why_selected", 55),
        ("Evidence Summary", "evidence_summary", 55),
        ("One-line Reason", "one_line_reason", 45),
        ("Feedback", "review_status", 14),
        ("Notes", "review_notes", 35),
        ("_candidate_id", "candidate_id", 1),
    ]

    for i, (label, _, _) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=i, value=label)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    dv = DataValidation(
        type="list",
        formula1=f'"{",".join(FEEDBACK_OPTIONS)}"',
        allow_blank=True,
        showDropDown=False,
    )
    ws.add_data_validation(dv)

    feedback_col_idx = next(i for i, (label, _, _) in enumerate(columns, start=1) if label == "Feedback")
    feedback_col_letter = get_column_letter(feedback_col_idx)

    for idx, row in enumerate(top, start=1):
        r = idx + 1
        ws.cell(row=r, column=1, value=idx).font = BOLD_FONT
        for c, (label, key, _) in enumerate(columns[1:], start=2):
            if key == "review_status":
                value = row.get("review_status") or "New"
            elif key == "review_notes":
                value = row.get("review_notes") or ""
            else:
                value = row.get(key)
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if key == "seller_readiness_score":
                fill = score_fill(row.get(key))
                if fill:
                    cell.fill = fill
                cell.font = BOLD_FONT
        ws.row_dimensions[r].height = 90
        dv.add(f"{feedback_col_letter}{r}")

    autosize_columns(ws, [w for _, _, w in columns])

    id_col_idx = next(i for i, (label, _, _) in enumerate(columns, start=1) if label == "_candidate_id")
    ws.column_dimensions[get_column_letter(id_col_idx)].width = 0
    ws.column_dimensions[get_column_letter(id_col_idx)].hidden = True

    ws.freeze_panes = "A2"
    return ws


def generate_dashboard(output_file):
    candidates = fetch_all_candidates()
    last_week = fetch_last_week_snapshot()

    wb = Workbook()
    wb.remove(wb.active)

    build_dashboard_sheet(wb, candidates, last_week)
    build_companies_db_sheet(wb, candidates)
    build_top_companies_sheet(wb, candidates)

    wb.save(output_file)
    print(f"Saved dashboard workbook ({len(candidates)} total candidates) -> {output_file}")
    return output_file