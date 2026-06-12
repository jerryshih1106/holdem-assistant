"""
Geometric Bet Planner (geo_bet_planner.py)

One of the most important but underused live poker skills: planning bet sizes
across streets to efficiently build the pot and commit stacks by the river.

If you want to get stacks in by the river, you must bet the right fraction of
pot on each earlier street. Too small on flop/turn = undershoot, forced to
overbet river. Too large = blow up the pot before everyone has a chance to call.

The geometric formula:
  Bet x * pot each street. After each bet, pot grows by factor (1+2x).
  Over n streets: total_committed = x*P * [1 + (1+2x) + (1+2x)^2 + ...]

Examples:
  Pot=20BB, stack=80BB (SPR=4), starting on flop (3 streets):
    33%/street: flop=6.6, turn=8.7, river=11.5 → total committed 26.8BB
    50%/street: flop=10, turn=15, river=22.5   → total committed 47.5BB
    65%/street: flop=13, turn=21, river=34     → total committed 68BB (~stacks)
    PSB/street: flop=20, turn=60, river=allin  → committed 80BB (allin by river)

Key insight: SPR 4 requires ~65%/street to get stacks in over 3 streets.
SPR 2 requires ~50%/street. SPR 1 requires ~33%/street or PSB on one street.

Common SPR → approximate geometric factor:
  SPR 1:  ~0.33 per street (3 streets) or shove immediately
  SPR 2:  ~0.50 per street
  SPR 3:  ~0.60 per street
  SPR 4:  ~0.65 per street
  SPR 6:  ~0.75 per street or larger (need a big flop bet)
  SPR 8+: likely need overbets or multiple streets of PSBs

Usage:
    from poker.geo_bet_planner import plan_geo_bets, GeoBetPlan, geo_plan_one_liner
    plan = plan_geo_bets(
        start_pot_bb=20.0,
        hero_stack_bb=80.0,
        start_street='flop',
    )
    print(plan.geo_factor, plan.flop_bet_bb, plan.turn_bet_bb, plan.river_bet_bb)
    print(geo_plan_one_liner(plan))
"""

from dataclasses import dataclass, field
from typing import List


def _n_streets(start_street: str) -> int:
    return {'flop': 3, 'turn': 2, 'river': 1}.get(start_street, 3)


def _simulate_plan(start_pot: float, stack: float, x: float, n_streets: int):
    """
    Simulate betting x*pot each street for n_streets.
    Returns (pots_before, bets, total_committed, final_remaining).
    Caps each bet at remaining stack.
    """
    pot = start_pot
    remaining = stack
    pots_before = []
    bets = []
    total_invested = 0.0

    for _ in range(n_streets):
        ideal_bet = x * pot
        bet = min(ideal_bet, remaining)
        pots_before.append(round(pot, 2))
        bets.append(round(bet, 2))
        total_invested += bet
        remaining -= bet
        pot += 2 * bet
        if remaining <= 0.01:
            break

    return pots_before, bets, round(total_invested, 2), round(max(0.0, remaining), 2)


def _find_geo_factor(start_pot: float, stack: float, n_streets: int) -> float:
    """Binary search for geometric factor x that commits hero's full stack."""
    lo, hi = 0.05, 3.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        _, _, total, remaining = _simulate_plan(start_pot, stack, mid, n_streets)
        if remaining > 0.05:
            lo = mid   # need bigger bets
        else:
            hi = mid   # already got it in; try smaller
    return round((lo + hi) / 2.0, 3)


def _plan_preset(start_pot: float, stack: float, x: float, n_streets: int) -> float:
    """Total committed with a fixed x across n_streets."""
    _, _, total, _ = _simulate_plan(start_pot, stack, x, n_streets)
    return total


STREET_NAMES = ['flop', 'turn', 'river']


