"""
Postflop Fold-to-Raise Advisor (postflop_fold_to_raise_advisor.py)

Advises whether to fold, call, or re-raise when villain raises hero's
continuation bet or lead on the flop or turn.

Common scenario: Hero cbets, villain raises. Should hero fold/call/3-bet?

KEY FACTORS:
  1. Pot odds: What price is hero getting?
  2. Hero equity: How often does hero have the best hand + draws?
  3. Villain raise range: Is it wide (bluffs + air) or tight (value-heavy)?
  4. Hero hand type: Draw/made hand/bluff catcher
  5. Effective SPR: Is there room to maneuver after calling?
  6. Street: Flop raise is more commonly semi-bluff; turn raise is value-heavy

VILLAIN RAISE RANGE INTERPRETATION:
  Aggressive villain (AF>=2.5, high 3-bet%): includes many semi-bluffs
  Passive villain (AF<1.5): heavy on value, light on bluffs
  Flop raise: 60-70% draws/semi-bluffs from aggressive villain
  Turn raise: 40-50% draws/semi-bluffs from aggressive villain (dry up)

DECISION THRESHOLDS:
  fold:   hero equity < break-even equity (pot odds threshold)
  call:   equity OK, but re-raising doesn't gain enough fold equity
  raise:  strong draws/sets + villain semi-bluffs + fold equity exists
  shove:  short SPR, good equity, shove is best play

DISTINCT FROM OTHER MODULES:
  postflop_spr_decision.py:  SPR-based hand selection
  range_protect_advisor.py:  Range construction and protection
  THIS MODULE:               Specific response to villain's flop/turn raise;
                             fold/call/3-bet decision tree; pot odds + equity

Usage:
    from poker.postflop_fold_to_raise_advisor import advise_fold_to_raise, FoldRaiseAdvice, ftr_one_liner

    result = advise_fold_to_raise(
        pot_before_raise=12.0,
        hero_bet=6.0,
        villain_raise_to=18.0,
        hero_stack=80.0,
        hero_equity=0.42,
        hero_hand_type='flush_draw',
        villain_af=2.8,
        villain_raise_pct=0.12,
        street='flop',
        hero_position='ip',
    )
    print(ftr_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


def _pot_odds(call_amount: float, pot_after_call: float) -> float:
    """Break-even equity needed to call."""
    return call_amount / pot_after_call


def _villain_value_pct(villain_af: float, villain_raise_pct: float, street: str) -> float:
    """
    Estimate villain's value bet percentage of their raise range.
    Higher AF and lower raise% → stronger value heavy range.
    """
    # Flop: more semi-bluffs. Turn: more value.
    base_value = 0.35 if street == 'flop' else 0.55
    if villain_af >= 3.0:
        af_adj = -0.10   # aggressive → includes more bluffs
    elif villain_af >= 2.0:
        af_adj = 0.0
    elif villain_af >= 1.0:
        af_adj = 0.10
    else:
        af_adj = 0.20   # very passive → almost only value

    # Low raise% → range is tight (value-heavy)
    if villain_raise_pct <= 0.06:
        rp_adj = 0.10
    elif villain_raise_pct <= 0.10:
        rp_adj = 0.05
    elif villain_raise_pct >= 0.18:
        rp_adj = -0.10
    else:
        rp_adj = 0.0

    return round(min(0.90, max(0.20, base_value + af_adj + rp_adj)), 2)


def _fold_equity_if_3bet(
    pot: float,
    hero_3bet_to: float,
    villain_value_pct: float,
    villain_af: float,
    hero_position: str,
) -> float:
    """
    Estimate probability villain folds to 3-bet.
    Semi-bluffs fold ~60-80% of the time; value hands almost never fold.
    """
    semi_bluff_pct = 1.0 - villain_value_pct
    # IP 3-bet has more fold equity
    ip_bonus = 0.05 if hero_position == 'ip' else 0.0

    # Semi-bluff folds: ~70% base
    semi_bluff_fold = 0.70 + ip_bonus

    # Value folds: very low
    value_fold = 0.05 + ip_bonus * 0.5

    fold_pct = semi_bluff_pct * semi_bluff_fold + villain_value_pct * value_fold
    return round(fold_pct, 3)


def _spr_after_call(hero_stack: float, villain_raise_to: float, hero_bet: float, pot_before_raise: float) -> float:
    call_amount = villain_raise_to - hero_bet
    pot_after = pot_before_raise + hero_bet + villain_raise_to
    remaining = hero_stack - call_amount
    return round(remaining / max(pot_after, 1.0), 2)


def _hand_type_equity_bonus(hero_hand_type: str) -> float:
    """Adjustment to hero's equity based on hand type context."""
    return {
        'nut_flush_draw': 0.08,
        'flush_draw':     0.05,
        'oesd':           0.05,
        'combo_draw':     0.12,  # flush + straight draw
        'top_pair':       0.03,
        'two_pair':       0.05,
        'set':            0.08,
        'bluff_catcher':  -0.05,
        'air':           -0.10,
        'overpair':       0.04,
        'bottom_pair':   -0.03,
    }.get(hero_hand_type, 0.0)


