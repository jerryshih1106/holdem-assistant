"""
Preflop All-In EV Calculator (preflop_allin_ev.py)

When facing a preflop shove (or considering shoving), calculate the precise
EV of calling vs folding based on:
  - Hero's hand equity vs villain's estimated shoving range
  - Pot size, call amount, effective stacks
  - ICM adjustment factor (optional, for tournaments)

CORE FORMULAS:
  required_equity = call / (pot_total + call)
  ev_call = equity × (pot + call) - call
  ev_fold = 0

  Decision: call when ev_call > ev_fold (i.e., equity > required_equity)

VILLAIN RANGE ESTIMATION:
  Villain shoves based on: position + stack depth + VPIP
  Deep stack (25+ BB): premium hands only (AA/KK/QQ/JJ/AKs: ~3-5%)
  Short stack (15 BB): Nash push range (~25-40% depending on position)
  Very short (8 BB):   Almost any hand from late position (~50-70%)

VILLAIN POSITION ADJUSTMENTS:
  BTN jam: much wider range than UTG jam
  SB jam: wide (BTN range is extremely wide)
  BB jam: defensive, often wider than expected vs steals

IMPORTANT DISTINCTION FROM pushfold.py:
  pushfold.py = "which hands should I PUSH with" (Nash frequencies)
  This module = "should I CALL this specific shove" (precise EV calculation)
  + "should I shove my hand into this specific villain?"

Usage:
    from poker.preflop_allin_ev import calc_allin_ev, AllinEVResult, allin_one_liner

    result = calc_allin_ev(
        hero_hand_rank_pct=0.93,   # JJ = ~93rd percentile
        villain_stack_bb=25.0,
        villain_position='BTN',
        villain_vpip=0.30,
        pot_bb=3.0,                # blinds + antes
        call_bb=25.0,              # villain's jam amount
        effective_stack_bb=50.0,
        is_tournament=False,
    )
    print(allin_one_liner(result))
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple


# --------------------------------------------------------------------------
# Villain jam range estimation
# --------------------------------------------------------------------------

# Nash push ranges by stack (rough approximation, BTN baseline)
_NASH_PUSH_PCT_BTN = {
    5:  0.75,
    8:  0.55,
    10: 0.45,
    12: 0.38,
    15: 0.30,
    20: 0.20,
    25: 0.12,
    30: 0.08,
    40: 0.05,
    50: 0.04,
}

_POSITION_JAM_MULT = {
    'UTG':  0.35,   # much tighter
    'UTG1': 0.40,
    'MP':   0.50,
    'HJ':   0.60,
    'CO':   0.75,
    'BTN':  1.00,   # baseline
    'SB':   1.10,
    'BB':   1.20,   # defensive/squeeze jams
}

# Equity vs villain's estimated jam range, given hero hand rank pct
# Approximate: vs tight ranges, equity is lower; vs wide ranges, equity is higher
def _equity_vs_jam_range(hero_rank_pct: float, villain_range_pct: float) -> float:
    """
    Estimate hero's hand equity vs villain's jam range.
    Higher hero_rank_pct = stronger hand = more equity.
    Wider villain_range_pct = villain has more trash = hero has more equity.
    """
    # Base equity model:
    # Very strong hands (AA) vs any range: 80-85%
    # Premium (QQ/AK) vs typical jam range: 55-65%
    # Medium (TT/AQs) vs typical jam range: 50-58%
    # Marginal (77/ATs) vs tight jam range: 40-48%

    # Baseline: equity = f(hero_rank_pct) adjusted by villain range width
    base_equity = 0.30 + hero_rank_pct * 0.55   # 0.30 to 0.85

    # Wider villain range = villain has more dominated hands = hero has more equity
    # Typical jam range 15% -> hero gets full base equity
    # Tighter jam range 5% -> hero loses some equity (villain has only premium hands)
    # Wider jam range 40% -> hero gains equity (villain has trash)
    range_adj = (villain_range_pct - 0.15) * 0.30
    adj_equity = base_equity + range_adj

    # Special cases for very strong hands
    if hero_rank_pct >= 0.98:   # AA
        adj_equity = 0.82 + (villain_range_pct - 0.05) * 0.04
    elif hero_rank_pct >= 0.96:  # KK
        adj_equity = 0.75 + (villain_range_pct - 0.05) * 0.04
    elif hero_rank_pct >= 0.93:  # QQ
        adj_equity = 0.65 + (villain_range_pct - 0.05) * 0.05
    elif hero_rank_pct >= 0.90:  # JJ
        adj_equity = 0.58 + (villain_range_pct - 0.10) * 0.05
    elif hero_rank_pct >= 0.87:  # TT
        adj_equity = 0.54 + (villain_range_pct - 0.10) * 0.05

    return round(min(0.90, max(0.15, adj_equity)), 3)


def _estimate_villain_jam_range(
    stack_bb: float,
    position: str,
    vpip: float,
) -> float:
    """Estimate villain's shoving range as a fraction of all hands."""
    # Start with Nash BTN baseline for this stack
    if stack_bb <= 5:
        base = 0.75
    elif stack_bb >= 50:
        base = 0.04
    else:
        # Interpolate from table
        sorted_keys = sorted(_NASH_PUSH_PCT_BTN.keys())
        lo, hi = sorted_keys[0], sorted_keys[-1]
        for i in range(len(sorted_keys) - 1):
            if sorted_keys[i] <= stack_bb <= sorted_keys[i + 1]:
                lo, hi = sorted_keys[i], sorted_keys[i + 1]
                break
        pct_lo = _NASH_PUSH_PCT_BTN[lo]
        pct_hi = _NASH_PUSH_PCT_BTN[hi]
        t = (stack_bb - lo) / (hi - lo)
        base = pct_lo + t * (pct_hi - pct_lo)

    pos_mult = _POSITION_JAM_MULT.get(position.upper(), 1.0)
    # VPIP adjustment: loose player jams wider, tight player jams tighter
    vpip_adj = (vpip - 0.25) * 0.20    # +/- 20% per 10% VPIP deviation

    result = base * pos_mult + vpip_adj
    return round(max(0.02, min(0.85, result)), 3)


