"""
Board Completion Advisor (board_completion_advisor.py)

Tracks draw completion probability and adjusts hero/villain range
estimates as each community card is revealed.

PURPOSE:
  Draws are the most common reason ranges shift on turn and river.
  This module answers:
  1. What is the probability a specific draw (flush/straight) completes
     given the current board and remaining community cards?
  2. How does draw completion change the villain's perceived range?
  3. When does the completed draw change who holds the range advantage?
  4. How should hero adjust bet/call/fold thresholds when draws complete?

DRAW COMPLETION PROBABILITIES:
  Flush draw (9 outs, flop):
    Turn: 9/47 = 19.1%
    River: 9/46 = 19.6% (given missed on turn)
    Flop-to-river: 1 - (38/47)*(37/46) = 35.0%
  Open-ended straight draw (8 outs):
    Turn: 8/47 = 17.0%
    Flop-to-river: 31.5%
  Gutshot (4 outs):
    Turn: 4/47 = 8.5%
    Flop-to-river: 16.5%
  Combo draw FD+OESD (15 outs):
    Turn: 15/47 = 31.9%
    Flop-to-river: 54.1%

RANGE ADJUSTMENT WHEN DRAW COMPLETES:
  When a flush card arrives:
  - Villain's range (wider caller) gains flush weight: 15-25% of range has flush
  - PFR's range (narrower): 8-12% has flush (fewer suited hands opened)
  - This shifts range advantage toward the caller significantly

  When a straight card arrives (e.g., 6 on T-9-7 board):
  - Both ranges affected similarly but connector hands in caller range gain
  - Straight completion tilts range advantage slight toward caller

ADAPTING HERO'S STRATEGY:
  If hero has the draw:
    - Continuing equity = pure_equity + implied_odds_bonus
    - Implied odds bonus = P(complete) * expected_win_if_complete
  If hero has made hand (and draw completes):
    - Reassess strength: is made hand still good?
    - Check/call becomes correct over lead/bet in some spots

DISTINCT FROM:
  equity_calculator.py:     Raw equity calculation
  turn_runout_analysis.py:  Turn-specific range advantage shift
  hand_vs_hand_equity_table.py: Equity by hand category
  THIS MODULE:              Draw-specific probability tracking;
                            which draws complete; villain range re-weighting;
                            strategy adaptation when draws complete/miss.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Draw completion outs and probabilities
DRAW_OUTS: dict = {
    'flush_draw':  9,
    'oesd':        8,
    'combo_draw':  15,
    'gutshot':     4,
    'double_gut':  8,
    'pair_to_set': 2,
    'overcards':   6,  # two overcards = 6 outs
}


def _cards_remaining(street: str) -> int:
    if street == 'flop':
        return 47
    elif street == 'turn':
        return 46
    return 0


def _turn_completion_prob(outs: int, street: str = 'flop') -> float:
    remaining = _cards_remaining(street)
    if remaining <= 0:
        return 0.0
    return round(outs / remaining, 4)


def _flop_to_river_prob(outs: int) -> float:
    """Probability of hitting on turn OR river from flop."""
    p_miss_both = ((47 - outs) / 47) * ((46 - outs) / 46)
    return round(1.0 - p_miss_both, 4)


# Villain range weight for completed draws
# (fraction of villain's range that has the completed draw)
VILLAIN_DRAW_WEIGHT = {
    'flush_draw':  0.18,   # typical caller range has ~18% flush draws
    'oesd':        0.12,
    'combo_draw':  0.08,
    'gutshot':     0.14,
}

PFR_DRAW_WEIGHT = {
    'flush_draw':  0.10,   # PFR opens fewer suited hands on average
    'oesd':        0.08,
    'combo_draw':  0.05,
    'gutshot':     0.08,
}


def _range_advantage_shift(draw_type: str, hero_is_pfr: bool) -> float:
    """How much does hero's range advantage shift when draw completes?"""
    villain_wt = VILLAIN_DRAW_WEIGHT.get(draw_type, 0.15)
    pfr_wt = PFR_DRAW_WEIGHT.get(draw_type, 0.08)
    if hero_is_pfr:
        return round(pfr_wt - villain_wt, 3)  # negative = range disadvantage
    else:
        return round(villain_wt - pfr_wt, 3)  # positive = range advantage


