"""
Cold 4-Bet Advisor (cold_4bet_advisor.py)

A "cold 4-bet" occurs when a player who did NOT open the pot re-raises after:
  1. Someone opens (raise)
  2. Another player 3-bets

The "cold" player is not the original opener, so their 4-bet range has very
different properties from a standard 4-bet by the original opener.

KEY DIFFERENCES vs Standard 4-Bet:
  Standard 4-bet (opener responds to 3-bet):
    - Opener has invested chips; pot odds favor calling/4-betting
    - Range includes more medium-strong hands (TT, JJ, AQ)
    - Stack-off threshold is lower (already committed)

  Cold 4-bet (uninvested player):
    - Player paid 0 chips into pot; facing 2 streets of aggression
    - Range MUST be very strong (AA, KK) or precise bluffs (Axs blockers)
    - Weaker hands like JJ, AQo should fold cold (not call, not 4-bet)
    - Cold call of a 3-bet is also risky without position — cold 4-bet avoids that
    - Huge pot-odds context: if cold 4-betting, must be prepared to call 5-bet

WHY cold 4-bet (rather than cold call 3-bet):
  Cold calling a 3-bet creates an inflated pot without position in many cases.
  Against most opponents: cold 4-bet with AA/KK builds more value AND folds out
  the opener's medium-strength 4-bet calling range (JJ/QQ/AK).

Cold 4-bet range construction:
  Value hands (always 4-bet):
    AA, KK — stack off vs any 5-bet
    AKs — 4-bet/call vs most villains
    QQ — 4-bet/fold vs tight 3-bettor; 4-bet/call vs loose

  Bluff hands (4-bet as blocker bluff):
    A5s, A4s, A3s, A2s (Ace blocks AA; suited for equity)
    KQs (blocks KK + AK)
    Suited connectors (TT can be bluff 4-bet to fold out JJ/QQ)

  Hands to fold cold (never cold 4-bet or cold call):
    JJ (vs UTG open + UTG+1 3-bet: dominated range; call if position)
    AQo (no blocker benefit; flip vs 4-bet caller range)
    AJs, KQo

SIZING:
  Cold 4-bet sizing: 2.2x-2.5x the 3-bet
  vs OOP 3-bet: 2.5-2.7x (bigger to punish; they have fewer implied odds)
  vs IP 3-bet: 2.2-2.4x (maintain pot control; they have better position)

  After cold 4-bet: pot is massive; usually playing for stacks
  Stack-off threshold: 40-50 BB effective stacks is standard commit zone

POSITION CONSIDERATIONS:
  BTN cold 4-bet: Strong position; can 4-bet wider (has position post-flop)
  SB cold 4-bet: Weaker position; need better hands
  CO cold 4-bet: Medium position; standard range
  UTG cold 4-bet: Very strong range only (no position; no implied odds)

Usage:
    from poker.cold_4bet_advisor import advise_cold_4bet, Cold4BetAdvice
    from poker.cold_4bet_advisor import cold_4bet_one_liner

    result = advise_cold_4bet(
        hero_hand_class='AA',
        hero_pos='BTN',
        opener_pos='UTG',
        threebetter_pos='CO',
        open_raise_bb=3.0,
        threbet_bb=9.0,
        hero_stack_bb=100.0,
        villain_3bet_pct=0.07,
        villain_3bet_fold_to_4bet=0.55,
        villain_vpip=0.25,
        board_type='preflop',
    )
    print(result.action, result.fourbet_to_bb)
"""

from dataclasses import dataclass, field
from typing import List


_HAND_STRENGTH = {
    'AA': 10, 'KK': 9, 'QQ': 8, 'JJ': 7, 'TT': 6,
    '99': 5, '88': 4, 'AKs': 9, 'AKo': 8, 'AQs': 7, 'AQo': 6,
    'AJs': 6, 'AJo': 5, 'KQs': 6, 'KQo': 5,
    'A5s': 3, 'A4s': 3, 'A3s': 3, 'A2s': 3,  # Ax suited: blocker 4-bets
    'KJs': 4, 'QJs': 4, 'JTs': 3,
    # Generic classes
    'premium': 10, 'strong_value': 8, 'value': 7, 'medium_value': 6,
    'marginal': 4, 'blocker': 3, 'air': 0,
}


def _hand_strength(hand_class: str) -> int:
    return _HAND_STRENGTH.get(hand_class, 5)


def _has_ace_blocker(hand_class: str) -> bool:
    return hand_class in ('AA', 'AKs', 'AKo', 'AQs', 'AQo', 'AJs', 'AJo',
                          'A5s', 'A4s', 'A3s', 'A2s')


def _has_king_blocker(hand_class: str) -> bool:
    return hand_class in ('KK', 'AKs', 'AKo', 'KQs', 'KQo', 'KJs')


