"""
Deterministic risk checks. No LLM involved here, so these results are
reproducible and auditable — which matters for a BFSI workflow.

Note on a bug carried over from the notebook: check_income_loan_ratio
returned a success string ("Loan amount is within the ratio") even when
nothing was wrong, and detect_risk_flags appended any truthy value. Every
application therefore came back with a risk flag. Here the check returns
None when the ratio is fine, so only real problems become flags.
"""

from typing import Any, Dict, List, Optional

from config import settings

REQUIRED_FIELDS = [
    "applicant_name",
    "age",
    "monthly_income",
    "loan_amount",
    "loan_purpose",
]

UNUSUAL_PURPOSE_TERMS = [
    "unknown",
    "gambling",
    "betting",
    "speculation",
    "crypto",
]


def _to_number(value: Any) -> Optional[float]:
    """Turn '₹45,000' or '45000' or 45000 into 45000.0, else None."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    cleaned = (
        str(value)
        .replace(",", "")
        .replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .strip()
    )

    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def check_missing_fields(application_data: Dict[str, Any]) -> List[str]:
    missing = []

    for field in REQUIRED_FIELDS:
        value = application_data.get(field)
        if value is None or str(value).strip() == "":
            missing.append(field)

    return missing


def check_income_loan_ratio(
    application_data: Dict[str, Any],
) -> Optional[str]:
    """Return a flag message, or None when the ratio is acceptable."""
    income = _to_number(application_data.get("monthly_income"))
    loan_amount = _to_number(application_data.get("loan_amount"))

    if income is None or loan_amount is None:
        # Missing-field check already reports absent values.
        if application_data.get("monthly_income") is not None and income is None:
            return "Monthly income could not be read as a number."
        if application_data.get("loan_amount") is not None and loan_amount is None:
            return "Loan amount could not be read as a number."
        return None

    if income <= 0:
        return "Reported monthly income is zero or negative."

    ratio = loan_amount / income

    if ratio > settings.MAX_LOAN_TO_INCOME_RATIO:
        return (
            f"Loan amount is {ratio:.1f}x monthly income, above the "
            f"{settings.MAX_LOAN_TO_INCOME_RATIO:.0f}x threshold."
        )

    return None


def check_loan_purpose(
    application_data: Dict[str, Any],
) -> Optional[str]:
    purpose = application_data.get("loan_purpose")

    if not purpose:
        return None  # Covered by the missing-field check.

    purpose_lower = str(purpose).lower()

    for term in UNUSUAL_PURPOSE_TERMS:
        if term in purpose_lower:
            return f"Potentially unusual loan purpose: {purpose}"

    return None


def detect_risk_flags(application_data: Dict[str, Any]) -> List[str]:
    """Run every rule and collect the flags that fired."""
    flags: List[str] = []

    for field in check_missing_fields(application_data):
        flags.append(f"Missing required field: {field}")

    for check in (check_income_loan_ratio, check_loan_purpose):
        result = check(application_data)
        if result:
            flags.append(result)

    if application_data.get("income_proof_present") is False:
        flags.append("Income proof is missing.")

    return flags


def loan_to_income_ratio(
    application_data: Dict[str, Any],
) -> Optional[float]:
    """Exposed separately so the UI can display the number."""
    income = _to_number(application_data.get("monthly_income"))
    loan_amount = _to_number(application_data.get("loan_amount"))

    if not income or loan_amount is None or income <= 0:
        return None

    return round(loan_amount / income, 2)
