"""PRF two-month index intervals (shared naming convention).

PRF divides the year into 11 overlapping two-month intervals. Everyone in this repo refers to an
interval by its NAME below (e.g. "Apr-May"). RMA's numeric interval codes are recorded here for
joining against RMA files. Owner of this file: the PRF calculator workstream (B4).

Codes VERIFIED on 2026-10-29 against two primary sources:
  * RMA Actuarial Data Master, table A00480 "Interval" for reinsurance years 2025 and 2026
    (files 2025_ADM_YTD.zip and 2026_ADM_YTD.zip, member *_A00480_Interval_YTD.txt):
    625 "JAN - FEB INDEX INTERVAL" (abbreviation JAN-FEB, start 0101) ... 635 "NOV - DEC INDEX
    INTERVAL" (NOV-DEC, start 1101). scripts/pull_prf_actuarial.py re-checks this on every run.
  * FCIC-18150 Rainfall Index Handbook (2026), Exhibit 5 D(3): "index interval 628 (April - May)
    and 631 (July - August)".
The same codes appear in ADM A00030 (Interval Code of every PRF insurance offer) and in the PRF
Decision Support Tool API.
"""

INTERVAL_NAMES = [
    "Jan-Feb", "Feb-Mar", "Mar-Apr", "Apr-May", "May-Jun", "Jun-Jul",
    "Jul-Aug", "Aug-Sep", "Sep-Oct", "Oct-Nov", "Nov-Dec",
]

# Calendar months (1-12) covered by each interval.
INTERVAL_MONTHS = {name: (i + 1, i + 2) for i, name in enumerate(INTERVAL_NAMES)}

# RMA numeric codes (confirmed, see module docstring).
INTERVAL_CODES = {name: 625 + i for i, name in enumerate(INTERVAL_NAMES)}
CODE_TO_INTERVAL = {v: k for k, v in INTERVAL_CODES.items()}
VERIFIED = True


def overlaps(a: str, b: str) -> bool:
    """True if two intervals share a month (PRF forbids selecting overlapping intervals)."""
    return bool(set(INTERVAL_MONTHS[a]) & set(INTERVAL_MONTHS[b]))
