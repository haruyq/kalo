"""KALPA Stellar Point, reverse-engineered from server values (checked in tests/test_core.py).

rate is the in-game integer (1,000,000 = 100%). level is Map.Difficulty.
Bands follow the rank thresholds in Global.ScoreToResult (99/98/97/95%).
"""
# (lower bound in %, value at lower bound, slope per 1%)
BANDS = [(99, 2.0, 0.75), (98, 1.0, 0.75), (97, 0.0, 0.75), (95, -1.5, 0.5)]
TOP_N = 30  # profile SP = sum of best TOP_N records / TOP_N
COUNTED_MODES = (0, 1, 2)  # NORMAL/HARD/COSMOS; per map only the better of normal/lunatic counts


def stellar_point(level, rate, lunatic=False):
    r = rate / 10000
    if rate >= 1_000_000:
        bonus = 3.0
    else:
        # ponytail: below 95% is unobserved; extend when a record there shows up.
        lo, base, slope = next((b for b in BANDS if r >= b[0]), BANDS[-1])
        bonus = base + slope * (r - lo)
    return (level + bonus) * (1.1 if lunatic else 1.0)


def profile_sp(record_sps):
    return sum(sorted(record_sps, reverse=True)[:TOP_N]) / TOP_N

