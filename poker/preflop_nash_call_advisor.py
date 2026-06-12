"""
Preflop Nash Call Advisor (preflop_nash_call_advisor.py)

Answers: "Villain just shoved. Should I call?"

Unlike pushfold.py (which gives push ranges) and jam_caller.py (which estimates
villain's range), this module computes the CALLING threshold using Nash equilibrium
principles — the minimum equity required to profitably call a shove.

KEY FORMULAS:
  Required equity (chip) = call_cost / (pot + call_cost)
  Required equity (ICM) = chip_req + ICM_premium (up to +8% near bubble)

  EV(call) = equity * total_pot - call_cost
  EV(fold) = 0

NASH CALLING RANGE CONSTRUCTION:
  Against Nash push ranges, the Nash CALL range is tighter than pure pot odds:
  - BTN shoves  8BB: call with TT+, AQs+, AKo (top ~15% hands)
  - BTN shoves 15BB: call with JJ+, AKs (top ~8% hands)
  - BTN shoves 25BB: call with QQ+, AKs (top ~5% hands)
  These tighten with ICM pressure (more players, near bubble).

  Villain push range estimate:
  - 5BB: ~70% of hands from BTN/SB
  - 10BB: ~45% BTN / 35% CO / 20% EP
  - 15BB: ~30% BTN / 20% CO / 12% EP
  - 20BB: ~20% BTN / 12% CO / 7% EP
  - 25BB: ~12% BTN / 7% CO / 4% EP

DISTINCTION FROM OTHER MODULES:
  pushfold.py:          Which hands to PUSH (Nash push frequency)
  jam_caller.py:        Should hero call a jam (estimation-based)
  preflop_allin_ev.py:  EV of calling/folding (range estimation model)
  THIS MODULE:          Nash equilibrium CALL thresholds + call range construction

Usage:
    from poker.preflop_nash_call_advisor import advise_nash_call, NashCallAdvice, nc_one_liner

    result = advise_nash_call(
        hero_stack_bb=30.0,
        villain_shove_bb=18.0,
        villain_position='BTN',
        hero_position='BB',
        hero_hand_rank_pct=0.87,    # AQs
        n_players=6,
        is_tournament=True,
        icm_pressure=0.30,
    )
    print(nc_one_liner(result))
"""

import math
from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# Villain push range by stack + position
# --------------------------------------------------------------------------

# Nash push range width (fraction of hands) by stack BB and position
_PUSH_RANGE_MATRIX = {
    # {stack: {position: pct}}
    5:  {'BTN': 0.75, 'SB': 0.70, 'CO': 0.65, 'HJ': 0.55, 'MP': 0.45, 'UTG': 0.40, 'BB': 0.80},
    8:  {'BTN': 0.60, 'SB': 0.55, 'CO': 0.45, 'HJ': 0.35, 'MP': 0.28, 'UTG': 0.20, 'BB': 0.65},
    10: {'BTN': 0.48, 'SB': 0.42, 'CO': 0.35, 'HJ': 0.25, 'MP': 0.18, 'UTG': 0.14, 'BB': 0.55},
    12: {'BTN': 0.40, 'SB': 0.35, 'CO': 0.28, 'HJ': 0.20, 'MP': 0.14, 'UTG': 0.10, 'BB': 0.45},
    15: {'BTN': 0.30, 'SB': 0.27, 'CO': 0.20, 'HJ': 0.14, 'MP': 0.10, 'UTG': 0.07, 'BB': 0.35},
    20: {'BTN': 0.20, 'SB': 0.17, 'CO': 0.13, 'HJ': 0.08, 'MP': 0.06, 'UTG': 0.04, 'BB': 0.25},
    25: {'BTN': 0.12, 'SB': 0.10, 'CO': 0.08, 'HJ': 0.05, 'MP': 0.04, 'UTG': 0.03, 'BB': 0.18},
    30: {'BTN': 0.08, 'SB': 0.07, 'CO': 0.05, 'HJ': 0.03, 'MP': 0.02, 'UTG': 0.02, 'BB': 0.12},
}