def _required_equity(call_bb: float, pot_bb: float) -> float:
    """Minimum equity to break even on a call."""
    total_pot = pot_bb + call_bb
    return round(call_bb / total_pot, 3)


def _ev_call(equity: float, pot_bb: float, call_bb: float) -> float:
    """EV of calling the all-in."""
    return round(equity * (pot_bb + call_bb) - call_bb, 2)


def _icm_adjusted_ev(
    ev_call: float,
    ev_fold: float,
    stack_bb: float,
    avg_stack_bb: float,
    icm_pressure: float,
) -> Tuple[float, float]:
    """
    Adjust EV for ICM in tournament contexts.
    ICM always makes calling less attractive vs chip EV:
      - Positive chip EV is discounted (gains worth less in tournament equity)
      - Negative chip EV is worsened (busting out has extra ICM penalty)
    Returns: (icm_ev_call, icm_ev_fold)
    """
    stack_ratio = stack_bb / max(avg_stack_bb, 1.0)

    if stack_ratio > 1.5:
        icm_penalty = icm_pressure * 0.30
    elif stack_ratio > 0.8:
        icm_penalty = icm_pressure * 0.15
    else:  # short stack: smaller penalty (must gamble to survive)
        icm_penalty = icm_pressure * 0.05

    # Discounts gains; amplifies losses — always pushes toward folding
    if ev_call >= 0:
        icm_ev_call = ev_call * (1.0 - icm_penalty)
    else:
        icm_ev_call = ev_call * (1.0 + icm_penalty)

    return round(icm_ev_call, 2), 0.0


def _risk_of_ruin_call(
    call_bb: float,
    stack_bb: float,
    ev_call: float,
) -> float:
    """Fraction of stack risked by calling."""
    return round(call_bb / max(stack_bb, 1.0), 3)


