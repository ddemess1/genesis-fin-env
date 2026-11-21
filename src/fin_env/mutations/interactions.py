"""INT1 / INT2 are compositions of base mutators (see plan._int1, plan._int2).

INT1: PARTIAL/MISSING_ALLOCATION then WRONG_FX_DATE (next business day's rate) on the SAME foreign
      payment that was received in the last 24 hours of the period (partial payment in another
      currency at the period boundary).
INT2: DUPLICATE_INVOICE whose clone is issued in the next period (inside the +3 day window),
      then PERIOD_CUTOFF on that clone (its postings are back-dated into the period).
Each component has its own MutationRecord; both share a group_id.
"""
from .plan import _int1, _int2  # noqa: F401
