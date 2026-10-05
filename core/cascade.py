"""Cascade eligibility for Turkish short-stay visas, from Decision C(2025) 4694.

The ladder moves forward only from a lawfully used previous visa, and only
inside the time limit that follows its expiry. Consulates can still decide
differently.
"""

from datetime import date

GUARANTEE = "Consulates can still decide differently — this is not a guarantee."

# Previous visa the traveller already held → next step, and how many years
# after expiry that step stays open.
_NEXT = {
    "single": ("6 months", 1),
    "6m": ("1 year", 2),
    "1y": ("3 years", 2),
    "3y": ("5 years", 2),
}


def cascade_eligibility(previous, expired_on, lawful, today=None):
    """Return whether the traveller may be eligible for the next ladder step.

    ``previous`` is none, single, 6m, 1y, or 3y. ``expired_on`` is the previous
    visa's expiry date. ``lawful`` is True, False, or None when they have not
    answered. A visa that has not expired yet is still inside the window.
    """
    if today is None:
        today = date.today()

    if previous == "none":
        return _no(
            "A cascade visa starts from a previous visa. With no earlier visa, this ladder does not start yet."
        )
    if previous not in _NEXT:
        return _no("Choose the validity of the previous visa.")
    if lawful is None:
        return _no("Choose whether the previous visa was used lawfully.")
    if not lawful:
        return _no(
            "The cascade applies only when the previous visa was used lawfully — no overstay or misuse."
        )
    if expired_on is None:
        return _no("Enter the expiry date of the previous visa.")

    step, years = _NEXT[previous]
    if expired_on <= today and expired_on < _cutoff(today, years):
        span = "1 year" if years == 1 else f"{years} years"
        return _no(f"more than {span} since expiry")
    adjective = {
        "6 months": "6-month",
        "1 year": "1-year",
        "3 years": "3-year",
        "5 years": "5-year",
    }[step]
    return {
        "eligible": True,
        "step": step,
        "reason": f"You may be eligible for a {adjective} multiple-entry visa.",
    }


def _cutoff(today, years):
    """The oldest expiry date still inside a window of ``years`` calendar years."""
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return date(today.year - years, 2, 28)


def _no(reason):
    return {"eligible": False, "step": None, "reason": reason}