@dataclass
class GeoBetPlan:
    """Geometric bet plan to get stacks in over remaining streets."""
    start_pot_bb: float
    hero_stack_bb: float
    start_street: str
    n_streets: int
    spr: float

    # Geometric factor that commits the stack
    geo_factor: float

    # Per-street bet details (0.0 if that street is not in the plan)
    flop_pot_bb: float
    flop_bet_bb: float
    flop_bet_pct: float

    turn_pot_bb: float
    turn_bet_bb: float
    turn_bet_pct: float

    river_pot_bb: float
    river_bet_bb: float
    river_bet_pct: float

    # Summary
    total_committed_bb: float
    remaining_stack_bb: float
    river_is_allin: bool

    # Preset alternatives (total committed with fixed x)
    plan_33pct_total: float   # conservative
    plan_50pct_total: float   # standard
    plan_65pct_total: float   # aggressive
    plan_100pct_total: float  # PSB each street

    # Guidance
    recommended_approach: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def plan_geo_bets(
    start_pot_bb: float = 20.0,
    hero_stack_bb: float = 80.0,
    start_street: str = 'flop',
) -> GeoBetPlan:
    """
    Plan geometric bet sizes to efficiently commit hero's stack by the river.

    Args:
        start_pot_bb:   Current pot size in big blinds
        hero_stack_bb:  Hero's effective stack (remaining) in big blinds
        start_street:   Current street: 'flop', 'turn', or 'river'

    Returns:
        GeoBetPlan with per-street bet sizes and geometric factor
    """
    n = _n_streets(start_street)
    spr = round(hero_stack_bb / max(0.1, start_pot_bb), 2)
    x = _find_geo_factor(start_pot_bb, hero_stack_bb, n)

    pots_before, bets, total_committed, remaining = _simulate_plan(
        start_pot_bb, hero_stack_bb, x, n
    )

    start_idx = STREET_NAMES.index(start_street)
    street_labels = STREET_NAMES[start_idx:]

    def _get(lst, i, default=0.0):
        return lst[i] if i < len(lst) else default

    def _pct(bet, pot):
        return round(bet / pot, 3) if pot > 0.01 else 0.0

    # Map streets to flop/turn/river slots
    fl_idx = 0 if start_street == 'flop' else -1
    tu_idx = (0 if start_street == 'turn' else 1) if start_street in ('flop', 'turn') else -1
    rv_idx = 0 if start_street == 'river' else (1 if start_street == 'turn' else 2)

    flop_pot = _get(pots_before, fl_idx) if fl_idx >= 0 else 0.0
    flop_bet = _get(bets, fl_idx) if fl_idx >= 0 else 0.0
    turn_pot = _get(pots_before, tu_idx) if tu_idx >= 0 else 0.0
    turn_bet = _get(bets, tu_idx) if tu_idx >= 0 else 0.0
    river_pot = _get(pots_before, rv_idx) if rv_idx >= 0 else 0.0
    river_bet = _get(bets, rv_idx) if rv_idx >= 0 else 0.0

    river_is_allin = remaining <= 0.05

    # Presets
    p33 = round(_plan_preset(start_pot_bb, hero_stack_bb, 0.33, n), 1)
    p50 = round(_plan_preset(start_pot_bb, hero_stack_bb, 0.50, n), 1)
    p65 = round(_plan_preset(start_pot_bb, hero_stack_bb, 0.65, n), 1)
    p100 = round(_plan_preset(start_pot_bb, hero_stack_bb, 1.00, n), 1)

    # Approach label
    if x <= 0.40:
        approach = 'small_bets'
    elif x <= 0.60:
        approach = 'standard_sizing'
    elif x <= 0.85:
        approach = 'large_bets'
    elif x <= 1.10:
        approach = 'pot_sized'
    else:
        approach = 'overbet_required'

    # Reasoning
    if n == 1:
        reason = (
            f'River only. Bet {x:.0%} of pot ({river_bet:.1f}BB) '
            f'to commit remaining stack ({hero_stack_bb:.1f}BB).'
        )
    else:
        reason = (
            f'SPR={spr:.1f} over {n} streets starting {start_street}. '
            f'Bet {x:.0%} of pot each street: '
        )
        if flop_bet > 0:
            reason += f'flop {flop_bet:.1f}BB, '
        if turn_bet > 0:
            reason += f'turn {turn_bet:.1f}BB, '
        if river_bet > 0:
            reason += f'river {river_bet:.1f}BB'
        reason += f'. Total committed: {total_committed:.1f}BB.'

    # Tips
    tips = []
    if spr > 6:
        tips.append(
            f'SPR={spr:.1f} is very deep. Getting stacks in requires large bets '
            f'({x:.0%}/street). Consider whether hand is strong enough to commit '
            f'{hero_stack_bb:.0f}BB — SPR>6 requires two pair+.'
        )
    elif spr <= 1.5:
        tips.append(
            f'SPR={spr:.1f} is very shallow. Consider shoving immediately instead '
            f'of building pot across {n} streets. Simplifies decision for villain too.'
        )
    if n == 1 and x > 1.0:
        tips.append(
            f'River overbet ({x:.0%} pot) required to get stacks in. '
            f'River overbets are polarizing — only use with strong value or as bluff '
            f'with blockers. Consider whether villain will call an overbet.'
        )
    if n >= 2 and flop_bet > 0:
        tips.append(
            f'Flop bet ({flop_bet:.1f}BB into {start_pot_bb:.1f}BB pot) sets up '
            f'a natural turn and river commitment. Villain who calls flop is getting '
            f'pot odds implying they will call reasonable turn bets too.'
        )
    tips.append(
        f'Conservative plan (33%/street): commits {p33:.1f}BB. '
        f'Standard (50%): {p50:.1f}BB. '
        f'Aggressive (65%): {p65:.1f}BB. '
        f'PSB each: {p100:.1f}BB (or all-in).'
    )

    return GeoBetPlan(
        start_pot_bb=round(start_pot_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        start_street=start_street,
        n_streets=n,
        spr=spr,
        geo_factor=x,
        flop_pot_bb=round(flop_pot, 1),
        flop_bet_bb=round(flop_bet, 1),
        flop_bet_pct=_pct(flop_bet, flop_pot),
        turn_pot_bb=round(turn_pot, 1),
        turn_bet_bb=round(turn_bet, 1),
        turn_bet_pct=_pct(turn_bet, turn_pot),
        river_pot_bb=round(river_pot, 1),
        river_bet_bb=round(river_bet, 1),
        river_bet_pct=_pct(river_bet, river_pot),
        total_committed_bb=round(total_committed, 1),
        remaining_stack_bb=round(remaining, 1),
        river_is_allin=river_is_allin,
        plan_33pct_total=p33,
        plan_50pct_total=p50,
        plan_65pct_total=p65,
        plan_100pct_total=p100,
        recommended_approach=approach,
        reasoning=reason,
        tips=tips,
    )


def geo_plan_one_liner(plan: GeoBetPlan) -> str:
    parts = []
    if plan.flop_bet_bb > 0:
        parts.append(f'F:{plan.flop_bet_bb:.0f}BB({plan.flop_bet_pct:.0%})')
    if plan.turn_bet_bb > 0:
        parts.append(f'T:{plan.turn_bet_bb:.0f}BB({plan.turn_bet_pct:.0%})')
    if plan.river_bet_bb > 0:
        suffix = 'AI' if plan.river_is_allin else f'{plan.river_bet_pct:.0%}'
        parts.append(f'R:{plan.river_bet_bb:.0f}BB({suffix})')
    bets_str = ' '.join(parts) if parts else 'no_bets'
    return (
        f'[GEO SPR={plan.spr:.1f}|{plan.start_street}] '
        f'x={plan.geo_factor:.0%} | {bets_str} | '
        f'total={plan.total_committed_bb:.0f}BB | '
        f'{"ALLIN" if plan.river_is_allin else "partial"}'
    )