def _implied_odds_bonus(
    draw_type: str,
    pot_bb: float,
    stack_bb: float,
    villain_stackoff_freq: float = 0.50,
) -> float:
    """Approximate implied odds bonus in BB for a draw."""
    outs = DRAW_OUTS.get(draw_type, 6)
    p_complete = _flop_to_river_prob(outs)
    # Implied winning = villain's remaining stack * stackoff_freq
    implied_win = min(stack_bb, pot_bb * 3) * villain_stackoff_freq
    return round(p_complete * implied_win, 2)


def _strategy_recommendation(
    hero_has_draw: bool,
    draw_completed: bool,
    hero_eq_after_complete: float,
    villain_range: str,
    hero_position: str,
) -> str:
    if hero_has_draw and not draw_completed:
        if hero_eq_after_complete >= 0.55:
            return 'continue_draw_equity_positive'
        else:
            return 'consider_folding_draw'
    elif hero_has_draw and draw_completed:
        if hero_eq_after_complete >= 0.75:
            return 'value_bet_completed_draw'
        else:
            return 'bet_medium_size'
    elif not hero_has_draw and draw_completed:
        if hero_eq_after_complete >= 0.60:
            return 'bet_for_protection'
        elif hero_eq_after_complete >= 0.45:
            return 'check_call_induce'
        else:
            return 'check_fold_draw_missed'
    else:
        return 'continue_standard_plan'


