
def check_eligibility(user, scheme):
    """
    Basic eligibility screening for the Government Scheme Finder.

    Returns a dictionary containing the screening result and explanations.
    This does not guarantee official eligibility.
    """
    result = {
        "eligible": False,
        "status": "needs_review",
        "reasons": [],
        "checks": []
    }

    if not scheme.active:
        result["status"] = "inactive"
        result["reasons"].append("This scheme is currently inactive.")
        return result

    result["checks"].append("Scheme is active.")

    # Check income only when the scheme defines an income limit.
    max_income = scheme.max_income
    user_income = getattr(user, "income", None)

    if max_income is not None:
        if user_income is None:
            result["reasons"].append(
                "Your income must be provided to check the income limit."
            )
            result["checks"].append("Income requirement needs verification.")
            return result

        if user_income > max_income:
            result["status"] = "not_matched"
            result["reasons"].append(
                f"Your recorded income exceeds the scheme's "
                f"configured limit of ₹{max_income:,.0f}."
            )
            return result

        result["checks"].append("Recorded income is within the configured limit.")
    else:
        result["checks"].append(
            "No income limit is configured in this project's database."
        )

    result["status"] = "needs_review"
    result["reasons"].append(
        "Review the official eligibility rules, including any age, "
        "occupation, residence, category, and documentation requirements."
    )

    return result


def is_eligible(user, scheme):
    """
    Backward-compatible basic filter.

    True means the scheme passes the configured screening checks,
    not that the user is officially eligible.
    """
    result = check_eligibility(user, scheme)

    return result["status"] == "needs_review"
