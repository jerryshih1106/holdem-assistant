"""
Minimum 4-Bet Threshold Advisor (min_4bet_threshold.py)

Determines WHEN to 4-bet (vs. cold-call or fold a 3-bet), what hands
qualify for value 4-bet vs. 4-bet bluff, and optimal 4-bet sizing.

THEORY:
  4-BET = re-raise over a 3-bet.

  THREE RESPONSES TO A 3-BET:
  1. FOLD: When hand is too weak to continue
  2. COLD CALL: Medium-strong hands (JJ/TT/AQs/KQs) that play well post-flop
  3. 4-BET: Premium hands (AA/KK/QQ/AKs) for value; or polarized bluffs (Ax/Kx suited)

  WHY NOT 4-BET EVERYTHING STRONG?
  - 4-betting thin value (JJ/AQs) builds pot when villain has QQ/AKs and we're behind
  - Better to cold-call and play post-flop where position helps
  - Exception: 5-bet all-in spots where JJ+ is correct to jam

  4-BET BLUFF SELECTION:
  - Hands WITH blockers (Ax, Kx) reduce villain's 4-bet-continuing combos
  - Ax blocks AA/AKs; Kx blocks KK/AKs
  - Need some equity if called (suited > offsuit)
  - Best 4-bet bluffs: A2s-A5s (blockers + some equity)

  ALPHA (BREAK-EVEN FOLD%) FOR 4-BET BLUFF:
  alpha = 4bet_raise / (pot_before_4bet + 4bet_raise)
  Villain must fold more than alpha for 4-bet bluff to be profitable.

  4-BET SIZING:
  - IP:  2.2x-2.5x the 3-bet
  - OOP: 2.5x-3.0x the 3-bet
  - Stack depth matters: if SPR < 2 after 4-bet, might as well shove

  BALANCED 4-BET RANGE:
  alpha(typical_4bet) = ~0.33-0.40
  So ~1/3 of 4-bet range should be bluffs for balance.
  Example: 6 value combos (AA/KK/QQ) -> 3 bluff combos (A5s, A4s, A3s)

  VALUE 4-BET THRESHOLD:
  - Deep (100BB+): AA/KK/QQ/AKs (premium only)
  - Medium (50-100BB): AA/KK/QQ/AKs/JJ (slightly wider)
  - Short (< 50BB): AA/KK/QQ/AKs/AKo/JJ+ (shove range widens)

DISTINCT FROM:
  preflop_allin_guide.py: All-in preflop scenarios
  three_bet_ranges.py:    3-bet range construction
  preflop_sizing_optimizer.py: Open sizing
  THIS MODULE:            4-BET SPECIFIC; alpha calculation; cold-call vs. 4-bet
                          threshold; bluff hand selection; balanced 4-bet range.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Value 4-bet range by stack depth
VALUE_4BET_THRESHOLD: dict = {
    # (stack_depth): minimum hand rank to 4-bet for value
    'deep':    0.95,  # only AA/KK/QQ/AKs
    'medium':  0.92,  # + JJ
    'short':   0.88,  # + TT/AKo
    'push_fold': 0.80,  # almost any premium; fold equity matters
}

HAND_RANK: dict = {
    'AA':   1.00, 'KK':  0.99, 'QQ':  0.98, 'AKs': 0.97,
    'JJ':   0.95, 'AKo': 0.94, 'TT':  0.92, 'AQs': 0.91,
    'AQo':  0.88, 'KQs': 0.87, '99':  0.86, 'AJs': 0.84,
    'KJs':  0.82, 'QJs': 0.80, '88':  0.79, 'AJo': 0.78,
    'KQo':  0.76, 'A5s': 0.65, 'A4s': 0.64, 'A3s': 0.63, 'A2s': 0.62,
    'K5s':  0.55, 'K4s': 0.54, '77':  0.73, '66':  0.70,
}

COLD_CALL_RANGE: frozenset = frozenset(['JJ', 'TT', 'AQs', 'AQo', 'KQs', '99', 'AJs'])

BLUFF_4BET_HANDS: frozenset = frozenset(['A5s', 'A4s', 'A3s', 'A2s', 'K5s', 'K4s', 'K3s', 'K2s'])


def _stack_depth_cat(stack_bb: float) -> str:
    if stack_bb >= 100:
        return 'deep'
    elif stack_bb >= 50:
        return 'medium'
    elif stack_bb >= 25:
        return 'short'
    else:
        return 'push_fold'


def _4bet_size(threebet_bb: float, position: str) -> float:
    multiplier = 2.3 if position == 'ip' else 2.8
    return round(threebet_bb * multiplier, 1)


def _alpha(fourbet_bb: float, pot_before_4bet: float) -> float:
    return round(fourbet_bb / (pot_before_4bet + fourbet_bb), 3)


def _villain_3bet_fold_ev(
    alpha: float,
    villain_fold_to_4bet: float,
    fourbet_bb: float,
    pot_before_4bet: float,
    hero_equity_if_called: float,
    total_pot_if_called: float,
) -> float:
    fold_ev = villain_fold_to_4bet * pot_before_4bet
    call_ev = (1.0 - villain_fold_to_4bet) * (hero_equity_if_called * total_pot_if_called - fourbet_bb)
    return round(fold_ev + call_ev, 2)


def _is_value_4bet(hero_hand: str, stack_bb: float) -> bool:
    depth_cat = _stack_depth_cat(stack_bb)
    threshold = VALUE_4BET_THRESHOLD.get(depth_cat, 0.95)
    hand_rank = HAND_RANK.get(hero_hand, 0.50)
    return hand_rank > threshold


def _is_bluff_4bet(hero_hand: str) -> bool:
    return hero_hand in BLUFF_4BET_HANDS


def _should_cold_call(hero_hand: str) -> bool:
    return hero_hand in COLD_CALL_RANGE


@dataclass
class FourBetResult:
    hero_hand: str
    stack_bb: float
    position: str

    is_value_4bet: bool
    is_bluff_4bet: bool
    should_cold_call: bool

    fourbet_size_bb: float
    alpha_breakeven: float
    bluff_4bet_ev_bb: float

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_4bet(
    hero_hand: str = 'AKs',
    stack_bb: float = 100.0,
    position: str = 'ip',
    threebet_bb: float = 9.0,
    pot_before_4bet: float = 12.0,
    villain_fold_to_4bet: float = 0.50,
    hero_equity_if_4bet_called: float = 0.55,
) -> FourBetResult:
    """
    Analyze whether to 4-bet, cold-call, or fold vs. a 3-bet.

    Args:
        hero_hand:                Hero's hole cards / hand category
        stack_bb:                 Hero's effective stack in BB
        position:                 Hero's position vs. 3-bettor ('ip' / 'oop')
        threebet_bb:              Size of villain's 3-bet in BB
        pot_before_4bet:          Pot size before hero acts
        villain_fold_to_4bet:     Villain's fold% facing a 4-bet
        hero_equity_if_4bet_called: Hero's equity when 4-bet is called

    Returns:
        FourBetResult
    """
    val_4bet = _is_value_4bet(hero_hand, stack_bb)
    bluff_4bet = _is_bluff_4bet(hero_hand)
    cold_call = _should_cold_call(hero_hand)
    fb_size = _4bet_size(threebet_bb, position)
    alpha = _alpha(fb_size, pot_before_4bet)
    total_pot_if_called = pot_before_4bet + 2 * fb_size
    bluff_ev = _villain_3bet_fold_ev(
        alpha, villain_fold_to_4bet, fb_size, pot_before_4bet,
        hero_equity_if_4bet_called, total_pot_if_called,
    )

    if val_4bet:
        action = '4BET_VALUE'
    elif bluff_4bet and villain_fold_to_4bet > alpha:
        action = '4BET_BLUFF'
    elif cold_call:
        action = 'COLD_CALL'
    else:
        action = 'FOLD'

    verdict = (
        f'[4BT {hero_hand}|{position}|{stack_bb:.0f}BB] '
        f'{action} size={fb_size:.0f}BB | '
        f'alpha={alpha:.0%} fold_vs_4b={villain_fold_to_4bet:.0%} EV={bluff_ev:+.1f}BB'
    )

    reasoning = (
        f'4-bet analysis: {hero_hand} in {position.upper()} at {stack_bb:.0f}BB. '
        f'Villain 3-bet={threebet_bb:.0f}BB. '
        f'4-bet to {fb_size:.0f}BB. Alpha={alpha:.0%}. '
        f'Villain fold to 4-bet: {villain_fold_to_4bet:.0%}. '
        f'EV if bluffing: {bluff_ev:+.1f}BB. '
        f'Recommendation: {action}.'
    )

    tips = []

    tips.append(
        f'4-BET SIZING: {position.upper()} 4-bet to {fb_size:.0f}BB ({fb_size/threebet_bb:.1f}x). '
        f'Break-even fold% = {alpha:.0%}. '
        f'Villain folds {villain_fold_to_4bet:.0%} -> {"profitable" if villain_fold_to_4bet > alpha else "unprofitable"} bluff 4-bet.'
    )

    if val_4bet:
        tips.append(
            f'VALUE 4-BET: {hero_hand} is in value 4-bet range at {stack_bb:.0f}BB ({_stack_depth_cat(stack_bb)}). '
            f'Build pot now; villain 3-bet range is often dominated by AA/KK/QQ/AKs. '
            f'4-bet for max value; do not cold-call with premium.'
        )
    elif bluff_4bet:
        if villain_fold_to_4bet > alpha:
            tips.append(
                f'4-BET BLUFF: {hero_hand} has blockers to villain\'s continuing range. '
                f'Villain folds {villain_fold_to_4bet:.0%} > alpha {alpha:.0%}. '
                f'EV={bluff_ev:+.1f}BB. Include ~1/3 bluffs in 4-bet range for balance.'
            )
        else:
            tips.append(
                f'BLUFF 4-BET MARGINAL: Villain folds {villain_fold_to_4bet:.0%} but need {alpha:.0%}. '
                f'4-bet bluff EV={bluff_ev:+.1f}BB. Prefer fold over bluff unless villain is over-folding.'
            )
    elif cold_call:
        tips.append(
            f'COLD CALL: {hero_hand} plays well post-flop but is not strong enough to 4-bet for value. '
            f'Cold-call vs. 3-bet and play IP/in position. '
            f'If OOP, lean towards fold with this hand ({hero_hand}) vs. a 3-bet.'
        )
    else:
        tips.append(
            f'FOLD: {hero_hand} is not in 4-bet range (value or bluff) and not in cold-call range. '
            f'Against a 3-bet, fold and wait for a better spot.'
        )

    tips.append(
        f'BALANCED 4-BET RANGE: alpha={alpha:.0%} means ~{alpha:.0%} of 4-bet range should be bluffs. '
        f'With ~6 value combos (AA/KK/QQ), include ~{round(6*alpha/(1-alpha))} bluff combos (A5s/A4s/A3s).'
    )

    return FourBetResult(
        hero_hand=hero_hand,
        stack_bb=stack_bb,
        position=position,
        is_value_4bet=val_4bet,
        is_bluff_4bet=bluff_4bet,
        should_cold_call=cold_call,
        fourbet_size_bb=fb_size,
        alpha_breakeven=alpha,
        bluff_4bet_ev_bb=bluff_ev,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def fbt_one_liner(r: FourBetResult) -> str:
    return (
        f'[4BT {r.hero_hand}|{r.position}] '
        f'{r.recommended_action} {r.fourbet_size_bb:.0f}BB '
        f'alpha={r.alpha_breakeven:.0%} EV={r.bluff_4bet_ev_bb:+.1f}BB'
    )
