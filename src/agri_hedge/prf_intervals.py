"""PRF two-month index intervals (shared naming convention).

PRF divides the year into 11 overlapping two-month intervals. Everyone in this repo refers to an
interval by its NAME below (e.g. "Apr-May"). RMA's numeric interval codes (believed to be
625 = Jan-Feb ... 635 = Nov-Dec) are recorded here for joining against RMA files. Owner of this
file: the PRF calculator workstream (B4), which must confirm the codes against the Actuarial Data
Master / handbook and update VERIFIED below.
"""

INTERVAL_NAMES = [
    "Jan-Feb", "Feb-Mar", "Mar-Apr", "Apr-May", "May-Jun", "Jun-Jul",
    "Jul-Aug", "Aug-Sep", "Sep-Oct", "Oct-Nov", "Nov-Dec",
]

# Calendar months (1-12) covered by each interval.
INTERVAL_MONTHS = {name: (i + 1, i + 2) for i, name in enumerate(INTERVAL_NAMES)}

# RMA numeric codes (to confirm).
INTERVAL_CODES = {name: 625 + i for i, name in enumerate(INTERVAL_NAMES)}
CODE_TO_INTERVAL = {v: k for k, v in INTERVAL_CODES.items()}
VERIFIED = False


def overlaps(a: str, b: str) -> bool:
    """True if two intervals share a month (PRF forbids selecting overlapping intervals)."""
    return bool(set(INTERVAL_MONTHS[a]) & set(INTERVAL_MONTHS[b]))