def _interp_push_range(stack_bb: float, position: str) -> float:
    """Interpolate villain's Nash push range for any stack depth."""
    pos = position.upper()
    sorted_keys = sorted(_PUSH_RANGE_MATRIX.keys())

    if stack_bb <= sorted_keys[0]:
        return _PUSH_RANGE_MATRIX[sorted_keys[0]].get(pos, 0.50)
    if stack_bb >= sorted_keys[-1]:
        return _PUSH_RANGE_MATRIX[sorted_keys[-1]].get(pos, 0.05)

    for i in range(len(sorted_keys) - 1):
        lo, hi = sorted_keys[i], sorted_keys[i + 1]
        if lo <= stack_bb <= hi:
            t = (stack_bb - lo) / (hi - lo)
            lo_pct = _PUSH_RANGE_MATRIX[lo].get(pos, 0.20)
            hi_pct = _PUSH_RANGE_MATRIX[hi].get(pos, 0.10)
            return round(lo_pct + t * (hi_pct - lo_pct), 3)

    return 0.15


def _hero_equity_vs_push_range(
    hero_rank_pct: float,
    villain_push_range_pct: float,
) -> float:
    """
    Hero's equity vs villain's push range.
    Wider push range = villain has more trash = hero has better equity.
    """
    # Base equity model
    base_eq = 0.32 + hero_rank_pct * 0.38

    # Wider range = more dominated hands in villain's range = hero wins more often
    range_bonus = (villain_push_range_pct - 0.20) * 0.25
    adj = base_eq + range_bonus

    # Hand-specific overrides
    if hero_rank_pct >= 0.98:    # AA
        adj = 0.82 + villain_push_range_pct * 0.05
    elif hero_rank_pct >= 0.96:   # KK
        adj = 0.74 + villain_push_range_pct * 0.04
    elif hero_rank_pct >= 0.93:   # QQ
        adj = 0.65 + villain_push_range_pct * 0.05
    elif hero_rank_pct >= 0.90:   # JJ
        adj = 0.58 + villain_push_range_pct * 0.05
    elif hero_rank_pct >= 0.87:   # TT/AQs
        adj = 0.53 + villain_push_range_pct * 0.05
    elif hero_rank_pct >= 0.83:   # 99/AJs
        adj = 0.50 + villain_push_range_pct * 0.05

    return round(min(0.90, max(0.20, adj)), 3)


def _required_equity_chip(call_cost: float, pot_before_call: float) -> float:
    """Chip EV breakeven equity."""
    total = pot_before_call + call_cost
    return round(call_cost / total, 3)


def _required_equity_icm(
    chip_req: float,
    n_players: int,
    icm_pressure: float,
    is_tournament: bool,
    hero_stack_bb: float,
) -> float:
    """ICM-adjusted required equity (always >= chip_req)."""
    if not is_tournament:
        return chip_req

    # Base ICM premium
    base_premium = icm_pressure * 0.06

    # More players = tighter calling (more bubbles to pass)
    player_premium = max(0, (n_players - 2)) * 0.008

    # Deep stacks: can afford to fold marginal spots
    if hero_stack_bb >= 30:
        depth_adj = 0.02
    elif hero_stack_bb >= 15:
        depth_adj = 0.01
    else:
        depth_adj = -0.01  # short stack: approach Nash (less ICM caution)

    total = chip_req + base_premium + player_premium + depth_adj
    return round(min(0.68, max(chip_req, total)), 3)


def _nash_call_range_description(
    stack_bb: float,
    position: str,
    n_players: int,
    icm_pressure: float,
) -> str:
    """Human-readable Nash call range for this spot."""
    pos = position.upper()
    pct_push = _interp_push_range(stack_bb, pos)

    if stack_bb <= 8:
        base = 'TT+, AJs+, AKo (any two profitable above equity threshold)'
    elif stack_bb <= 12:
        base = 'JJ+, AQs+, AKo'
    elif stack_bb <= 17:
        base = 'QQ+, AKs, AKo; JJ marginal'
    elif stack_bb <= 22:
        base = 'QQ+, AKs; JJ/AKo marginal'
    else:
        base = 'KK+, AKs; QQ/AKo marginal'

    if icm_pressure >= 0.50:
        base += ' [TIGHTEN: high ICM pressure — fold marginal spots]'
    elif icm_pressure <= 0.10:
        base += ' [STANDARD: low ICM pressure — near chip EV]'

    if n_players >= 7:
        base += ' [MULTI: many players — tighten 3-5%]'

    return base


