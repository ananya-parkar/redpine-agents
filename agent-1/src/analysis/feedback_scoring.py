# agent-1/src/analysis/feedback_scoring.py
def feedback_adjustment(status):
    if status == "Pursuing":
        return +10

    if status == "Passed":
        return -25

    return 0