def _position_rank(pos: str) -> int:
    """Higher rank = later position = more post-flop advantage."""
    return {'UTG': 0, 'UTG+1': 1, 'MP': 2, 'HJ': 3, 'CO': 4, 'BTN': 5, 'SB': 1, 'BB': 2}.get(pos, 3)


def _equity_vs_5bet_call(hand_class: str) -> float:
    """Hero's equity when calling a 5-bet all-in. Assumes villain has QQ-AA,AKs,AKo."""
    _eq = {
        'AA': 0.85, 'KK': 0.71, 'QQ': 0.56, 'JJ': 0.49, 'TT': 0.46,
        'AKs': 0.47, 'AKo': 0.45, 'AQs': 0.40, 'A5s': 0.34,
        'A4s': 0.33, 'A3s': 0.33, 'A2s': 0.32,
        'premium': 0.80, 'strong_value': 0.60, 'value': 0.52, 'medium_value': 0.46,
        'blocker': 0.33, 'marginal': 0.40, 'air': 0.30,
        'KQs': 0.38, 'KQo': 0.36,
    }
    return _eq.get(hand_class, 0.45)


def _can_stack_off(
    hand_class: str,
    hero_stack_bb: float,
    threbet_bb: float,
) -> bool:
    """Can hero stack off after 4-bet if villain 5-bets?"""
    strength = _hand_strength(hand_class)
    if strength >= 9:  # AA, KK
        return True
    if strength >= 8 and hero_stack_bb <= 50:  # QQ, AKs: call off vs short stacks
        return True
    if strength >= 7 and hero_stack_bb <= 35:  # AKo, JJ: only at shallow stacks
        return True
    return False


def _fourbet_range_type(
    hand_strength: int,
    has_ace_blocker: bool,
    has_king_blocker: bool,
    hero_pos: str,
    villain_3bet_pct: float,
) -> str:
    """Classify the 4-bet as value, semi-bluff, or pure bluff."""
    pos_rank = _position_rank(hero_pos)

    if hand_strength >= 9:
        return 'value_stack_off'   # AA/KK: 4-bet/call vs anything
    if hand_strength == 8:
        return 'value_stack_off' if villain_3bet_pct <= 0.10 else 'value_fold_to_5bet'
    if hand_strength == 7 and pos_rank >= 4:
        return 'value_fold_to_5bet'   # QQ/AQs IP: 4-bet but fold to 5-bet vs nits
    if has_ace_blocker and hand_strength <= 4:
        return 'blocker_bluff'     # Axs: semi-bluff with ace blocker
    if has_king_blocker and hand_strength <= 5:
        return 'blocker_bluff'
    return 'dont_4bet'


def _fourbet_sizing(
    threbet_bb: float,
    hero_pos: str,
    threebetter_pos: str,
) -> float:
    """Optimal cold 4-bet sizing."""
    hero_rank = _position_rank(hero_pos)
    vill_rank = _position_rank(threebetter_pos)

    if hero_rank > vill_rank:
        mult = 2.3   # Hero IP vs OOP 3-bettor: standard
    else:
        mult = 2.5   # Hero OOP: slightly bigger to charge them

    return round(threbet_bb * mult, 1)


def _action(
    range_type: str,
    villain_3bet_fold_to_4bet: float,
    hand_strength: int,
    hero_stack_bb: float,
    threbet_bb: float,
) -> tuple:
    """
    Returns (action, reasoning).
    action: '4bet_value', '4bet_bluff', 'cold_call', 'fold'
    """
    # Clear value: 4-bet for value, prepared to stack off
    if range_type == 'value_stack_off':
        return (
            '4bet_value',
            f'Value 4-bet: hand strength={hand_strength}. '
            f'Stack off if 5-bet. '
            f'4-bet/call is optimal — villain 3-bet folds to 4-bet only '
            f'{villain_3bet_fold_to_4bet:.0%} of time, but all 5-bets favor hero.'
        )

    # Medium value: 4-bet but fold to 5-bet
    if range_type == 'value_fold_to_5bet':
        fold_to_4bet = villain_3bet_fold_to_4bet >= 0.55
        if fold_to_4bet:
            return (
                '4bet_value',
                f'4-bet/fold vs 5-bet: villain folds to 4-bets {villain_3bet_fold_to_4bet:.0%}. '
                f'Profitable even as pure bluff. Hand (rank={hand_strength}) is value vs fold equity.'
            )
        return (
            'cold_call',
            f'Cold call: villain only folds to 4-bet {villain_3bet_fold_to_4bet:.0%} of time. '
            f'Not enough fold equity to 4-bet/fold. '
            f'Call and play post-flop with position advantage.'
        )

    # Blocker bluff: 4-bet as pure fold equity play
    if range_type == 'blocker_bluff':
        if villain_3bet_fold_to_4bet >= 0.55:
            return (
                '4bet_bluff',
                f'Blocker 4-bet bluff: fold equity={villain_3bet_fold_to_4bet:.0%}. '
                f'Ace/King blocker reduces villain\'s AA/KK combos. '
                f'Fold to any 5-bet immediately.'
            )
        return (
            'fold',
            f'Fold blocker bluff: villain only folds to 4-bet {villain_3bet_fold_to_4bet:.0%}. '
            f'Not worth bluffing — cold 4-bet bluff becomes -EV without fold equity.'
        )

    # Default: fold (don't cold 4-bet)
    return (
        'fold',
        f'Fold cold: hand rank={hand_strength} insufficient for cold 4-bet range. '
        f'Cold 4-betting JJ/AQo from early position vs UTG open + 3-bet is -EV. '
        f'Fold and wait for better spot.'
    )


