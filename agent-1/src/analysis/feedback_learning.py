# agent-1/src/analysis/feedback_learning.py
from src.storage.postgres_storage import get_feedback_patterns

BAD_DATA_PENALTIES = {
    "WRONG_OWNER": 15,
    "NOT_HOTEL": 50,
    "DUPLICATE_LISTING": 25,
}

PASSED_PENALTIES = {
    "ECONOMY_BRAND": 10,
    "LOW_ROOM_COUNT": 5,
}


def build_feedback_rules():

    patterns = get_feedback_patterns()

    active_rules = {}

    for reason, count in patterns:

        if count < 3:
            continue

        active_rules[reason] = count
    
    print(
        "[ACTIVE FEEDBACK RULES]",
        active_rules
    )

    return active_rules


def apply_feedback_penalties(row, rules):

    print(
        row["hotel_name"],
        row.get("owner_confidence")
    )

    score_penalty = 0
    row["feedback_rule_applied"] = ""

    if "WRONG_OWNER" in rules:
        owner_confidence = (
            str(row.get("owner_confidence", ""))
            .strip()
            .lower()
        )

        if owner_confidence in [
            "low",
            "error",
            "not checked"
        ]:

            score_penalty += 15
            row["feedback_rule_applied"] = "WRONG_OWNER"

    if "NOT_HOTEL" in rules:

        if not row.get("is_hotel", True):
            score_penalty += 50

    if "DUPLICATE_LISTING" in rules:

        if row.get("duplicate_candidate"):
            score_penalty += 25

    row["feedback_penalty"] = score_penalty
    before_score = row["final_lead_score"]

    row["final_lead_score"] = max(
        0,
        row["final_lead_score"] - score_penalty
    )

    print(
        f"[FEEDBACK LEARNING] "
        f"{row['hotel_name']} | "
        f"before={before_score} | "
        f"penalty={score_penalty} | "
        f"after={row['final_lead_score']}"
    )

    return row