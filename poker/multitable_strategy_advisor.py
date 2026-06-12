"""
Multitable Strategy Advisor (multitable_strategy_advisor.py)

Playing multiple tables simultaneously requires simplifying strategy.
At 1 table: complex reads, bluffs, mixed strategies.
At 4+ tables: TAG simplification, value-only, avoid complex multi-street plans.

PROVEN GUIDELINES (online grinders):
  1 table:    Full GTO / creative play. 150-250 hands/hour.
  2-3 tables: Slight simplification. Some reads possible. 300-500 h/h.
  4-6 tables: TAG strategy. Avoid complex bluffs. 600-900 h/h.
  7-10 tables: Very tight, value-heavy. Minimal creativity. 1000-1500 h/h.
  10+ tables: Near robotic. Only nut situations. Mass-tabler profile.

WIN RATE TRADEOFF:
  Win rate (BB/100) typically decreases with more tables.
  Total earnings (BB/hour) may increase up to an optimal point, then falls.
  Optimal point varies by player skill and game type.

  Typical: WR drops ~0.5-1.0 BB/100 per 3 additional tables.
  Optimal table count maximizes BB/hour, not BB/100.

Usage:
    from poker.multitable_strategy_advisor import advise_multitable, MultitableAdvice, mt_one_liner

    advice = advise_multitable(
        n_tables=6,
        current_bb100=3.5,
        vpip=26.0,
        game_format='6max',
        hands_per_hour_single=250,
    )
    print(mt_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List, Dict


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Approximate hands/hour per table count tier
_HANDS_PER_HOUR_TABLE = {
    1:   250,
    2:   240,
    3:   220,
    4:   210,
    6:   200,
    8:   190,
    10:  180,
    12:  170,
    16:  160,
}

# BB/100 drop per additional table (cumulative from baseline)
# Table 1 = 0.0 (baseline), each 3 more tables = -0.8 BB/100
_WR_DROP_PER_TABLE = 0.27   # BB/100 per additional table (diminishing after 3)

# Strategy tier by table count
def _strategy_tier(n: int) -> str:
    if n <= 1:  return 'full_gto'
    if n <= 3:  return 'creative_tag'
    if n <= 6:  return 'solid_tag'
    if n <= 10: return 'nitty_tag'
    return 'mass_table'

_TIER_DESC = {
    'full_gto':    'Full GTO / read-based. Complex bluffs, mixed strategies, exploits. Full attention.',
    'creative_tag': 'Slightly simplified. Reads still possible. Reduce complex multi-street bluffs.',
    'solid_tag':   'TAG strategy. Value-heavy. Avoid ambiguous bluffs. Keep ranges straightforward.',
    'nitty_tag':   'Very tight. Near value-only. Avoid marginal spots. Nitty-TAG is fine here.',
    'mass_table':  'Robotic. Open-fold-bet-value only. Complex spots: default to fold/check.',
}

_VPIP_ADJUSTMENT = {
    'full_gto':    0,
    'creative_tag': -1,
    'solid_tag':   -3,
    'nitty_tag':   -5,
    'mass_table':  -8,
}

_STRATEGY_DO = {
    'full_gto':    ['Full range opens', 'Balanced bluffs', 'Complex check-raises', 'Timing reads', 'Multi-street bluffs'],
    'creative_tag': ['Near-full range', 'Value + clear bluffs', 'Standard check-raises', 'Some reads'],
    'solid_tag':   ['Standard opens', 'Value bets + semi-bluffs', 'Simple lines only', 'Reduce complex spots'],
    'nitty_tag':   ['Tight opens', 'Value-heavy', 'Bet/fold most spots', 'Avoid marginal decisions'],
    'mass_table':  ['Premium hands only', 'Pure value betting', 'Fold everything marginal', 'Simple click-fold'],
}

_STRATEGY_DONT = {
    'full_gto':    [],
    'creative_tag': ['Complex 3-street bluffs', 'Thin slow-plays'],
    'solid_tag':   ['Bluffs without equity', 'Slow plays', 'Complex check-raise bluffs', '3-way bluffs'],
    'nitty_tag':   ['Any bluffs', 'Marginal spots', 'Limping', 'Creative lines'],
    'mass_table':  ['Bluffs ever', 'Post-flop creativity', 'Slow plays', 'Thin value bets'],
}


def _estimate_hands_per_hour(n_tables: int, hands_single: int) -> int:
    """Estimate total hands/hour given table count."""
    if n_tables <= 0:
        return 0
    # Efficiency decreases with more tables due to decision time pressure
    efficiencies = {1: 1.0, 2: 0.97, 3: 0.93, 4: 0.87, 6: 0.80, 8: 0.72, 10: 0.64, 12: 0.58, 16: 0.52}
    eff = efficiencies.get(n_tables)
    if eff is None:
        # Interpolate
        keys = sorted(efficiencies.keys())
        for i in range(len(keys) - 1):
            if keys[i] <= n_tables <= keys[i+1]:
                frac = (n_tables - keys[i]) / (keys[i+1] - keys[i])
                eff = efficiencies[keys[i]] + frac * (efficiencies[keys[i+1]] - efficiencies[keys[i]])
                break
        else:
            eff = 0.45
    return int(n_tables * hands_single * eff)


def _estimate_wr_at_n_tables(baseline_bb100: float, n_tables: int) -> float:
    """Estimate BB/100 at n tables, given single-table baseline."""
    if n_tables <= 1:
        return baseline_bb100
    # WR drops as attention splits
    additional = n_tables - 1
    drop = min(additional * _WR_DROP_PER_TABLE, baseline_bb100 * 0.80)  # cap at 80% of baseline
    return round(baseline_bb100 - drop, 2)


def _optimal_table_count(baseline_bb100: float, hands_single: int) -> int:
    """Find table count that maximizes BB/hour (not BB/100)."""
    best_bbph = 0.0
    best_n = 1
    for n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16]:
        wr = _estimate_wr_at_n_tables(baseline_bb100, n)
        hph = _estimate_hands_per_hour(n, hands_single)
        bbph = wr / 100 * hph
        if bbph > best_bbph:
            best_bbph = bbph
            best_n = n
    return best_n


# --------------------------------------------------------------------------
# Dataclass
# --------------------------------------------------------------------------

@dataclass
class MultitableAdvice:
    # Inputs
    n_tables: int
    current_bb100: float
    vpip: float
    game_format: str
    hands_per_hour_single: int

    # Analysis
    strategy_tier: str          # 'full_gto', 'creative_tag', 'solid_tag', etc.
    tier_description: str
    estimated_wr_at_n: float    # BB/100 estimated at current n_tables
    estimated_hands_per_hour: int
    estimated_bb_per_hour: float

    optimal_table_count: int    # table count maximizing BB/hour
    optimal_bb_per_hour: float

    adjusted_vpip_target: float # recommended VPIP at this table count
    do_list: List[str]          # things to do at this table count
    dont_list: List[str]        # things to avoid

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Main function
# --------------------------------------------------------------------------

def advise_multitable(
    n_tables: int = 4,
    current_bb100: float = 4.0,
    vpip: float = 26.0,
    game_format: str = '6max',
    hands_per_hour_single: int = 250,
) -> MultitableAdvice:
    """
    Advise strategy adjustments for playing multiple tables simultaneously.

    Args:
        n_tables:              Current number of tables hero is playing
        current_bb100:         Hero's best known BB/100 win rate (single table estimate)
        vpip:                  Hero's current VPIP
        game_format:           '6max', 'full_ring', 'heads_up'
        hands_per_hour_single: Hero's hands/hour rate at one table

    Returns:
        MultitableAdvice
    """
    tier = _strategy_tier(n_tables)
    tier_desc = _TIER_DESC[tier]

    est_wr = _estimate_wr_at_n_tables(current_bb100, n_tables)
    est_hph = _estimate_hands_per_hour(n_tables, hands_per_hour_single)
    est_bbph = round(est_wr / 100 * est_hph, 2)

    opt_n = _optimal_table_count(current_bb100, hands_per_hour_single)
    opt_wr = _estimate_wr_at_n_tables(current_bb100, opt_n)
    opt_hph = _estimate_hands_per_hour(opt_n, hands_per_hour_single)
    opt_bbph = round(opt_wr / 100 * opt_hph, 2)

    vpip_adj = vpip + _VPIP_ADJUSTMENT[tier]
    do_list = _STRATEGY_DO[tier]
    dont_list = _STRATEGY_DONT[tier]

    reasoning = (
        f'{n_tables} tables: tier={tier}, estimated WR={est_wr:+.2f}BB/100, '
        f'HPH={est_hph}, BB/hour={est_bbph:+.2f}. '
        f'Optimal: {opt_n} tables (BB/hour={opt_bbph:+.2f}).'
    )

    if n_tables == opt_n:
        verdict = (
            f'{n_tables} TABLES: Already at optimal count for BB/hour. '
            f'Est WR={est_wr:+.2f}BB/100, {est_hph} h/hr = {est_bbph:+.2f}BB/hr.'
        )
    elif n_tables < opt_n:
        verdict = (
            f'{n_tables} TABLES: Below optimal. Consider adding {opt_n - n_tables} more table(s). '
            f'Optimal: {opt_n} tables = {opt_bbph:+.2f}BB/hr vs current {est_bbph:+.2f}BB/hr.'
        )
    else:
        verdict = (
            f'{n_tables} TABLES: Possibly over-tabled. Optimal is {opt_n} tables. '
            f'Current: {est_bbph:+.2f}BB/hr. Optimal: {opt_bbph:+.2f}BB/hr. Consider reducing.'
        )

    tips = []

    if tier == 'mass_table':
        tips.append(
            f'MASS-TABLING ({n_tables} tables): Strategy is now nearly robotic. '
            f'VPIP target: {vpip_adj:.0f}%. '
            f'Bet/fold is your default post-flop. Complexity costs more than it earns.'
        )
    elif tier == 'nitty_tag':
        tips.append(
            f'NITTY-TAG MODE ({n_tables} tables): Reduce VPIP to {vpip_adj:.0f}%. '
            f'Avoid all bluffs. Value bet thinly only. Missed c-bets = check/fold.'
        )
    elif tier == 'solid_tag':
        tips.append(
            f'SOLID-TAG MODE ({n_tables} tables): VPIP target {vpip_adj:.0f}%. '
            f'Use semi-bluffs with equity but avoid pure air bluffs. '
            f'Keep lines simple: bet/fold or check/call.'
        )

    if n_tables > opt_n + 2:
        tips.append(
            f'OVER-TABLED: At {n_tables} tables you are likely leaving BB/hour on the table. '
            f'Reduce to {opt_n} tables for peak profitability. '
            f'Quality over quantity — fewer tables + better decisions = more profit.'
        )

    if current_bb100 < 2.0 and n_tables > 2:
        tips.append(
            f'LOW WR WARNING: Current WR={current_bb100:+.1f}BB/100 is marginal for multi-tabling. '
            f'Multi-tabling amplifies both profits AND losses. '
            f'Consider: is this due to multi-tabling degrading decisions?'
        )

    if not tips:
        tips.append(
            f'At {n_tables} tables ({tier}): VPIP target {vpip_adj:.0f}%. '
            f'Est WR: {est_wr:+.2f}BB/100, BB/hr: {est_bbph:+.2f}. {tier_desc}'
        )

    return MultitableAdvice(
        n_tables=n_tables,
        current_bb100=round(current_bb100, 2),
        vpip=round(vpip, 1),
        game_format=game_format,
        hands_per_hour_single=hands_per_hour_single,
        strategy_tier=tier,
        tier_description=tier_desc,
        estimated_wr_at_n=est_wr,
        estimated_hands_per_hour=est_hph,
        estimated_bb_per_hour=est_bbph,
        optimal_table_count=opt_n,
        optimal_bb_per_hour=opt_bbph,
        adjusted_vpip_target=round(vpip_adj, 1),
        do_list=do_list,
        dont_list=dont_list,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def mt_one_liner(r: MultitableAdvice) -> str:
    return (
        f'[MT {r.n_tables}tables|{r.strategy_tier}] '
        f'WR={r.estimated_wr_at_n:+.2f}BB/100 BB/hr={r.estimated_bb_per_hour:+.2f} | '
        f'optimal={r.optimal_table_count}tbl({r.optimal_bb_per_hour:+.2f}BB/hr) | '
        f'vpip_adj={r.adjusted_vpip_target:.0f}%'
    )