@dataclass
class FoldRaiseAdvice:
    # Inputs
    pot_before_raise: float
    hero_bet: float
    villain_raise_to: float
    hero_stack: float
    hero_equity: float
    hero_hand_type: str
    villain_af: float
    villain_raise_pct: float
    street: str
    hero_position: str

    # Pot odds analysis
    call_amount: float
    pot_after_call: float
    breakeven_equity: float  # required equity to call profitably
    equity_margin: float     # hero_equity - breakeven_equity

    # Villain range analysis
    villain_value_pct: float   # estimated % of raise range that is value
    villain_bluff_pct: float   # estimated % that is semi-bluff/bluff

    # 3-bet analysis
    hero_3bet_to: float
    fold_equity: float           # estimated fold probability
    ev_3bet: float               # EV of 3-betting
    ev_call: float               # EV of calling
    ev_fold: float               # 0 always (fold = give up)

    # SPR
    spr_after_call: float
    is_short_spr: bool           # SPR < 1.5

    # Decision
    action: str           # 'fold' / 'call' / 'raise' / 'shove'
    confidence: str       # 'high' / 'medium' / 'low'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_fold_to_raise(
    pot_before_raise: float = 12.0,
    hero_bet: float = 6.0,
    villain_raise_to: float = 18.0,
    hero_stack: float = 80.0,
    hero_equity: float = 0.42,
    hero_hand_type: str = 'flush_draw',  # see _hand_type_equity_bonus for options
    villain_af: float = 2.5,
    villain_raise_pct: float = 0.12,
    street: str = 'flop',
    hero_position: str = 'ip',
) -> FoldRaiseAdvice:
    """
    Advise hero on folding/calling/raising when villain raises hero's cbet or lead.

    Args:
        pot_before_raise:  Pot size before villain's raise (hero's bet not included)
        hero_bet:          Hero's bet that villain raised
        villain_raise_to:  Amount villain raised to
        hero_stack:        Hero's stack BEFORE the raise (not counting already bet)
        hero_equity:       Hero's raw equity vs villain's perceived range (0-1)
        hero_hand_type:    Type of hand hero holds
        villain_af:        Villain's aggression factor
        villain_raise_pct: Villain's raise percentage in this spot
        street:            'flop' or 'turn'
        hero_position:     'ip' or 'oop'

    Returns:
        FoldRaiseAdvice
    """
    call_amount = villain_raise_to - hero_bet
    pot_after_call = pot_before_raise + hero_bet + villain_raise_to + call_amount
    be_eq = _pot_odds(call_amount, pot_after_call)

    villain_val_pct = _villain_value_pct(villain_af, villain_raise_pct, street)
    villain_bluff_pct = 1.0 - villain_val_pct

    # Equity with hand-type bonus
    adj_equity = min(0.95, max(0.05, hero_equity + _hand_type_equity_bonus(hero_hand_type)))
    equity_margin = round(adj_equity - be_eq, 3)

    # 3-bet sizing: ~2.5x villain's raise
    hero_3bet_to = round(villain_raise_to * 2.5, 1)
    hero_3bet_cost = hero_3bet_to - hero_bet
    fold_eq = _fold_equity_if_3bet(pot_after_call, hero_3bet_to, villain_val_pct, villain_af, hero_position)

    # EV of 3-bet
    pot_now = pot_before_raise + hero_bet + villain_raise_to
    ev_3bet_win_folds = fold_eq * pot_now          # villain folds: hero wins current pot
    ev_3bet_call = (1.0 - fold_eq) * (adj_equity * (pot_now + hero_3bet_cost) - hero_3bet_cost)
    ev_3bet = round(ev_3bet_win_folds + ev_3bet_call - hero_3bet_cost * fold_eq, 2)
    # Simpler formulation: EV = p_fold * pot_now + p_call * (equity * total_pot - cost) - cost
    # When villain calls we put in hero_3bet_cost more
    ev_3bet = round(fold_eq * pot_now + (1 - fold_eq) * adj_equity * (pot_now + hero_3bet_cost + hero_3bet_to) - hero_3bet_cost, 2)

    # EV of call
    ev_call = round(adj_equity * pot_after_call - call_amount, 2)

    ev_fold = 0.0  # hero gives up their investment already made

    spr = _spr_after_call(hero_stack, villain_raise_to, hero_bet, pot_before_raise)
    short_spr = spr < 1.5

    # Decision logic
    if adj_equity < be_eq - 0.05:
        action = 'fold'
        confidence = 'high'
    elif short_spr and adj_equity >= be_eq:
        action = 'shove'
        confidence = 'high' if adj_equity >= be_eq + 0.05 else 'medium'
    elif ev_3bet > ev_call and ev_3bet > 0 and (
        hero_hand_type in ('combo_draw', 'set', 'flush_draw', 'oesd', 'nut_flush_draw', 'overpair')
        and fold_eq >= 0.45
    ):
        action = 'raise'
        confidence = 'high' if ev_3bet > ev_call + 2.0 else 'medium'
    elif adj_equity >= be_eq:
        action = 'call'
        confidence = 'high' if equity_margin > 0.08 else 'medium' if equity_margin > 0.02 else 'low'
    else:
        action = 'fold'
        confidence = 'medium' if abs(equity_margin) < 0.04 else 'high'

    # Reasoning
    reasoning = (
        f'Hero cbets {hero_bet:.1f}BB into {pot_before_raise:.1f}BB pot; villain raises to {villain_raise_to:.1f}BB. '
        f'Call={call_amount:.1f}BB into pot_after={pot_after_call:.1f}BB. '
        f'Need {be_eq:.0%} equity (breakeven); have {adj_equity:.0%} (margin={equity_margin:+.0%}). '
        f'Villain range: {villain_val_pct:.0%} value, {villain_bluff_pct:.0%} bluffs (AF={villain_af}, raise%={villain_raise_pct:.0%}). '
        f'EV(call)={ev_call:+.2f} EV(raise)={ev_3bet:+.2f} EV(fold)=0. '
        f'SPR_after_call={spr:.1f}{"(short)" if short_spr else ""}. '
        f'Recommendation: {action} ({confidence} confidence).'
    )

    verdict = (
        f'[FTR {street.upper()}|{hero_hand_type}|{hero_position}] '
        f'{action.upper()} ({confidence}) | '
        f'eq={adj_equity:.0%} be={be_eq:.0%} margin={equity_margin:+.0%} | '
        f'ev_call={ev_call:+.2f} ev_raise={ev_3bet:+.2f}'
    )

    tips = []

    if villain_bluff_pct >= 0.55 and street == 'flop':
        tips.append(
            f'Villain bluffs {villain_bluff_pct:.0%} of their raises on the flop (high bluff frequency). '
            f'Calling is profitable vs this aggressive player; consider 3-betting with strong draws/sets.'
        )

    if action == 'raise':
        tips.append(
            f'3-BET SIZING: Raise to {hero_3bet_to:.1f}BB (2.5x villain raise). '
            f'Fold equity={fold_eq:.0%}: villain folds {fold_eq:.0%} of range. '
            f'EV of raise: {ev_3bet:+.2f}BB vs EV of call: {ev_call:+.2f}BB.'
        )
    elif action == 'shove':
        tips.append(
            f'SHORT SPR SHOVE (SPR={spr:.1f}): With low SPR, raising to {hero_3bet_to:.1f}BB commits stack anyway. '
            f'Shove for maximum fold equity and to deny draws from calling at good odds. '
            f'Equity={adj_equity:.0%} vs breakeven={be_eq:.0%}.'
        )
    elif action == 'call':
        tips.append(
            f'CALL AND EVALUATE: Hero has {adj_equity:.0%} equity (breakeven={be_eq:.0%}). '
            f'SPR after call = {spr:.1f}. '
            f'On {"turn" if street == "flop" else "river"}: '
            f'{"re-evaluate before betting again" if spr >= 2.0 else "likely commit/fold on next street"}.'
        )

    if street == 'turn' and villain_val_pct >= 0.65:
        tips.append(
            f'TURN RAISE WARNING: Villain raises turn {villain_raise_pct:.0%} of the time with {villain_val_pct:.0%} value range. '
            f'Turn raises are value-heavy — folding marginal hands is correct. '
            f'Even a flush draw may be a fold if villain is very tight.'
        )

    if hero_hand_type == 'air':
        tips.append(
            f'AIR AGAINST RAISE: You have no equity. Fold immediately. '
            f'Do not call on the hope villain is bluffing — with no equity you lose even when you call correctly.'
        )

    return FoldRaiseAdvice(
        pot_before_raise=pot_before_raise,
        hero_bet=hero_bet,
        villain_raise_to=villain_raise_to,
        hero_stack=hero_stack,
        hero_equity=round(hero_equity, 3),
        hero_hand_type=hero_hand_type,
        villain_af=villain_af,
        villain_raise_pct=villain_raise_pct,
        street=street,
        hero_position=hero_position,
        call_amount=round(call_amount, 2),
        pot_after_call=round(pot_after_call, 2),
        breakeven_equity=round(be_eq, 3),
        equity_margin=equity_margin,
        villain_value_pct=villain_val_pct,
        villain_bluff_pct=villain_bluff_pct,
        hero_3bet_to=hero_3bet_to,
        fold_equity=fold_eq,
        ev_3bet=ev_3bet,
        ev_call=ev_call,
        ev_fold=ev_fold,
        spr_after_call=spr,
        is_short_spr=short_spr,
        action=action,
        confidence=confidence,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ftr_one_liner(r: FoldRaiseAdvice) -> str:
    return (
        f'[FTR {r.street.upper()}|{r.hero_hand_type}|{r.hero_position}] '
        f'{r.action.upper()} ({r.confidence}) | '
        f'eq={r.hero_equity:.0%} be={r.breakeven_equity:.0%} margin={r.equity_margin:+.0%} | '
        f'ev_call={r.ev_call:+.2f} ev_raise={r.ev_3bet:+.2f}'
    )