def _ev_of_4bet_bluff(
    pot_before_4bet: float,
    fourbet_to_bb: float,
    villain_fold_pct: float,
    eq_if_called: float,
    total_pot_if_called: float,
) -> float:
    """EV of a bluff 4-bet."""
    ev_fold = villain_fold_pct * pot_before_4bet
    ev_call = (1 - villain_fold_pct) * (eq_if_called * total_pot_if_called - fourbet_to_bb)
    return round(ev_fold + ev_call, 2)


@dataclass
class Cold4BetAdvice:
    """Advice for cold 4-betting."""
    hero_hand_class: str
    hero_pos: str
    opener_pos: str
    threebetter_pos: str
    open_raise_bb: float
    threbet_bb: float
    hero_stack_bb: float
    villain_3bet_pct: float
    villain_3bet_fold_to_4bet: float
    villain_vpip: float

    # Analysis
    hand_strength: int
    has_ace_blocker: bool
    has_king_blocker: bool
    range_type: str          # 'value_stack_off', 'value_fold_to_5bet', 'blocker_bluff', 'dont_4bet'
    equity_vs_5bet: float
    can_stack_off: bool

    # Decision
    action: str              # '4bet_value', '4bet_bluff', 'cold_call', 'fold'
    fourbet_to_bb: float
    pot_after_4bet: float    # total pot if villain calls 4-bet (no 5-bet)
    ev_bluff_4bet: float     # EV of bluff 4-bet (if applicable)

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_cold_4bet(
    hero_hand_class: str = 'AA',
    hero_pos: str = 'BTN',
    opener_pos: str = 'UTG',
    threebetter_pos: str = 'CO',
    open_raise_bb: float = 3.0,
    threbet_bb: float = 9.0,
    hero_stack_bb: float = 100.0,
    villain_3bet_pct: float = 0.07,
    villain_3bet_fold_to_4bet: float = 0.55,
    villain_vpip: float = 0.25,
    board_type: str = 'preflop',
) -> Cold4BetAdvice:
    """
    Advise hero on whether and how to cold 4-bet.

    Args:
        hero_hand_class:          Hero's hand (e.g., 'AA', 'KK', 'A5s', 'JJ')
        hero_pos:                 Hero's position ('UTG','MP','CO','BTN','SB','BB')
        opener_pos:               Original raiser's position
        threebetter_pos:          3-bettor's position
        open_raise_bb:            Opener's raise size in BB
        threbet_bb:               3-bettor's 3-bet size in BB
        hero_stack_bb:            Hero's effective stack in BB
        villain_3bet_pct:         3-bettor's 3-bet percentage (0-1)
        villain_3bet_fold_to_4bet: Fraction of 3-bets that fold to 4-bets (HUD: Fold to 4-bet)
        villain_vpip:             3-bettor's VPIP
        board_type:               'preflop' for preflop decisions

    Returns:
        Cold4BetAdvice
    """
    strength = _hand_strength(hero_hand_class)
    ace_blocker = _has_ace_blocker(hero_hand_class)
    king_blocker = _has_king_blocker(hero_hand_class)
    range_type = _fourbet_range_type(
        strength, ace_blocker, king_blocker, hero_pos, villain_3bet_pct
    )
    stack_off = _can_stack_off(hero_hand_class, hero_stack_bb, threbet_bb)
    eq_vs_5bet = _equity_vs_5bet_call(hero_hand_class)
    fourbet_size = _fourbet_sizing(threbet_bb, hero_pos, threebetter_pos)
    action, reasoning = _action(
        range_type, villain_3bet_fold_to_4bet, strength, hero_stack_bb, threbet_bb
    )

    # EV estimate for bluff 4-bet
    pot_before_4bet = 1.5 + open_raise_bb + threbet_bb  # SB + BB + open + 3-bet
    total_pot_if_called = pot_before_4bet + fourbet_size * 2  # approx
    ev_bluff = _ev_of_4bet_bluff(
        pot_before_4bet,
        fourbet_size,
        villain_3bet_fold_to_4bet,
        eq_vs_5bet,
        total_pot_if_called,
    )
    pot_after = round(pot_before_4bet + fourbet_size + threbet_bb, 1)

    # Tips
    tips = []
    tips.append(
        f'Cold 4-bet range: AA/KK (value/stack off) + Axs/KQs (blocker bluffs). '
        f'Hands like JJ, AQo should FOLD cold vs UTG open + 3-bet — they are dominated. '
        f'Do not cold call wide 3-bets without position.'
    )
    if range_type == 'value_stack_off':
        tips.append(
            f'{hero_hand_class} (rank={strength}): cold 4-bet {fourbet_size:.1f}BB. '
            f'Stack off vs 5-bet (equity={eq_vs_5bet:.0%}). '
            f'vs villain who 3-bets {villain_3bet_pct:.0%} of time: range is AK/QQ-AA = you dominate.'
        )
    if range_type == 'blocker_bluff':
        tips.append(
            f'Blocker 4-bet: {hero_hand_class} blocks AA{"+" if ace_blocker else ""}'
            f'{"KK" if king_blocker else ""}. '
            f'Villain folds to 4-bet {villain_3bet_fold_to_4bet:.0%}. '
            f'EV of bluff = {ev_bluff:.1f}BB. Fold immediately to 5-bet.'
        )
    if action == 'cold_call':
        tips.append(
            f'Cold call {threbet_bb:.1f}BB: villain 3-bet fold rate {villain_3bet_fold_to_4bet:.0%} too low to bluff. '
            f'Call and use position advantage post-flop. '
            f'Look for spots to float or bluff-raise on low boards.'
        )
    if villain_3bet_pct <= 0.05:
        tips.append(
            f'Nit 3-bettor (3-bet%={villain_3bet_pct:.0%}): range is AA/KK/AK almost exclusively. '
            f'Reduce cold 4-bet bluff frequency dramatically. '
            f'Only cold 4-bet for value (AA/KK); fold everything else.'
        )
    elif villain_3bet_pct >= 0.12:
        tips.append(
            f'Loose 3-bettor ({villain_3bet_pct:.0%}): 3-bet range includes many bluffs. '
            f'Cold 4-bet more aggressively (add QQ, AKo to value range). '
            f'Blocker bluffs become more profitable as well.'
        )
    if hero_stack_bb <= 40 and action in ('4bet_value', '4bet_bluff'):
        tips.append(
            f'Shallow stack ({hero_stack_bb:.0f}BB): cold 4-bet commits ~{fourbet_size/hero_stack_bb:.0%} of stack. '
            f'At this depth, any 4-bet = implicit stack-off commitment. '
            f'Only 4-bet hands you are happy stacking off with.'
        )
    if not tips:
        tips.append(
            f'{action.upper()}: {hero_hand_class} (rank={strength}) from {hero_pos}. '
            f'4-bet to {fourbet_size:.1f}BB if value. Fold if below threshold. '
            f'Cold 4-bet range is narrow: AA/KK/AKs + Axs blockers only.'
        )

    return Cold4BetAdvice(
        hero_hand_class=hero_hand_class,
        hero_pos=hero_pos,
        opener_pos=opener_pos,
        threebetter_pos=threebetter_pos,
        open_raise_bb=round(open_raise_bb, 1),
        threbet_bb=round(threbet_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        villain_3bet_pct=round(villain_3bet_pct, 4),
        villain_3bet_fold_to_4bet=round(villain_3bet_fold_to_4bet, 3),
        villain_vpip=round(villain_vpip, 3),
        hand_strength=strength,
        has_ace_blocker=ace_blocker,
        has_king_blocker=king_blocker,
        range_type=range_type,
        equity_vs_5bet=round(eq_vs_5bet, 3),
        can_stack_off=stack_off,
        action=action,
        fourbet_to_bb=fourbet_size,
        pot_after_4bet=pot_after,
        ev_bluff_4bet=ev_bluff,
        reasoning=reasoning,
        tips=tips,
    )


def cold_4bet_one_liner(result: Cold4BetAdvice) -> str:
    return (
        f'[C4B {result.hero_hand_class}|{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'4b_to={result.fourbet_to_bb:.1f}BB '
        f'range={result.range_type} | '
        f'fold_to_4b={result.villain_3bet_fold_to_4bet:.0%} '
        f'ev_bluff={result.ev_bluff_4bet:.1f}BB'
    )