@dataclass
class AllinEVResult:
    # Inputs
    hero_hand_rank_pct: float
    villain_stack_bb: float
    villain_position: str
    villain_vpip: float
    pot_bb: float
    call_bb: float
    effective_stack_bb: float
    is_tournament: bool
    icm_pressure: float

    # Villain range
    villain_jam_range_pct: float    # estimated % of hands villain shoves with
    range_description: str          # 'ultra_tight', 'tight', 'standard', 'wide', 'very_wide'

    # Hero equity
    hero_equity: float
    required_equity: float
    equity_margin: float            # hero_equity - required_equity

    # EV calculation
    ev_call: float
    ev_fold: float
    ev_advantage: float             # ev_call - ev_fold

    # ICM-adjusted (if tournament)
    icm_ev_call: float
    icm_ev_advantage: float

    # Decision
    decision: str                   # 'call', 'fold', 'marginal_call', 'marginal_fold'
    confidence: str                 # 'high', 'medium', 'low'
    stack_risk_pct: float           # % of stack risked

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calc_allin_ev(
    hero_hand_rank_pct: float = 0.85,
    villain_stack_bb: float = 20.0,
    villain_position: str = 'BTN',
    villain_vpip: float = 0.30,
    pot_bb: float = 3.0,
    call_bb: float = 20.0,
    effective_stack_bb: float = 50.0,
    is_tournament: bool = False,
    icm_pressure: float = 0.0,
    avg_stack_bb: float = 50.0,
) -> AllinEVResult:
    """
    Calculate EV of calling or folding a preflop all-in.

    Args:
        hero_hand_rank_pct:  Hero hand strength (0=worst, 1=best). Examples:
                             AA=0.99, KK=0.98, QQ=0.96, JJ=0.93, TT=0.89,
                             99=0.83, AKs=0.97, AKo=0.92, AQs=0.87, AQo=0.74,
                             KQs=0.77, 76s=0.55, A5s=0.62, 72o=0.01
        villain_stack_bb:    Villain's effective stack before jam
        villain_position:    Villain's table position
        villain_vpip:        Villain's VPIP (0.0-1.0)
        pot_bb:              Pot before hero's call decision (includes antes/blinds)
        call_bb:             Amount hero must call to go all-in
        effective_stack_bb:  Hero's effective stack
        is_tournament:       True if tournament (ICM matters)
        icm_pressure:        ICM pressure level (0=none, 1=extreme bubble)
        avg_stack_bb:        Average stack in tournament

    Returns:
        AllinEVResult
    """
    villain_range = _estimate_villain_jam_range(
        villain_stack_bb, villain_position, villain_vpip
    )

    if villain_range <= 0.05:
        range_desc = 'ultra_tight'
    elif villain_range <= 0.10:
        range_desc = 'tight'
    elif villain_range <= 0.20:
        range_desc = 'standard'
    elif villain_range <= 0.35:
        range_desc = 'wide'
    else:
        range_desc = 'very_wide'

    hero_eq = _equity_vs_jam_range(hero_hand_rank_pct, villain_range)
    req_eq = _required_equity(call_bb, pot_bb)
    eq_margin = round(hero_eq - req_eq, 3)

    ev_c = _ev_call(hero_eq, pot_bb, call_bb)
    ev_f = 0.0
    ev_adv = round(ev_c - ev_f, 2)

    icm_ev_c, _ = _icm_adjusted_ev(ev_c, ev_f, effective_stack_bb, avg_stack_bb, icm_pressure)
    icm_adv = round(icm_ev_c - ev_f, 2)

    stack_risk = _risk_of_ruin_call(call_bb, effective_stack_bb, ev_c)

    # Decision logic
    effective_ev = icm_ev_c if is_tournament else ev_c
    margin_threshold = 0.03   # call if equity > required + 3%

    if eq_margin >= margin_threshold:
        if eq_margin >= 0.10:
            decision = 'call'
            confidence = 'high'
        else:
            decision = 'call'
            confidence = 'medium'
    elif eq_margin <= -margin_threshold:
        decision = 'fold'
        confidence = 'high' if eq_margin <= -0.10 else 'medium'
    elif eq_margin > 0:
        decision = 'marginal_call'
        confidence = 'low'
    else:
        decision = 'marginal_fold'
        confidence = 'low'

    # Override if tournament ICM is against calling
    if is_tournament and icm_pressure >= 0.50 and eq_margin < 0.12:
        if decision == 'call':
            decision = 'marginal_call'
            confidence = 'low'

    reasoning = (
        f'Villain {villain_position} jams {villain_stack_bb:.0f}BB ({villain_range:.0%} range = {range_desc}). '
        f'Hero equity={hero_eq:.0%} vs required={req_eq:.0%} (margin={eq_margin:+.1%}). '
        f'EV(call)={ev_c:+.2f}BB EV(fold)=0. '
        f'Stack at risk: {stack_risk:.0%}. Decision: {decision}.'
    )

    verdict = (
        f'[ALLIN {villain_position}@{villain_stack_bb:.0f}BB|{range_desc}] '
        f'{decision.upper()} ({confidence}) | '
        f'eq={hero_eq:.0%} req={req_eq:.0%} margin={eq_margin:+.1%} | '
        f'ev={ev_c:+.2f}BB'
    )

    tips = []

    if decision in ('call', 'marginal_call'):
        tips.append(
            f'{"CALL" if decision=="call" else "MARGINAL CALL"}: '
            f'EV={ev_c:+.2f}BB. '
            f'Hero equity ({hero_eq:.0%}) {"comfortably" if eq_margin>=0.10 else "marginally"} '
            f'exceeds breakeven ({req_eq:.0%}). '
            f'Villain range is {range_desc} ({villain_range:.0%} of hands).'
        )
    else:
        tips.append(
            f'{"FOLD" if decision=="fold" else "MARGINAL FOLD"}: '
            f'EV={ev_c:+.2f}BB. '
            f'Hero equity ({hero_eq:.0%}) is {"far" if eq_margin<=-0.10 else "slightly"} '
            f'below required ({req_eq:.0%}). '
            f'Villain {range_desc} range gives you insufficient equity.'
        )

    if range_desc in ('ultra_tight', 'tight') and hero_hand_rank_pct < 0.90:
        tips.append(
            f'TIGHT JAM WARNING: Villain jams only {villain_range:.0%} of hands from {villain_position}. '
            f'This range is AA/KK/QQ/AKs heavy. '
            f'Only call with premium holdings (QQ+ / AK).'
        )
    elif range_desc == 'very_wide' and hero_hand_rank_pct >= 0.55:
        tips.append(
            f'WIDE JAM: Villain jams {villain_range:.0%} of hands — many weak holdings. '
            f'Hero has good equity ({hero_eq:.0%}) and should call profitably.'
        )

    if is_tournament and icm_pressure >= 0.30:
        tips.append(
            f'ICM WARNING (pressure={icm_pressure:.0%}): '
            f'ICM-adjusted EV={icm_ev_c:+.2f}BB vs chip EV={ev_c:+.2f}BB. '
            f'Near the bubble, calling off stack requires higher equity threshold. '
            f'Add ~5-8% to required equity: need {req_eq + 0.07:.0%}+ to justify call.'
        )

    if stack_risk >= 0.80:
        tips.append(
            f'HIGH RISK: Calling costs {stack_risk:.0%} of your stack ({call_bb:.0f}BB). '
            f'EV must be significantly positive to justify calling off near all your chips.'
        )

    return AllinEVResult(
        hero_hand_rank_pct=round(hero_hand_rank_pct, 3),
        villain_stack_bb=round(villain_stack_bb, 1),
        villain_position=villain_position.upper(),
        villain_vpip=round(villain_vpip, 3),
        pot_bb=round(pot_bb, 1),
        call_bb=round(call_bb, 1),
        effective_stack_bb=round(effective_stack_bb, 1),
        is_tournament=is_tournament,
        icm_pressure=round(icm_pressure, 3),
        villain_jam_range_pct=villain_range,
        range_description=range_desc,
        hero_equity=hero_eq,
        required_equity=req_eq,
        equity_margin=eq_margin,
        ev_call=ev_c,
        ev_fold=ev_f,
        ev_advantage=ev_adv,
        icm_ev_call=icm_ev_c,
        icm_ev_advantage=icm_adv,
        decision=decision,
        confidence=confidence,
        stack_risk_pct=stack_risk,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def allin_one_liner(r: AllinEVResult) -> str:
    return (
        f'[ALLIN {r.villain_position}@{r.villain_stack_bb:.0f}BB|{r.range_description}] '
        f'{r.decision.upper()} ({r.confidence}) | '
        f'eq={r.hero_equity:.0%} req={r.required_equity:.0%} margin={r.equity_margin:+.1%} | '
        f'ev={r.ev_call:+.2f}BB'
    )