@dataclass
class NashCallAdvice:
    # Inputs
    hero_stack_bb: float
    villain_shove_bb: float
    villain_position: str
    hero_position: str
    hero_hand_rank_pct: float
    n_players: int
    is_tournament: bool
    icm_pressure: float

    # Range analysis
    villain_push_range_pct: float   # estimated % of hands villain pushes with
    hero_equity: float              # hero's equity vs villain's push range

    # Equity thresholds
    required_equity_chip: float     # chip EV breakeven
    required_equity_icm: float      # ICM-adjusted (always >= chip req)
    equity_margin: float            # hero_equity - required_equity_icm

    # EV
    call_cost_bb: float
    pot_total_bb: float
    ev_call: float
    ev_fold: float

    # Decision
    decision: str       # 'call' / 'fold' / 'marginal_call' / 'marginal_fold'
    confidence: str
    nash_call_range: str    # which hands to call with

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_nash_call(
    hero_stack_bb: float = 30.0,
    villain_shove_bb: float = 18.0,
    villain_position: str = 'BTN',
    hero_position: str = 'BB',
    hero_hand_rank_pct: float = 0.87,
    n_players: int = 6,
    is_tournament: bool = True,
    icm_pressure: float = 0.20,
) -> NashCallAdvice:
    """
    Calculate Nash-equilibrium call advice vs a preflop shove.

    Args:
        hero_stack_bb:       Hero's effective stack in BB
        villain_shove_bb:    Villain's shove amount in BB
        villain_position:    Villain's position
        hero_position:       Hero's position (usually BB for single-raised pots)
        hero_hand_rank_pct:  Hero hand strength 0-1
        n_players:           Total players at table
        is_tournament:       True = ICM applies
        icm_pressure:        0=none, 1=extreme bubble

    Returns:
        NashCallAdvice
    """
    # Hero's investment before call
    if hero_position.upper() == 'BB':
        hero_prior_bb = 1.0
    elif hero_position.upper() == 'SB':
        hero_prior_bb = 0.5
    else:
        hero_prior_bb = 0.0

    call_cost = max(0.0, villain_shove_bb - hero_prior_bb)
    pot_total = villain_shove_bb + hero_prior_bb + 0.5  # SB+BB+villain's shove approx

    villain_range = _interp_push_range(villain_shove_bb, villain_position)
    hero_eq = _hero_equity_vs_push_range(hero_hand_rank_pct, villain_range)

    req_chip = _required_equity_chip(call_cost, pot_total - call_cost)
    req_icm = _required_equity_icm(req_chip, n_players, icm_pressure, is_tournament, hero_stack_bb)
    eq_margin = round(hero_eq - req_icm, 3)

    ev_c = round(hero_eq * pot_total - call_cost, 2)
    ev_f = 0.0

    # Decision
    margin_hi = 0.05
    margin_lo = -0.05

    if eq_margin >= margin_hi:
        decision = 'call'
        conf = 'high'
    elif eq_margin >= 0.02:
        decision = 'call'
        conf = 'medium'
    elif eq_margin >= margin_lo:
        decision = 'marginal_call' if eq_margin >= 0 else 'marginal_fold'
        conf = 'low'
    else:
        decision = 'fold'
        conf = 'high' if eq_margin <= -0.10 else 'medium'

    nash_range = _nash_call_range_description(
        villain_shove_bb, villain_position, n_players, icm_pressure
    )

    reasoning = (
        f'Hero {hero_position.upper()} vs {villain_position.upper()} shove {villain_shove_bb:.0f}BB. '
        f'Villain push range: {villain_range:.0%} ({villain_shove_bb:.0f}BB {villain_position.upper()}). '
        f'Hero equity={hero_eq:.0%} vs range. '
        f'Required (chip)={req_chip:.0%} (ICM)={req_icm:.0%}. '
        f'Margin={eq_margin:+.0%}. '
        f'EV(call)={ev_c:+.2f}BB. Decision: {decision}.'
    )

    verdict = (
        f'[NC {hero_position.upper()}vs{villain_position.upper()}@{villain_shove_bb:.0f}BB] '
        f'{decision.upper()} ({conf}) | '
        f'eq={hero_eq:.0%} req={req_icm:.0%} margin={eq_margin:+.0%} | '
        f'ev={ev_c:+.2f}BB'
    )

    tips = []

    if decision in ('call', 'marginal_call'):
        tips.append(
            f'{"CALL" if decision == "call" else "MARGINAL CALL"}: '
            f'Hero equity {hero_eq:.0%} vs villain {villain_position.upper()} push range ({villain_range:.0%} hands). '
            f'{"Comfortably" if eq_margin >= 0.05 else "Marginally"} above '
            f'ICM-adjusted threshold ({req_icm:.0%}). EV={ev_c:+.2f}BB.'
        )
    else:
        tips.append(
            f'{"FOLD" if decision == "fold" else "MARGINAL FOLD"}: '
            f'Hero equity {hero_eq:.0%} below ICM threshold ({req_icm:.0%}). '
            f'Villain {villain_position.upper()} {villain_shove_bb:.0f}BB shove range is '
            f'{"tight" if villain_range <= 0.15 else "standard" if villain_range <= 0.30 else "wide"} ({villain_range:.0%}).'
        )

    tips.append(
        f'NASH CALL RANGE: Against {villain_position.upper()} {villain_shove_bb:.0f}BB push → {nash_range}'
    )

    if is_tournament and icm_pressure >= 0.30:
        icm_premium = round(req_icm - req_chip, 3)
        tips.append(
            f'ICM IMPACT: Tournament ICM pressure ({icm_pressure:.0%}) adds {icm_premium:+.0%} to required equity. '
            f'Chip breakeven = {req_chip:.0%}, ICM breakeven = {req_icm:.0%}. '
            f'Fold marginal calls (equity between {req_chip:.0%}-{req_icm:.0%}) unless desperate.'
        )

    if villain_range <= 0.10:
        tips.append(
            f'TIGHT SHOVE WARNING: Villain only shoves {villain_range:.0%} of hands from {villain_position.upper()} '
            f'at {villain_shove_bb:.0f}BB. This range is premium-heavy (KK+/AKs). '
            f'Need QQ+ or AKs to call profitably.'
        )

    return NashCallAdvice(
        hero_stack_bb=round(hero_stack_bb, 1),
        villain_shove_bb=round(villain_shove_bb, 1),
        villain_position=villain_position.upper(),
        hero_position=hero_position.upper(),
        hero_hand_rank_pct=round(hero_hand_rank_pct, 3),
        n_players=n_players,
        is_tournament=is_tournament,
        icm_pressure=round(icm_pressure, 3),
        villain_push_range_pct=villain_range,
        hero_equity=hero_eq,
        required_equity_chip=req_chip,
        required_equity_icm=req_icm,
        equity_margin=eq_margin,
        call_cost_bb=round(call_cost, 1),
        pot_total_bb=round(pot_total, 1),
        ev_call=ev_c,
        ev_fold=ev_f,
        decision=decision,
        confidence=conf,
        nash_call_range=nash_range,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def nc_one_liner(r: NashCallAdvice) -> str:
    return (
        f'[NC {r.hero_position}vs{r.villain_position}@{r.villain_shove_bb:.0f}BB] '
        f'{r.decision.upper()} ({r.confidence}) | '
        f'eq={r.hero_equity:.0%} req={r.required_equity_icm:.0%} margin={r.equity_margin:+.0%} | '
        f'ev={r.ev_call:+.2f}BB'
    )
