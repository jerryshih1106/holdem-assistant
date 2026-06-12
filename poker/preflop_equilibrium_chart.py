"""
Preflop Equilibrium Chart (preflop_equilibrium_chart.py)

Provides GTO-based preflop equilibrium advice: open-raising ranges,
3-bet ranges, 4-bet ranges, and calling ranges by position and stack depth.

PREFLOP GTO CONCEPTS:
  At equilibrium, each player's range is unexploitable -- villain cannot
  profitably deviate by folding or calling more.

  KEY RANGES BY POSITION (100BB deep):
  Open-raise:
    UTG:  ~15% of hands (pairs 44+, ATo+, KQo, AJs+, KQs, suited connectors)
    CO:   ~25% of hands (add lower suited connectors, weaker Ax)
    BTN:  ~45% of hands (much wider; add low suited broadways, more pairs)
    SB:   ~35% vs BB (extra incentive due to position disadvantage)

  3-Bet vs open:
    Value:  TT+, AK, AQ (always 3-bet)
    Semi-bluff: A5s-A2s, KQs, 65s (blockers + playability)

  4-Bet vs 3-bet:
    Value: QQ+, AK
    Bluff: A5s, KQs (Ace/King blockers to villain's nutted range)

  Calling ranges (flat):
    IP: JJ-77, AK-AQ, suited broadway, suited connectors
    OOP: fewer; more 3-bet/fold (position disadvantage)

STACK DEPTH ADJUSTMENTS:
  Short stack (< 30BB): Push/fold; 3-bet = jam
  Medium (30-50BB):     Larger 3-bets; less flatting
  Deep (>150BB):        More speculative calls; set-mining more profitable

DISTINCT FROM:
  preflop_hand_bucketing.py:    Classifies individual hands into action buckets
  preflop_equity_advisor.py:    Equity calculations preflop
  THIS MODULE:                  Full equilibrium charts; range-level GTO advice;
                                frequency recommendations per position matchup

Usage:
    from poker.preflop_equilibrium_chart import get_preflop_equilibrium, PreflopEquilibriumResult, pec_one_liner

    result = get_preflop_equilibrium(
        hero_position='co',
        action_facing='open',
        villain_position='utg',
        hero_hand='AJs',
        stack_bb=100.0,
        villain_vpip=0.25,
        villain_3bet=0.07,
    )
    print(pec_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# GTO open-raise range width by position (% of hands)
GTO_OPEN_RANGE_PCT = {
    'utg':  0.15,
    'utg1': 0.17,
    'mp':   0.20,
    'lj':   0.22,
    'hj':   0.25,
    'co':   0.28,
    'btn':  0.45,
    'sb':   0.35,
}

# 3-bet frequency vs open by position
GTO_3BET_FREQ = {
    'btn_vs_co':   0.14,
    'btn_vs_hj':   0.12,
    'bb_vs_btn':   0.16,
    'bb_vs_co':    0.14,
    'bb_vs_utg':   0.09,
    'co_vs_utg':   0.08,
    'co_vs_mp':    0.09,
    'sb_vs_btn':   0.18,   # SB has position disadvantage → 3-bet more, call less
    'default':     0.10,
}

# 4-bet frequency vs 3-bet
GTO_4BET_FREQ = {
    'default': 0.20,   # 4-bet about 20% of hands 3-bet into
}

# Hand strength categories for preflop decisions
HAND_CATEGORY = {
    # Premium pairs
    'AA': 'premium', 'KK': 'premium', 'QQ': 'premium',
    # Strong pairs
    'JJ': 'strong_pair', 'TT': 'strong_pair', '99': 'strong_pair',
    # Medium pairs
    '88': 'medium_pair', '77': 'medium_pair', '66': 'medium_pair',
    # Small pairs
    '55': 'small_pair', '44': 'small_pair', '33': 'small_pair', '22': 'small_pair',
    # Premium broadways
    'AKs': 'premium_broadway', 'AKo': 'premium_broadway',
    'AQs': 'strong_broadway', 'AJs': 'strong_broadway', 'ATs': 'strong_broadway',
    'AQo': 'strong_broadway',
    # Speculative suited Aces
    'A9s': 'suited_ace', 'A8s': 'suited_ace', 'A7s': 'suited_ace',
    'A6s': 'suited_ace', 'A5s': 'suited_ace_bluff', 'A4s': 'suited_ace_bluff',
    'A3s': 'suited_ace_bluff', 'A2s': 'suited_ace_bluff',
    # Offsuit aces
    'AJo': 'broadway_offsuit', 'ATo': 'broadway_offsuit',
    # King hands
    'KQs': 'premium_broadway', 'KJs': 'strong_broadway', 'KTs': 'strong_broadway',
    'KQo': 'broadway_offsuit', 'KJo': 'broadway_offsuit',
    # Suited connectors
    'JTs': 'suited_connector', 'T9s': 'suited_connector', '98s': 'suited_connector',
    '87s': 'suited_connector', '76s': 'suited_connector', '65s': 'suited_connector',
    '54s': 'suited_connector',
    # Suited one-gappers
    'J9s': 'suited_gapper', 'T8s': 'suited_gapper', '97s': 'suited_gapper',
    '86s': 'suited_gapper', '75s': 'suited_gapper',
}


def _hand_category(hand: str) -> str:
    return HAND_CATEGORY.get(hand, 'unknown')


def _stack_regime(stack_bb: float) -> str:
    if stack_bb < 25:
        return 'push_fold'
    elif stack_bb < 40:
        return 'short'
    elif stack_bb < 60:
        return 'medium_short'
    elif stack_bb <= 150:
        return 'standard'
    else:
        return 'deep'


def _get_3bet_freq(hero_position: str, villain_position: str) -> float:
    key = f'{hero_position.lower()}_vs_{villain_position.lower()}'
    return GTO_3BET_FREQ.get(key, GTO_3BET_FREQ['default'])


def _equilibrium_action(
    action_facing: str,
    hand: str,
    hero_position: str,
    villain_position: str,
    stack_regime: str,
    villain_3bet: float,
    villain_vpip: float,
) -> tuple:
    """(action: str, frequency: float, explanation: str)"""
    cat = _hand_category(hand)

    if action_facing == 'none':
        # First to act: open or fold
        open_pct = GTO_OPEN_RANGE_PCT.get(hero_position.lower(), 0.20)
        strong_cats = ('premium', 'strong_pair', 'premium_broadway', 'strong_broadway')
        spec_cats = ('medium_pair', 'small_pair', 'suited_connector', 'suited_ace_bluff', 'suited_ace')
        if cat in strong_cats:
            return 'open_raise', 1.0, f'{hand} ({cat}): always open from {hero_position}.'
        elif cat in spec_cats:
            if hero_position in ('btn', 'co', 'sb'):
                return 'open_raise', 0.85, f'{hand}: open from {hero_position} (top {open_pct:.0%} range).'
            else:
                return 'open_raise', 0.50, f'{hand}: open some from {hero_position}; part of range.'
        else:
            return 'fold', 0.0, f'{hand} ({cat}): below open range from {hero_position}.'

    if action_facing == 'open':
        # Facing an open: 3-bet, call, or fold
        three_bet_freq = _get_3bet_freq(hero_position, villain_position)

        if cat == 'premium':
            return '3bet_value', 1.0, f'{hand}: always 3-bet premium pairs for value.'
        elif cat in ('strong_pair', 'premium_broadway'):
            if stack_regime in ('push_fold', 'short'):
                return '3bet_jam', 1.0, f'{hand}: jam/3-bet short stack.'
            return '3bet_value', 0.85, f'{hand}: 3-bet for value. Mix with flat at {hero_position}.'
        elif cat == 'suited_ace_bluff':
            if villain_vpip <= 0.20:
                return '3bet_bluff', three_bet_freq, f'{hand}: 3-bet bluff vs tight player; good blockers (Ace).'
            else:
                return 'call', 0.65, f'{hand}: call or 3-bet bluff vs wider range.'
        elif cat in ('suited_connector', 'suited_gapper', 'medium_pair', 'small_pair'):
            # Good implied odds; flat in position
            if hero_position in ('btn', 'co'):
                return 'call', 0.75, f'{hand}: flat in position for implied odds.'
            else:
                return 'fold', 0.0, f'{hand}: fold out of position; poor implied odds OOP.'
        elif cat in ('strong_broadway', 'suited_ace'):
            if hero_position in ('btn', 'co', 'hj'):
                return 'call', 0.80, f'{hand}: flat in position; too good to fold, not strong enough to 3-bet all combos.'
            else:
                return '3bet_bluff', 0.40, f'{hand}: mix 3-bet and fold OOP.'
        else:
            return 'fold', 0.0, f'{hand} ({cat}): fold vs open; below defend range.'

    if action_facing == '3bet':
        # Facing a 3-bet: 4-bet, call, or fold
        if cat == 'premium':
            return '4bet_value', 1.0, f'{hand}: always 4-bet premium pairs.'
        elif cat == 'strong_pair' and hand in ('QQ', 'JJ'):
            if villain_3bet <= 0.05:
                return 'call', 0.50, f'{hand}: tight 3-bettor -- consider flat or 4-bet depending on position.'
            return '4bet_value', 0.70, f'{hand}: 4-bet for value or call; mix.'
        elif cat == 'premium_broadway' and hand == 'AKs':
            return '4bet_value', 0.85, f'AKs: 4-bet for value; equity too strong to flat.'
        elif cat == 'suited_ace_bluff' and hand in ('A5s', 'A4s'):
            return '4bet_bluff', 0.40, f'{hand}: 4-bet bluff; ace blocker reduces villain\'s AA/AK combos.'
        elif cat in ('strong_broadway', 'suited_connector') and villain_3bet <= 0.06:
            return 'fold', 0.0, f'{hand}: fold vs tight 3-bettor. Below 4-bet/call range.'
        elif cat in ('strong_broadway', 'suited_connector'):
            return 'call', 0.35, f'{hand}: marginal call vs aggressive 3-bettor; need position.'
        else:
            return 'fold', 0.0, f'{hand}: fold vs 3-bet; below continuing range.'

    return 'check', 0.0, 'No action decision needed.'


@dataclass
class PreflopEquilibriumResult:
    # Inputs
    hero_position: str
    action_facing: str
    villain_position: str
    hero_hand: str
    stack_bb: float
    villain_vpip: float
    villain_3bet: float

    # Analysis
    hand_category: str
    stack_regime: str
    open_range_pct: float         # GTO open range for hero's position
    three_bet_freq: float         # GTO 3-bet frequency for this spot

    # Recommendation
    action: str                   # 'open_raise'/'3bet_value'/'3bet_bluff'/'4bet_value'/'call'/'fold'
    action_frequency: float       # how often to take this action (0-1)
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def get_preflop_equilibrium(
    hero_position: str = 'co',
    action_facing: str = 'open',
    villain_position: str = 'utg',
    hero_hand: str = 'AJs',
    stack_bb: float = 100.0,
    villain_vpip: float = 0.25,
    villain_3bet: float = 0.07,
) -> PreflopEquilibriumResult:
    """
    Provide GTO preflop equilibrium advice for a given spot.

    Args:
        hero_position:   Hero's position ('utg'/'mp'/'co'/'btn'/'sb'/'bb')
        action_facing:   'none' (first in) / 'open' (facing raise) / '3bet' (facing 3-bet)
        villain_position: Opener's position (if applicable)
        hero_hand:       Hand in notation: 'AKs', 'QQ', 'T9s', etc.
        stack_bb:        Effective stack depth
        villain_vpip:    Villain's VPIP stat
        villain_3bet:    Villain's 3-bet frequency

    Returns:
        PreflopEquilibriumResult
    """
    cat = _hand_category(hero_hand)
    regime = _stack_regime(stack_bb)
    open_pct = GTO_OPEN_RANGE_PCT.get(hero_position.lower(), 0.20)
    three_bet_freq = _get_3bet_freq(hero_position, villain_position)

    action, freq, explanation = _equilibrium_action(
        action_facing, hero_hand, hero_position, villain_position,
        regime, villain_3bet, villain_vpip
    )

    reasoning = (
        f'Preflop equilibrium: {hero_hand} ({cat}) at {hero_position} facing {action_facing}. '
        f'Stack={stack_bb:.0f}BB ({regime}). '
        f'Villain={villain_position} VPIP={villain_vpip:.0%} 3bet={villain_3bet:.0%}. '
        f'Open range={open_pct:.0%}. GTO 3-bet freq={three_bet_freq:.0%}. '
        f'Action={action} freq={freq:.0%}.'
    )

    verdict = (
        f'[PEC {hero_hand}|{hero_position}|{action_facing}] '
        f'{action.upper()} ({freq:.0%}) | '
        f'cat={cat} stack={regime}'
    )

    tips = [explanation]

    tips.append(
        f'EQUILIBRIUM CONTEXT: From {hero_position.upper()}, GTO open range = {open_pct:.0%} of hands. '
        f'GTO 3-bet frequency in this spot = {three_bet_freq:.0%}. '
        f'Hand category: {cat.replace("_"," ")}. '
        f'Action frequency = {freq:.0%} (mix accordingly).'
    )

    if villain_vpip >= 0.35:
        tips.append(
            f'LOOSE VILLAIN (VPIP={villain_vpip:.0%}): Exploitative adjustment: '
            f'3-bet more for value (wider range calls down). '
            f'Remove low-equity bluffs; add value. '
            f'Reduce speculative calls (cannot fold out loose players).'
        )
    elif villain_vpip <= 0.15:
        tips.append(
            f'TIGHT VILLAIN (VPIP={villain_vpip:.0%}): Exploitative adjustment: '
            f'Fold marginal hands vs tight ranges. '
            f'3-bet/4-bet requires stronger hands. '
            f'Respect aggression -- tight players have it.'
        )

    if regime in ('push_fold', 'short'):
        tips.append(
            f'SHORT STACK ({stack_bb:.0f}BB, {regime}): Push/fold mode. '
            f'3-betting = jam. No post-flop play -- preflop all-in equity matters most. '
            f'Widen jam range; tighten call range.'
        )

    if villain_3bet >= 0.12:
        tips.append(
            f'AGGRESSIVE 3-BETTOR (3bet={villain_3bet:.0%}): '
            f'Villain 3-bets a wide range; some are bluffs. '
            f'4-bet more hands for value/bluff. '
            f'Calling 3-bets in position vs this villain is profitable with suited connectors/pairs.'
        )

    return PreflopEquilibriumResult(
        hero_position=hero_position,
        action_facing=action_facing,
        villain_position=villain_position,
        hero_hand=hero_hand,
        stack_bb=stack_bb,
        villain_vpip=villain_vpip,
        villain_3bet=villain_3bet,
        hand_category=cat,
        stack_regime=regime,
        open_range_pct=open_pct,
        three_bet_freq=three_bet_freq,
        action=action,
        action_frequency=freq,
        action_explanation=explanation,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pec_one_liner(r: PreflopEquilibriumResult) -> str:
    return (
        f'[PEC {r.hero_hand}|{r.hero_position}|{r.action_facing}] '
        f'{r.action.upper()} ({r.action_frequency:.0%}) | '
        f'cat={r.hand_category} stack={r.stack_regime}'
    )
