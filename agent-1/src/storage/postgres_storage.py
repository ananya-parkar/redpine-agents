# agent-1/src/storage/postgres_storage.py
import psycopg2
from src.core.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)
from src.collectors.property_records import normalize_address
from datetime import datetime
from src.storage.lead_key import build_lead_key
from dateutil.relativedelta import relativedelta

def get_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def insert_priority_leads(rows):
    enforce_pii_retention()
    print(
        "[DEBUG] rows received:",
        len(rows)
    )
    
    if not rows:
        return

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    for row in rows:
        llm = row.get("llm_analysis", {})
        print(
                row.get("hotel_name"),
                row.get("cmbs_watchlist_flag"),
                row.get("cmbs_delinquency_flag"),
                row.get("cmbs_special_servicing_flag"),
            )
        
        cur.execute(
        """
        SELECT final_lead_score,
            lead_status
        FROM hotel_leads
        WHERE lead_key=%s
        """,
        (build_lead_key(row),)
        )

        existing = cur.fetchone()
        row["suppress_digest"] = False

        if existing:

            old_score, status = existing

            # --------------------
            # FEEDBACK LOOP
            # --------------------

            if status == "PURSUING":
                row["suppress_digest"] = True

            if status == "PASSED":
                row["final_lead_score"] -= 25

            # --------------------
            # RESURFACING
            # --------------------
            old_score = old_score or 0
            score_delta = abs(
                float(row["final_lead_score"])
                - float(old_score)
            )

            if score_delta < 10:
                row["suppress_digest"] = True

            if not row["suppress_digest"]:
                row["last_resurfaced"] = datetime.utcnow()
            
        row["last_score"] = row["final_lead_score"]
        row.setdefault("last_resurfaced", None)

        print(
            "[DEBUG]",
            row.get("hotel_name"),
            row.get("last_score"),
            row.get("last_resurfaced"),
            row.get("suppress_digest")
        )

        cleanup_due_date = datetime.utcnow() + relativedelta(months=12)

        cur.execute(
        """
        INSERT INTO hotel_leads (
            hotel_name,
            address,
            lead_key,
            final_lead_score,
            opportunity_score,
            owner_name,
            franchise_affiliated,
            current_brand,
            lead_reason,

            distress_probability,
            seller_fatigue_probability,
            review_summary,
            investment_thesis,
            recommended_action,
            distress_summary,
            llm_star_rating,

            ownership_since,
            ownership_length_years,
            attom_year_built,

            cmbs_watchlist,
            cmbs_delinquent,
            cmbs_special_servicing,
            price_tier,
            first_surfaced,
            last_score,
            last_resurfaced,
            feedback_penalty,
            feedback_rule_applied,
            cleanup_due_date,
            pii_retention_exempt
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,
            %s,%s
        )
        ON CONFLICT(lead_key)
        DO UPDATE SET
            final_lead_score = EXCLUDED.final_lead_score,
            opportunity_score = EXCLUDED.opportunity_score,

            owner_name = EXCLUDED.owner_name,
            ownership_since = EXCLUDED.ownership_since,
            distress_probability = EXCLUDED.distress_probability,
            seller_fatigue_probability = EXCLUDED.seller_fatigue_probability,

            review_summary = EXCLUDED.review_summary,
            investment_thesis = EXCLUDED.investment_thesis,
            recommended_action = EXCLUDED.recommended_action,
            distress_summary = EXCLUDED.distress_summary,
            llm_star_rating = EXCLUDED.llm_star_rating,
            lead_reason = EXCLUDED.lead_reason,

            ownership_length_years = EXCLUDED.ownership_length_years,
            attom_year_built = EXCLUDED.attom_year_built,

            cmbs_watchlist = EXCLUDED.cmbs_watchlist,
            cmbs_delinquent = EXCLUDED.cmbs_delinquent,
            cmbs_special_servicing = EXCLUDED.cmbs_special_servicing,
            price_tier = EXCLUDED.price_tier,
            last_score = EXCLUDED.last_score,
            last_resurfaced = EXCLUDED.last_resurfaced,
            feedback_penalty = EXCLUDED.feedback_penalty,
            feedback_rule_applied = EXCLUDED.feedback_rule_applied,
            cleanup_due_date = EXCLUDED.cleanup_due_date,
            pii_retention_exempt = EXCLUDED.pii_retention_exempt    
        """,
        (
            row.get("hotel_name"),
            row.get("address"),
            build_lead_key(row),
            row.get("final_lead_score"),
            llm.get("opportunity_score"),
            row.get("owner_name"),
            row.get("franchise_affiliated"),
            row.get("current_brand"),
            row.get("lead_reason"),
            llm.get("distress_probability"),
            llm.get("seller_fatigue_probability"),
            llm.get("review_summary"),
            llm.get("investment_thesis"),
            llm.get("recommended_action"),
            llm.get("distress_summary"),
            llm.get("llm_star_rating"),
            row.get("ownership_since") or None,
            int(row["ownership_length_years"])
            if str(row.get("ownership_length_years", "")).isdigit()
            else None,

            int(row["attom_year_built"])
            if str(row.get("attom_year_built", "")).isdigit()
            else None,

            bool(row.get("cmbs_watchlist")),
            bool(row.get("cmbs_delinquent")),
            bool(row.get("cmbs_special_servicing")),
            row.get("price_tier"),
            datetime.utcnow(),
            row.get("last_score"),
            row.get("last_resurfaced"),
            row.get("feedback_penalty", 0),
            row.get("feedback_rule_applied"),
            cleanup_due_date,
            False,
        )
    )
        if cur.rowcount > 0:
            inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f"[POSTGRES] Inserted {inserted} priority leads", flush=True)

