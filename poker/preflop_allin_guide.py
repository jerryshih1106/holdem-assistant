"""
Preflop All-In Guide (preflop_allin_guide.py)

Analyzes when to commit all chips preflop for non-short stacks.
This covers the 3-bet/4-bet/5-bet shove situations common in modern poker,
NOT the push/fold (short-stack) scenario covered by pushfold.py.

PREFLOP ALL-IN THEORY (for 50-200BB stacks):
  Preflop commitments occur in these spots:
  1. 3-bet shove: 3-bet all-in vs an open (typically 15-30BB effective)
  2. 4-bet/5-bet: calling or shoving a 4-bet
  3. Set-up hands: JJ vs 4-bet from UTG
  4. Domination avoidance: KQ vs 3-bet (dominated by AK/AQ)

  KEY RANGES:
    Snap call 5-bet: AA, KK
    Usually call 4-bet: QQ, JJ (marginally), AKs, AKo
    Usually fold 4-bet: QQ vs UTG, AQ, 88-TT vs 4-bet
    3-bet shove hands: depends on stack depth

  STACK DEPTH ANALYSIS:
    20-35BB: 3-bet shove with JJ+/AK; call off with TT/AQs
    35-60BB: 4-bet to ~22BB; 5-bet shove only AA/KK
    60-100BB: 4-bet to ~24BB; only AA/KK snap shove
    100-200BB: deep stack play; GTO 4-bet/fold with more hands

  MATH BEHIND 4-BET DECISION (example: 100BB):
    Open: 2.5BB; 3-bet: 7.5BB; 4-bet: 22BB; shove: 100BB
    If you 4-bet to 22BB and face a 5-bet shove:
      Need 32%+ equity to call (based on pot odds vs committed stack)
    QQ has ~45% vs AA/KK range if villain only 5-bets those
    QQ has ~37% vs {AA, KK, AK} range
    QQ folds to 5-bet vs UTG tight 4-bettor (villain only has AA/KK)

  DOMINATION TRAPS:
    AK vs UTG 4-bet: only 34% vs AA/KK; fold is often correct
    QQ vs UTG 4-bet: villain range {AA,KK} = QQ is 45%; call
    AQo vs 3-bet: dominated by AK; fold or call depending on position

DISTINCT FROM:
  pushfold.py:         Short-stack (<20BB) push/fold ranges
  facing_4bet.py:      Facing 4-bets specifically
  fourbet_advisor.py:  When to 4-bet
  fourbet_sizing.py:   4-bet sizing
  THIS MODULE:         PREFLOP ALL-IN decisions; 3-bet shove,
                       4-bet call/fold; domination analysis;
                       stack depth thresholds.

Usage:
    from poker.preflop_allin_guide import analyze_preflop_allin, PreFlopAllIn, pfag_one_liner

    result = analyze_preflop_allin(
        hero_hand='QQ',
        hero_position='btn',
        villain_action='four_bet',
        villain_position='utg',
        villain_range_width='tight',
        effective_stack_bb=100.0,
        three_bet_size_bb=22.0,
        current_pot_bb=25.0,
    )
    print(pfag_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Equity lookup vs different villain 4-bet ranges
EQUITY_VS_RANGE = {
    # (hand, range_type) -> equity
    ('AA', 'tight'):   0.82,   # AA vs {KK}
    ('KK', 'tight'):   0.30,   # KK vs {AA}
    ('QQ', 'tight'):   0.45,   # QQ vs {AA, KK}
    ('JJ', 'tight'):   0.37,   # JJ vs {AA, KK, QQ}
    ('TT', 'tight'):   0.32,
    ('AKs', 'tight'):  0.34,   # AK vs {AA, KK}
    ('AKo', 'tight'):  0.33,
    ('AQs', 'tight'):  0.27,
    ('AQo', 'tight'):  0.26,

    ('AA', 'medium'):  0.79,
    ('KK', 'medium'):  0.55,   # KK vs {AA, QQ+, AK}
    ('QQ', 'medium'):  0.48,   # QQ vs {KK+, AK}
    ('JJ', 'medium'):  0.42,
    ('TT', 'medium'):  0.38,
    ('AKs', 'medium'): 0.45,
    ('AKo', 'medium'): 0.44,
    ('AQs', 'medium'): 0.36,
    ('AQo', 'medium'): 0.35,

    ('AA', 'wide'):    0.75,
    ('KK', 'wide'):    0.62,
    ('QQ', 'wide'):    0.55,
    ('JJ', 'wide'):    0.50,
    ('TT', 'wide'):    0.46,
    ('AKs', 'wide'):   0.52,
    ('AKo', 'wide'):   0.50,
    ('AQs', 'wide'):   0.44,
    ('AQo', 'wide'):   0.42,
}

# Default equity when not in table
DEFAULT_EQUITY = {'tight': 0.35, 'medium': 0.42, 'wide': 0.48}

# Minimum equity to call a shove (based on pot odds)
def _min_equity_to_call_shove(effective_stack_bb: float, current_pot_bb: float) -> float:
    """Break-even equity to call all-in."""
    call_amount = effective_stack_bb - (current_pot_bb - effective_stack_bb) / 2
    call_amount = max(1.0, effective_stack_bb - current_pot_bb / 2)
    total = current_pot_bb + call_amount
    return round(call_amount / total, 3)


def _equity_vs_villain_range(hero_hand: str, range_type: str) -> float:
    return EQUITY_VS_RANGE.get((hero_hand, range_type), DEFAULT_EQUITY.get(range_type, 0.40))


def _allin_response(
    hero_hand: str,
    villain_action: str,
    villain_range_width: str,
    effective_stack_bb: float,
    current_pot_bb: float,
) -> str:
    """Determine call/fold for facing 4-bet or 5-bet."""
    hero_eq = _equity_vs_villain_range(hero_hand, villain_range_width)
    min_eq = _min_equity_to_call_shove(effective_stack_bb, current_pot_bb)

    if hero_hand in ('AA', 'KK'):
        return 'call_shove'   # always call

    if hero_eq >= min_eq + 0.05:
        return 'call_shove'
    elif hero_eq >= min_eq:
        return 'call_marginal'
    else:
        return 'fold'


def _three_bet_shove_threshold(stack_bb: float) -> str:
    """Minimum hand to 3-bet shove given stack depth."""
    if stack_bb <= 20:
        return 'JJ+/AK+'
    elif stack_bb <= 35:
        return 'QQ+/AK'
    elif stack_bb <= 50:
        return 'KK+/AKs'
    else:
        return 'AA/KK (only)'


def _four_bet_response(
    hero_hand: str,
    villain_action: str,
    villain_range_width: str,
    effective_stack_bb: float,
    current_pot_bb: float,
    villain_position: str,
) -> str:
    """Full 4-bet/5-bet response decision."""
    if villain_action == 'three_bet':
        # Hero is facing a 3-bet; should hero 4-bet, call, or fold?
        if hero_hand in ('AA', 'KK'):
            return '4bet_value'
        if hero_hand in ('QQ', 'JJ', 'AKs', 'AKo'):
            return '4bet_or_call'
        if hero_hand in ('TT', '99', 'AQs', 'AQo', 'AJs'):
            return 'call_or_fold'
        return 'fold'
    elif villain_action in ('four_bet', 'five_bet'):
        return _allin_response(hero_hand, villain_action, villain_range_width,
                               effective_stack_bb, current_pot_bb)
    return 'fold'


@dataclass
class PreFlopAllIn:
    # Inputs
    hero_hand: str
    hero_position: str
    villain_action: str
    villain_position: str
    villain_range_width: str
    effective_stack_bb: float
    three_bet_size_bb: float
    current_pot_bb: float

    # Analysis
    hero_equity: float
    min_equity_to_call: float
    response: str             # 'call_shove' / 'fold' / '4bet_value' / 'call_marginal' etc.
    three_bet_shove_threshold: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_preflop_allin(
    hero_hand: str = 'QQ',
    hero_position: str = 'btn',
    villain_action: str = 'four_bet',
    villain_position: str = 'utg',
    villain_range_width: str = 'tight',
    effective_stack_bb: float = 100.0,
    three_bet_size_bb: float = 22.0,
    current_pot_bb: float = 25.0,
) -> PreFlopAllIn:
    """
    Analyze preflop all-in decision.

    Args:
        hero_hand:            Hero's hand (e.g. 'QQ', 'AKo')
        hero_position:        Hero's position
        villain_action:       'three_bet' / 'four_bet' / 'five_bet'
        villain_position:     Villain's position
        villain_range_width:  'tight' / 'medium' / 'wide'
        effective_stack_bb:   Effective stack in BB
        three_bet_size_bb:    Size of the 3-bet (or 4-bet facing us)
        current_pot_bb:       Current pot before hero acts

    Returns:
        PreFlopAllIn
    """
    hero_eq = _equity_vs_villain_range(hero_hand, villain_range_width)
    min_eq = _min_equity_to_call_shove(effective_stack_bb, current_pot_bb)
    response = _four_bet_response(hero_hand, villain_action, villain_range_width,
                                   effective_stack_bb, current_pot_bb, villain_position)
    shove_thresh = _three_bet_shove_threshold(effective_stack_bb)

    verdict = (
        f'[PFAG {hero_hand}|{hero_position}|{villain_position}_{villain_action}] '
        f'{response.upper()} | '
        f'eq={hero_eq:.0%} min={min_eq:.0%} range={villain_range_width}'
    )

    reasoning = (
        f'Preflop all-in: {hero_hand} at {hero_position} vs {villain_position} {villain_action}. '
        f'Villain range width: {villain_range_width}. '
        f'Hero equity vs range: {hero_eq:.0%}. '
        f'Min equity to call shove: {min_eq:.0%}. '
        f'Stack: {effective_stack_bb:.0f}BB. '
        f'Response: {response}.'
    )

    tips = []

    tips.append(
        f'EQUITY vs {villain_range_width.upper()} {villain_position.upper()} {villain_action.replace("_"," ")}: '
        f'{hero_hand} = {hero_eq:.0%}. '
        f'Min equity to call: {min_eq:.0%} (pot odds = call / pot+call). '
        f'{"CALL: equity sufficient." if hero_eq >= min_eq else "FOLD: equity insufficient -- dominated."}'
    )

    if response in ('call_shove', 'call_marginal'):
        tips.append(
            f'CALL {"(marginal)" if response == "call_marginal" else "(clear)"}: '
            f'{hero_hand} has {hero_eq:.0%} equity vs {villain_range_width} range. '
            f'{"Marginal: consider villain tells and position." if response == "call_marginal" else "Clear call: equity comfortably beats pot odds."}'
        )
    elif 'fold' in response:
        tips.append(
            f'FOLD {hero_hand}: Dominated by {villain_position} {villain_range_width} range. '
            f'Equity {hero_eq:.0%} < required {min_eq:.0%}. '
            f'Even {hero_hand} is not strong enough here. '
            f'Exception: if you read villain as bluffing, adjust range to "wide" first.'
        )
    elif '4bet' in response:
        four_bet_size = three_bet_size_bb * 2.8
        tips.append(
            f'4-BET to {four_bet_size:.1f}BB (2.8x the 3-bet of {three_bet_size_bb:.1f}BB). '
            f'If villain 5-bets: snap call with {hero_hand} (equity = {hero_eq:.0%}). '
            f'Commitment threshold: {shove_thresh}.'
        )

    tips.append(
        f'STACK DEPTH GUIDE ({effective_stack_bb:.0f}BB): '
        f'3-bet shove threshold: {shove_thresh}. '
        f'At {effective_stack_bb:.0f}BB: {"3-bet/shove freely" if effective_stack_bb <= 30 else "4-bet then call off with AA/KK only" if effective_stack_bb >= 80 else "standard 4-bet/call off QQ+/AK"}.'
    )

    return PreFlopAllIn(
        hero_hand=hero_hand,
        hero_position=hero_position,
        villain_action=villain_action,
        villain_position=villain_position,
        villain_range_width=villain_range_width,
        effective_stack_bb=effective_stack_bb,
        three_bet_size_bb=three_bet_size_bb,
        current_pot_bb=current_pot_bb,
        hero_equity=hero_eq,
        min_equity_to_call=min_eq,
        response=response,
        three_bet_shove_threshold=shove_thresh,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pfag_one_liner(r: PreFlopAllIn) -> str:
    return (
        f'[PFAG {r.hero_hand}|{r.hero_position}] '
        f'{r.response.upper()} vs {r.villain_action} | '
        f'eq={r.hero_equity:.0%} min={r.min_equity_to_call:.0%}'
    )
