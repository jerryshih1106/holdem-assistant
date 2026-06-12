"""
Late Registration Tournament Advisor (late_reg_tournament_advisor.py)

Late registration in tournaments allows players to join after the start.
This creates a strategic decision: register early (play all streets) or
late (skip early blind levels, start with higher M-ratio pressure).

KEY TRADEOFFS:
  Early registration:
    + Play more hands, accumulate chips early
    + Skip the "ramp up" period where M is highest
    - Risk early bust on bad spots
    - Time investment in early low-stakes levels
    - Variance of early blind levels

  Late registration:
    + Skip early variance (bust risk when chips have little value)
    + Start with an effective M-ratio immediately
    + Save time if skill edge is low in early levels
    - Miss chip accumulation opportunities
    - May start with below-average stack (if others have accumulated)
    - Some blind levels are better than others to start at

OPTIMAL LATE REG TIMING:
  Register when: starting_stack_bb gives M-ratio in "yellow" zone (M=10-20)
  or when the blind level is where post-flop skill differentiates players.

  NEVER register at: M < 6 (already in push/fold mode before you start)
  GOOD to register: M = 15-25 (green/yellow zone, normal poker still)

Usage:
    from poker.late_reg_tournament_advisor import advise_late_reg, LateRegAdvice, latreg_one_liner

    advice = advise_late_reg(
        starting_chips=10000,
        current_bb=200,
        current_ante=25,
        n_players_table=9,
        avg_stack=12000,
        total_registered=300,
        blind_level=8,
        estimated_ev_per_level=0.02,
    )
    print(latreg_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List


def _calc_m_ratio(chips: float, bb: float, sb: float, ante: float, n: int) -> float:
    orbit = bb + sb + ante * n
    if orbit <= 0:
        return 999.0
    return round(chips / orbit, 1)


def _m_zone(m: float) -> str:
    if m > 20:  return 'green'
    if m > 10:  return 'yellow'
    if m > 6:   return 'orange'
    if m > 1:   return 'red'
    return 'dead'


def _reg_recommendation(m: float, avg_stack_ratio: float) -> str:
    """Should hero register now?"""
    if m < 6:
        return 'do_not_reg'      # already in push/fold when you sit down
    if m < 10:
        return 'questionable'    # tight push/fold start
    if avg_stack_ratio < 0.50:
        return 'late_disadvantage'  # starting well below average
    if m >= 12 and avg_stack_ratio >= 0.70:
        return 'register_now'    # good M and reasonable stack relative to avg
    if m >= 8:
        return 'marginal'
    return 'questionable'


_REC_DESC = {
    'register_now':       'Good timing to late register. M-ratio is healthy and stack is competitive.',
    'marginal':           'Marginal timing. M-ratio is acceptable but avg stack gap may hurt.',
    'questionable':       'Late registration is questionable. M-ratio will be tight on arrival.',
    'do_not_reg':         'Do NOT register. You would start in push/fold mode immediately.',
    'late_disadvantage':  'Late registration at a disadvantage. Starting stack is well below average.',
}

_SKILL_ADJUSTMENT = {
    # How much skill edge changes the late reg recommendation
    'large_edge':    +2,    # Pro player: late reg is fine, skill overcomes
    'moderate_edge': +1,
    'small_edge':    0,
    'breakeven':     -1,
    'losing':        -2,    # Losing player should reg early (more hands = no edge)
}


@dataclass
class LateRegAdvice:
    # Inputs
    starting_chips: float
    current_bb: float
    current_ante: float
    n_players_table: int
    avg_stack: float
    total_registered: int
    blind_level: int
    estimated_ev_per_level: float   # hero's edge in BB per orbit at this level

    # Calculations
    m_ratio_on_reg: float
    m_zone: str
    avg_stack_ratio: float          # starting_chips / avg_stack
    chips_behind_avg: float

    # Decision
    recommendation: str             # 'register_now', 'marginal', 'do_not_reg', etc.
    recommendation_desc: str
    latest_recommended_level: int   # latest blind level to still register
    ideal_reg_level: int            # ideal level to register

    # EV estimates
    ev_saved_by_skipping: float     # chips saved by skipping early levels (approx)
    ev_lost_by_skipping: float      # chip accumulation missed

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_late_reg(
    starting_chips: float = 10000.0,
    current_bb: float = 200.0,
    current_ante: float = 25.0,
    n_players_table: int = 9,
    avg_stack: float = 12000.0,
    total_registered: int = 300,
    blind_level: int = 8,
    estimated_ev_per_level: float = 0.02,
    big_blind_at_level1: float = 50.0,
) -> LateRegAdvice:
    """
    Advise on whether and when to late-register a tournament.

    Args:
        starting_chips:       Stack you receive when registering
        current_bb:           Current big blind at this level
        current_ante:         Current ante per player
        n_players_table:      Players per table
        avg_stack:            Current average stack in chips
        total_registered:     Total players registered so far
        blind_level:          Current blind level (1 = start)
        estimated_ev_per_level: Hero's estimated edge in fraction of stack per level
        big_blind_at_level1:  BB at level 1 (for skip EV calculation)

    Returns:
        LateRegAdvice
    """
    sb = current_bb * 0.5
    m = _calc_m_ratio(starting_chips, current_bb, sb, current_ante, n_players_table)
    zone = _m_zone(m)
    avg_ratio = round(starting_chips / max(avg_stack, 1.0), 3)
    chips_behind = round(avg_stack - starting_chips, 0)

    rec = _reg_recommendation(m, avg_ratio)
    rec_desc = _REC_DESC[rec]

    # Latest recommended level to reg: where M would still be >= 10
    # Estimate: as blinds double each level, find the level where M drops below 10
    # Simplified: M = starting_chips / orbit_cost. Find BB where M=10.
    orbit_at_m10 = starting_chips / 10.0
    # orbit = bb + sb + ante*n = 1.5*bb + ante*n
    # bb at M=10 = orbit_at_m10 / (1.5 + ante_ratio * n)
    ante_ratio = current_ante / max(current_bb, 1.0)
    bb_at_m10 = orbit_at_m10 / (1.5 + ante_ratio * n_players_table)
    # Estimate level from BB using doubling structure
    if bb_at_m10 > current_bb and big_blind_at_level1 > 0:
        import math
        levels_ahead = max(0, int(math.log(bb_at_m10 / max(current_bb, 1.0)) / math.log(1.5)))
        latest_level = blind_level + levels_ahead
    else:
        latest_level = blind_level

    # Ideal level: where M would be ~15-20
    bb_at_m17 = starting_chips / (17 * (1.5 + ante_ratio * n_players_table))
    if bb_at_m17 > big_blind_at_level1 and big_blind_at_level1 > 0:
        import math
        levels_back = max(0, int(math.log(bb_at_m17 / max(big_blind_at_level1, 1.0)) / math.log(1.5)))
        ideal_level = max(1, levels_back)
    else:
        ideal_level = max(1, blind_level - 2)

    # EV saved by skipping early levels (variance avoidance)
    # Rough: each early level, expected bust risk is small but meaningful
    ev_saved = round(starting_chips * 0.005 * (blind_level - 1), 0)  # approx

    # EV lost from chip accumulation in early levels
    ev_lost = round(estimated_ev_per_level * starting_chips * (blind_level - 1), 0)

    reasoning = (
        f'Late reg at level {blind_level}: starting_chips={starting_chips:.0f} '
        f'M={m:.1f} ({zone}) vs avg={avg_stack:.0f} ({avg_ratio:.2f}x avg). '
        f'Recommendation: {rec}. Latest reg level: {latest_level}.'
    )

    verdict = (
        f'[LATE REG Level {blind_level}|M={m:.1f}|{zone.upper()}] {rec.upper()}: '
        f'{rec_desc} Stack {avg_ratio:.2f}x avg.'
    )

    tips = []

    if rec == 'do_not_reg':
        tips.append(
            f'DO NOT REG: M={m:.1f} means you start in push/fold mode immediately. '
            f'You would have only {m:.0f} orbits before busting. '
            f'Late reg cutoff should have been ~{latest_level - 1} levels ago.'
        )
    elif rec == 'register_now':
        tips.append(
            f'GOOD TIMING: M={m:.1f} ({zone} zone) gives you room to play normal poker. '
            f'You start at {avg_ratio:.0%} of average. '
            f'Ideal registration was around level {ideal_level} for M~17.'
        )
    elif rec == 'late_disadvantage':
        tips.append(
            f'STACK DISADVANTAGE: You start with {chips_behind:,.0f} chips less than average. '
            f'This is a significant disadvantage. '
            f'You will need to chip up quickly. Consider early aggression from LP.'
        )

    tips.append(
        f'LATE REG RULE: Ideal late reg timing is when M >= 15 and stack >= 70% of avg. '
        f'Current: M={m:.1f}, stack={avg_ratio:.0%} of avg. '
        f'Latest acceptable reg: level {latest_level} (M will be ~10).'
    )

    if estimated_ev_per_level > 0.03:
        tips.append(
            f'SKILL EDGE ({estimated_ev_per_level:.1%}/level): With this edge, '
            f'late reg costs you {ev_lost:,.0f} chips in skipped EV. '
            f'Strong skill advantage makes earlier registration more valuable.'
        )

    return LateRegAdvice(
        starting_chips=starting_chips,
        current_bb=current_bb,
        current_ante=current_ante,
        n_players_table=n_players_table,
        avg_stack=avg_stack,
        total_registered=total_registered,
        blind_level=blind_level,
        estimated_ev_per_level=estimated_ev_per_level,
        m_ratio_on_reg=m,
        m_zone=zone,
        avg_stack_ratio=avg_ratio,
        chips_behind_avg=chips_behind,
        recommendation=rec,
        recommendation_desc=rec_desc,
        latest_recommended_level=latest_level,
        ideal_reg_level=ideal_level,
        ev_saved_by_skipping=ev_saved,
        ev_lost_by_skipping=ev_lost,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def latreg_one_liner(r: LateRegAdvice) -> str:
    return (
        f'[LATREG Level{r.blind_level}|M={r.m_ratio_on_reg:.1f}|{r.m_zone}] '
        f'{r.recommendation.upper()} | '
        f'stack={r.avg_stack_ratio:.2f}x_avg latest_ok=L{r.latest_recommended_level}'
    )
