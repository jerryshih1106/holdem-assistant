"""
Geometric Bet Sizing Guide (geometric_bet_sizing_guide.py)

Geometric sizing = choosing bet sizes across multiple streets so that the
remaining effective stack becomes fully committed by the target street.
Used when you want to build the pot to a natural all-in on the river.

THEORY:
  GEOMETRIC SIZING FORMULA:
  If pot = P and stack = S, with N streets remaining:
  Each street bet fraction G satisfies: (1 + G)^N = (P + S) / P
  => G = ((P + S) / P)^(1/N) - 1
  => Bet = G * current_pot on each street.
  After N streets of betting G * pot each time, all chips are in.

  EXAMPLE (SPR=4, 3 streets):
  Pot=100, Stack=400, SPR=4.
  G = (500/100)^(1/3) - 1 = 5^(1/3) - 1 = 1.710 - 1 = 0.710
  Flop: bet 71% pot (71BB). Pot becomes 242BB. Stack = 329BB.
  Turn: bet 71% pot (172BB). Pot becomes 586BB. Stack = 157BB.
  River: bet 71% pot (416BB). Stack committed = 0. All-in.

  WHY GEOMETRIC SIZING?
  - Prevents "sizing mistakes": too small early -> awkward overbet later
  - Forces commitment at a predictable rate
  - Villain cannot dodge future bets by folding after a small flop bet
  - Creates maximum pressure with minimum information leakage

  GEOMETRIC vs POLARIZED SIZING:
  Geometric: smooth escalation; suited for value hands (set, two pair)
  Polarized: small early + large river; suited for bluffs (last street has max fold equity)
  Half-pot * 3 streets approximates geometric (0.5*1.5*1.5 = 1.125 pots, committed)

  ADJUSTMENTS:
  - Scare card hits: can overbet geometric to maintain pressure
  - Villain seems to be folding: deviate down (small turn probe instead of full geometric)
  - Villain seems to be calling: deviate up (overbet shove remaining streets)

DISTINCT FROM:
  pot_geometry_calculator.py: Pot geometry calculations
  pot_geometry_planner.py:    Multi-street pot planning
  bet_sizing.py:              General sizing
  leverage_pressure_guide.py: Leverage effect
  THIS MODULE:                GEOMETRIC FORMULA specifically; computing G factor;
                              per-street sizing breakdown; commitment timeline.
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple


STREETS_ORDER: list = ['flop', 'turn', 'river']

SPR_TO_GEOMETRIC_FACTOR: dict = {
    1.0: 0.260,
    2.0: 0.442,
    3.0: 0.587,
    4.0: 0.710,
    6.0: 0.913,
    8.0: 1.080,
    12.0: 1.351,
    20.0: 1.759,
}

GEOMETRIC_DEVIATION_REASONS: dict = {
    'scare_card':        'Overbet current street by 1.3x geometric factor',
    'villain_folding':   'Reduce to 50% of geometric; maintain pressure but save chips',
    'villain_calling':   'Push to 1.5x geometric or jam remaining streets',
    'draw_heavy_board':  'Use geometric; sizing naturally charges draws',
    'dry_board':         'Geometric works well; no draws to charge',
}


def _geometric_factor(pot: float, stack: float, streets_remaining: int) -> float:
    if stack <= 0 or streets_remaining <= 0:
        return 1.0
    ratio = (pot + stack) / pot
    G = ratio ** (1.0 / streets_remaining) - 1.0
    return round(min(2.0, max(0.10, G)), 3)


def _build_street_plan(
    pot: float,
    stack: float,
    start_street: str,
) -> List[Tuple[str, float, float, float]]:
    idx = STREETS_ORDER.index(start_street) if start_street in STREETS_ORDER else 0
    streets = STREETS_ORDER[idx:]
    n = len(streets)
    G = _geometric_factor(pot, stack, n)

    plan = []
    cur_pot = pot
    cur_stack = stack

    for street in streets:
        bet = round(G * cur_pot, 1)
        bet = min(bet, cur_stack)
        new_pot = cur_pot + 2 * bet
        new_stack = cur_stack - bet
        plan.append((street, round(G, 3), round(bet, 1), round(new_pot, 1)))
        cur_pot = new_pot
        cur_stack = new_stack
        if cur_stack <= 0:
            break

    return plan


def _commitment_street(plan: List[Tuple]) -> str:
    for street, _, bet, new_pot in plan:
        pass
    return street


def _spr_lookup(spr: float) -> float:
    keys = sorted(SPR_TO_GEOMETRIC_FACTOR.keys())
    for k in keys:
        if spr <= k:
            return SPR_TO_GEOMETRIC_FACTOR[k]
    return SPR_TO_GEOMETRIC_FACTOR[max(keys)]


@dataclass
class GeometricBetSizingResult:
    pot_bb: float
    stack_bb: float
    spr: float
    start_street: str

    geometric_factor: float
    street_plan: List[Tuple[str, float, float, float]]
    commitment_street: str
    approx_factor_from_spr: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_geometric_bet_sizing(
    pot_bb: float = 20.0,
    stack_bb: float = 80.0,
    start_street: str = 'flop',
) -> GeometricBetSizingResult:
    """
    Calculate geometric bet sizing plan to commit stack by the river.

    Args:
        pot_bb:       Current pot in BB
        stack_bb:     Effective stack remaining in BB
        start_street: Street to start geometric plan ('flop','turn','river')

    Returns:
        GeometricBetSizingResult
    """
    spr = round(stack_bb / pot_bb, 2) if pot_bb > 0 else 0.0
    idx = STREETS_ORDER.index(start_street) if start_street in STREETS_ORDER else 0
    n_streets = len(STREETS_ORDER) - idx
    G = _geometric_factor(pot_bb, stack_bb, n_streets)
    plan = _build_street_plan(pot_bb, stack_bb, start_street)
    commit_street = _commitment_street(plan)
    approx_G = _spr_lookup(spr)

    plan_str_parts = []
    for street, g, bet, new_pot in plan:
        plan_str_parts.append(f'{street}:{bet:.0f}BB({g:.0%}pot)')
    plan_str = ' -> '.join(plan_str_parts)

    verdict = (
        f'[GEO pot={pot_bb:.0f}BB|stack={stack_bb:.0f}BB|spr={spr:.1f}] '
        f'G={G:.3f} ({G:.0%}pot/street) commit={commit_street} '
        f'plan=[{plan_str}]'
    )

    reasoning = (
        f'Geometric sizing: pot={pot_bb:.0f}BB, stack={stack_bb:.0f}BB (SPR={spr:.1f}). '
        f'Starting from {start_street} with {n_streets} streets. '
        f'Geometric factor G={G:.3f} ({G:.0%} of current pot each street). '
        f'Stack commits by: {commit_street}. '
        f'Street plan: {plan_str}.'
    )

    tips = []

    tips.append(
        f'GEOMETRIC FACTOR: G={G:.3f} ({G:.0%} of pot) each street from {start_street}. '
        f'SPR={spr:.1f}; stack commits by {commit_street}. '
        f'{"High SPR: geometric factor is small -- small % each street." if spr >= 8 else "Medium SPR: moderate bet each street." if spr >= 3 else "Low SPR: geometric factor large -- commit quickly."}'
    )

    tips.append(
        f'STREET PLAN (geometric): {plan_str}. '
        f'Each street bet is {G:.0%} of CURRENT pot (pot grows after each bet). '
        f'Villain must call correct pot odds at each street to realize equity.'
    )

    if n_streets >= 3:
        tips.append(
            f'3-STREET GEOMETRIC: Flop -> Turn -> River all committed. '
            f'Key insight: small flop bet ({plan[0][2]:.0f}BB) implies {plan[-1][2]:.0f}BB river bet. '
            f'Villain must consider TOTAL commitment when deciding to call flop.'
        )

    if spr >= 8:
        tips.append(
            f'DEEP STACK (SPR={spr:.1f}): Geometric factor {G:.0%} per street is large. '
            f'Deep stacks need a large pot % each street to get all chips in. '
            f'Alternative: bet smaller early and escalate -- {G*0.7:.0%} flop, {G:.0%} turn, overbet river.'
        )
    elif spr <= 2:
        tips.append(
            f'LOW SPR (SPR={spr:.1f}): Geometric factor {G:.0%} is small -- stack is already close to pot. '
            f'Consider shoving directly (SPR too low for multi-street plan). '
            f'If staying geometric: {plan[0][2]:.0f}BB commits {plan[0][2]/stack_bb:.0%} of stack on {start_street} alone.'
        )

    return GeometricBetSizingResult(
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        spr=spr,
        start_street=start_street,
        geometric_factor=G,
        street_plan=plan,
        commitment_street=commit_street,
        approx_factor_from_spr=approx_G,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def geo_one_liner(r: GeometricBetSizingResult) -> str:
    return (
        f'[GEO pot={r.pot_bb:.0f}BB|spr={r.spr:.1f}] '
        f'G={r.geometric_factor:.3f}({r.geometric_factor:.0%}/street) commit={r.commitment_street}'
    )