@dataclass
class DrawCompletionResult:
    draw_type: str
    street: str
    draw_completed: bool

    outs: int
    turn_prob: float
    flop_to_river_prob: float
    villain_range_weight: float
    pfr_range_weight: float
    range_advantage_shift: float

    hero_has_draw: bool
    implied_odds_bonus_bb: float
    strategy: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_draw_completion(
    draw_type: str = 'flush_draw',
    street: str = 'flop',
    draw_completed: bool = False,
    hero_has_draw: bool = True,
    hero_is_pfr: bool = True,
    pot_bb: float = 15.0,
    stack_bb: float = 100.0,
    hero_equity_if_hits: float = 0.90,
    villain_stackoff_freq: float = 0.50,
    hero_position: str = 'ip',
) -> DrawCompletionResult:
    """
    Analyze draw completion probability and strategy implications.

    Args:
        draw_type:              Type of draw
        street:                 Current street ('flop' or 'turn')
        draw_completed:         Did the draw complete on this card?
        hero_has_draw:          Does hero hold the draw?
        hero_is_pfr:            Is hero the preflop raiser?
        pot_bb:                 Current pot in BB
        stack_bb:               Effective stack in BB
        hero_equity_if_hits:    Hero's equity if draw completes
        villain_stackoff_freq:  Frequency villain stacks off vs made draw
        hero_position:          'ip' / 'oop'

    Returns:
        DrawCompletionResult
    """
    outs = DRAW_OUTS.get(draw_type, 6)
    turn_prob = _turn_completion_prob(outs, street)
    ftr_prob = _flop_to_river_prob(outs)
    villain_wt = VILLAIN_DRAW_WEIGHT.get(draw_type, 0.15)
    pfr_wt = PFR_DRAW_WEIGHT.get(draw_type, 0.08)
    adv_shift = _range_advantage_shift(draw_type, hero_is_pfr)
    implied_bonus = _implied_odds_bonus(draw_type, pot_bb, stack_bb, villain_stackoff_freq)

    villain_range = 'draw_weighted' if draw_completed else 'pre_completion'
    strategy = _strategy_recommendation(
        hero_has_draw, draw_completed,
        hero_equity_if_hits,
        villain_range, hero_position,
    )

    verdict = (
        f'[BCA {draw_type}|{street}{"(HIT)" if draw_completed else "(MISS)"}] '
        f'{"HERO HIT" if (hero_has_draw and draw_completed) else "VILLAIN HIT" if (not hero_has_draw and draw_completed) else "PENDING"} | '
        f'p_complete={turn_prob:.1%} | {strategy}'
    )

    reasoning = (
        f'Draw: {draw_type} ({outs} outs) on {street}. '
        f'Turn completion: {turn_prob:.1%}, Flop-to-river: {ftr_prob:.1%}. '
        f'Villain range weight: {villain_wt:.0%} (vs PFR: {pfr_wt:.0%}). '
        f'Range advantage shift when completed: {adv_shift:+.2f}. '
        f'Implied bonus: +{implied_bonus:.1f}BB. '
        f'Strategy: {strategy}.'
    )

    tips = []

    tips.append(
        f'DRAW PROBABILITY: {draw_type} ({outs} outs). '
        f'Next card: {turn_prob:.1%} chance. '
        f'Over both remaining cards: {ftr_prob:.1%} total. '
        f'{"This is a STRONG draw -- continue aggressively." if outs >= 12 else "Moderate draw -- consider pot odds carefully." if outs >= 7 else "Weak draw -- need good pot odds to continue."}'
    )

    tips.append(
        f'RANGE IMPACT: When {draw_type} completes, villain range shifts. '
        f'Villain has {villain_wt:.0%} of flush draws in range; PFR has {pfr_wt:.0%}. '
        f'Range advantage shifts {adv_shift:+.2f} toward {"caller (disadvantage for PFR)" if adv_shift < 0 else "PFR (advantage for PFR)"} '
        f'when draw completes.'
    )

    if hero_has_draw and not draw_completed:
        tips.append(
            f'HERO HAS DRAW: {draw_type} still pending on {street}. '
            f'Implied odds bonus: +{implied_bonus:.1f}BB. '
            f'If you hit: equity={hero_equity_if_hits:.0%}. '
            f'Strategy: {strategy}. '
            f'{"Semi-bluff bet to fold equity + draw equity." if hero_position == "ip" else "Check to avoid commitment OOP; call or x/r for maximum value."}'
        )
    elif not hero_has_draw and draw_completed:
        tips.append(
            f'DRAW COMPLETED (VILLAIN MAY HAVE HIT): {draw_type} completed on {street}. '
            f'Villain range now includes completed {draw_type}: ~{villain_wt:.0%} of their range. '
            f'Reassess: does your hand beat their range? '
            f'{"Bet for protection if you have top pair or better." if strategy == "bet_for_protection" else "Check/call marginal hands." if strategy == "check_call_induce" else "Check/fold marginal or weak hands."}'
        )
    elif hero_has_draw and draw_completed:
        tips.append(
            f'YOU HIT THE DRAW! {draw_type} completed. '
            f'Equity now {hero_equity_if_hits:.0%}. '
            f'{"IP: Lead bet for value, size up (large or overbet)." if hero_position == "ip" else "OOP: Donk lead or check-raise if villain likely to bet."} '
            f'Villain stackoff freq: {villain_stackoff_freq:.0%} -- '
            f'{"build pot fast." if villain_stackoff_freq >= 0.50 else "may need to value-bet smaller (villain tight)."}'
        )

    return DrawCompletionResult(
        draw_type=draw_type,
        street=street,
        draw_completed=draw_completed,
        outs=outs,
        turn_prob=turn_prob,
        flop_to_river_prob=ftr_prob,
        villain_range_weight=villain_wt,
        pfr_range_weight=pfr_wt,
        range_advantage_shift=adv_shift,
        hero_has_draw=hero_has_draw,
        implied_odds_bonus_bb=implied_bonus,
        strategy=strategy,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bca_one_liner(r: DrawCompletionResult) -> str:
    hit_label = 'HIT' if r.draw_completed else 'PENDING'
    return (
        f'[BCA {r.draw_type}|{r.street}|{hit_label}] '
        f'p={r.turn_prob:.1%} | '
        f'adv_shift={r.range_advantage_shift:+.2f} | {r.strategy}'
    )