def get_existing_addresses():

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT address
        FROM hotel_leads
        """
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return {row[0].lower().strip() for row in rows if row[0]}

def update_lead_status(address, status):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE hotel_leads
        SET lead_status=%s
        WHERE address=%s
        """,
        (status, address)
    )

    conn.commit()
    cur.close()
    conn.close()

def get_existing_leads():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            lead_key,
            final_lead_score,
            lead_status
        FROM hotel_leads
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {
        lead_key: {
            "score": score,
            "status": status
        }
        for lead_key, score, status in rows
    }

def update_feedback(
    hotel_name,
    status,
    reason,
    notes
):
    reason = normalize_feedback_reason(reason)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE hotel_leads
        SET
            lead_status=%s,
            feedback_reason=%s,
            feedback_notes=%s,
            pii_retention_exempt=%s
        WHERE hotel_name=%s
        """,
        (
            status,
            reason,
            notes,
            status == "PURSUING",
            hotel_name
        )
    )

    conn.commit()
    cur.close()
    conn.close()
def get_feedback_patterns():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            feedback_reason,
            COUNT(*)
            FROM hotel_leads
            WHERE lead_status='BAD_DATA'
            GROUP BY feedback_reason
            HAVING COUNT(*) >= 3
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

FEEDBACK_REASON_MAP = {
    "wrong owner": "WRONG_OWNER",
    "owner mismatch": "WRONG_OWNER",
    "incorrect owner": "WRONG_OWNER",
    "not hotel": "NOT_HOTEL",
    "duplicate": "DUPLICATE_LISTING",
    "duplicate listing": "DUPLICATE_LISTING",
}

def normalize_feedback_reason(reason):
    if not reason:
        return ""
    key = str(reason).strip().lower()
    return FEEDBACK_REASON_MAP.get(
        key,
        key.upper()
    )

def enforce_pii_retention():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE hotel_leads
        SET
            owner_name = NULL
        WHERE
            COALESCE(pii_retention_exempt, FALSE) = FALSE
            AND first_surfaced <= NOW() - INTERVAL '12 months'
            AND owner_name IS NOT NULL
        """
    )

    cleaned = cur.rowcount

    conn.commit()
    cur.close()
    conn.close()

    print(
        f"[PII RETENTION] Cleaned PII for {cleaned} leads",
        flush=True
    )

if __name__ == "__main__":
    conn = get_connection()
    print("Postgres Connected Successfully")
    conn.close()