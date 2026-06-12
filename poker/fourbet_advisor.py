"""
4-bet Advisor (fourbet_advisor.py)

Analyzes when to 4-bet, call, or fold facing a 3-bet.
One of the highest-leverage decisions in NLHE — most players
either over-fold or call with dominated hands.

Key concepts:
  - Value 4-bet: QQ+, AK (always); JJ/AQs vs wide 3-bettors
  - 4-bet bluff: A2s-A5s, KQs (blocker + fold equity)
  - Call: JJ/TT/AQs vs tight 3-bettors OOP; more IP
  - Fold: off-suit broadways, weak suited connectors, pair < TT vs tight range

Usage:
    from poker.fourbet_advisor import analyze_fourbet, FourBetResult
    result = analyze_fourbet(
        hand='JJ',
        hero_pos='BTN',
        villain_pos='BB',
        villain_3bet_pct=0.08,
        three_bet_size_bb=12.0,
        stack_bb=100.0,
        in_position=True,
    )
    print(result.action, result.fourbet_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Hand classification ───────────────────────────────────────────────────────
# Tiers determine base 4-bet / call / fold preference

_VALUE_4BET_HANDS = {
    'AA', 'KK', 'QQ', 'AKs', 'AKo',
}

_VALUE_4BET_VS_WIDE = {
    'JJ', 'AQs',   # 4-bet vs > 8% 3-bet range
}

_BLUFF_4BET_HANDS = {
    'A5s', 'A4s', 'A3s', 'A2s',   # block AK/AA; thin call equity
    'KQs',                          # block KK; good blocker
}

_CALL_HANDS_IP = {
    'JJ', 'TT', '99', 'AQs', 'AQo', 'KQs', 'AJs', 'KJs',
}

_CALL_HANDS_OOP = {
    'JJ', 'TT', 'AQs',
}

# Position fold frequency to a 4-bet (from the 3-bettors perspective)
# Tighter 3-bet range (UTG) folds less to 4-bet; looser (BTN, SB) folds more
_VILLAIN_3BET_FOLD_TO_4BET: dict = {
    'UTG': 0.50,
    'HJ':  0.52,
    'CO':  0.55,
    'BTN': 0.58,
    'SB':  0.60,
    'BB':  0.55,
}


def _parse_hand(hand: str):
    """Return (rank1, rank2, suited) where rank1 >= rank2."""
    _RANK_ORDER = '23456789TJQKA'
    h = hand.strip()
    if len(h) == 3:
        r1, r2, suffix = h[0].upper(), h[1].upper(), h[2].lower()
        suited = (suffix == 's')
    elif len(h) == 2:
        r1, r2 = h[0].upper(), h[1].upper()
        suited = False
    else:
        r1, r2, suited = 'A', 'A', False

    r1_idx = _RANK_ORDER.index(r1) if r1 in _RANK_ORDER else 12
    r2_idx = _RANK_ORDER.index(r2) if r2 in _RANK_ORDER else 12
    return r1_idx, r2_idx, suited


def _hand_equity_vs_3bet_range(hand: str, villain_3bet_pct: float) -> float:
    """
    Approximate equity of hero's hand vs villain's 3-bet range.
    Villain range tightens as 3bet_pct decreases.
    """
    r1, r2, suited = _parse_hand(hand)
    is_pair = (r1 == r2)

    # Base equity by hand tier
    if hand in ('AA', 'KK'):
        return 0.82 if villain_3bet_pct > 0.06 else 0.78
    if hand in ('QQ',):
        return 0.68 - max(0, (0.05 - villain_3bet_pct)) * 2.0
    if hand in ('JJ',):
        return 0.58 - max(0, (0.05 - villain_3bet_pct)) * 3.0
    if hand in ('TT',):
        return 0.52 - max(0, (0.06 - villain_3bet_pct)) * 2.5
    if hand in ('AKs', 'AKo'):
        equity = 0.48 if villain_3bet_pct < 0.06 else 0.52
        return equity + (0.02 if suited else 0)
    if hand in ('AQs', 'AQo'):
        return 0.42 + (0.02 if suited else 0)
    if hand in ('KQs',):
        return 0.38 + 0.02

    # Blocker hands (A2s-A5s): decent equity when hit, block AK/AA
    if r1 == 12 and suited and r2 <= 3:    # A2s-A5s
        return 0.34

    # Other pocket pairs by rank
    if is_pair:
        pair_rank = r1
        return max(0.30, 0.40 + (pair_rank - 7) * 0.015)

    # Suited broadways
    if suited and r1 >= 9 and r2 >= 9:
        return 0.38

    return 0.32   # generic hand


@dataclass
class FourBetResult:
    """Full 4-bet situation analysis."""
    # Inputs
    hand: str
    hero_pos: str
    villain_pos: str
    villain_3bet_pct: float
    three_bet_size_bb: float
    stack_bb: float
    in_position: bool

    # 4-bet sizing
    fourbet_size_bb: float
    min_fourbet_bb: float
    max_fourbet_bb: float

    # Equity & fold equity
    hero_equity: float
    villain_fold_to_4bet: float     # estimated fold % to our 4-bet

    # EV components
    ev_4bet: float
    ev_call: float
    ev_fold: float

    # Hand classification
    hand_tier: str      # 'premium', 'value', 'bluff', 'call', 'fold'
    is_value: bool
    is_bluff: bool
    is_call: bool

    # Decision
    action: str         # '4bet', 'call', 'fold'
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_fourbet(
    hand: str,
    hero_pos: str = 'BTN',
    villain_pos: str = 'BB',
    villain_3bet_pct: float = 0.08,
    three_bet_size_bb: float = 12.0,
    stack_bb: float = 100.0,
    in_position: bool = True,
    open_size_bb: float = 2.5,
) -> FourBetResult:
    """
    Analyze what to do facing a 3-bet.

    Args:
        hand:              Hero's hand string ('AA', 'AKs', 'JJ', 'A5s', etc.)
        hero_pos:          Hero's position ('UTG','HJ','CO','BTN','SB','BB')
        villain_pos:       Villain's position (3-better)
        villain_3bet_pct:  Villain's 3-bet frequency (0-1)
        three_bet_size_bb: Size of villain's 3-bet in BBs
        stack_bb:          Effective stack in BBs
        in_position:       True if hero acts after villain postflop
        open_size_bb:      Hero's original open size

    Returns:
        FourBetResult
    """
    # Normalize: uppercase ranks, lowercase suit ('AKs', 'AKo', 'JJ', ...)
    h = hand.strip()
    if len(h) == 3:
        hand_upper = h[:2].upper() + h[2].lower()
    else:
        hand_upper = h.upper()
    is_wide_3bet = villain_3bet_pct > 0.08    # 8% is roughly JJ+/AQs+ range

    # ── Hand tier classification ─────────────────────────────────────────────
    if hand_upper in _VALUE_4BET_HANDS:
        hand_tier = 'premium'
        is_value = True
        is_bluff = False
        is_call = False
    elif hand_upper in _VALUE_4BET_VS_WIDE and is_wide_3bet:
        hand_tier = 'value'
        is_value = True
        is_bluff = False
        is_call = False
    elif hand_upper in _BLUFF_4BET_HANDS:
        hand_tier = 'bluff'
        is_value = False
        is_bluff = True
        is_call = False
    elif in_position and hand_upper in _CALL_HANDS_IP:
        hand_tier = 'call'
        is_value = False
        is_bluff = False
        is_call = True
    elif not in_position and hand_upper in _CALL_HANDS_OOP:
        hand_tier = 'call'
        is_value = False
        is_bluff = False
        is_call = True
    else:
        hand_tier = 'fold'
        is_value = False
        is_bluff = False
        is_call = False

    # JJ/AQs: value 4-bet vs very wide 3-bettor (>10%)
    if hand_upper in _VALUE_4BET_VS_WIDE and villain_3bet_pct > 0.10:
        hand_tier = 'value'
        is_value = True
        is_call = False

    # ── 4-bet sizing ──────────────────────────────────────────────────────────
    # Standard: 2.2x IP, 2.5x OOP
    position_mult = 2.2 if in_position else 2.5
    fourbet_size = position_mult * three_bet_size_bb
    fourbet_size = max(fourbet_size, three_bet_size_bb * 2.0)
    fourbet_size = min(fourbet_size, stack_bb)    # all-in cap

    min_4bet = three_bet_size_bb * 2.0
    max_4bet = min(stack_bb, three_bet_size_bb * 3.5)

    # ── Fold equity ───────────────────────────────────────────────────────────
    base_fold = _VILLAIN_3BET_FOLD_TO_4BET.get(villain_pos, 0.55)
    # Adjust: tight 3-bet range folds less; wide range folds more
    fold_adj = (villain_3bet_pct - 0.08) * 0.8
    villain_fold_to_4bet = max(0.30, min(0.80, base_fold + fold_adj))

    # ── Equity ────────────────────────────────────────────────────────────────
    hero_equity = _hand_equity_vs_3bet_range(hand_upper, villain_3bet_pct)

    # ── EV calculations ────────────────────────────────────────────────────────
    pot_before_4bet = three_bet_size_bb + open_size_bb   # rough: 3bet + open
    total_pot_if_fold = pot_before_4bet                   # villain folds, hero wins
    total_pot_if_call = pot_before_4bet + fourbet_size    # hero 4bets, villain calls

    # EV of 4-betting:
    #   P(fold) * win_pot + P(call) * (equity * total_pot - (1-equity) * investment)
    hero_investment_4bet = fourbet_size - three_bet_size_bb  # net investment vs call
    ev_if_villain_folds = pot_before_4bet
    ev_if_villain_calls = (hero_equity * (total_pot_if_call + three_bet_size_bb)
                           - (1 - hero_equity) * hero_investment_4bet)

    ev_4bet = (villain_fold_to_4bet * ev_if_villain_folds
               + (1 - villain_fold_to_4bet) * ev_if_villain_calls)

    # EV of calling:
    pot_if_call = pot_before_4bet   # already includes the 3-bet
    call_investment = three_bet_size_bb - open_size_bb    # net call cost (already opened)
    ev_call = hero_equity * (pot_if_call * 2.0) - (1 - hero_equity) * call_investment

    ev_fold = 0.0   # give up open raise investment (sunk)

    # ── Action decision ────────────────────────────────────────────────────────
    if is_value or (is_bluff and ev_4bet > ev_call):
        action = '4bet'
    elif is_call and ev_call > ev_4bet:
        action = 'call'
    elif is_call and ev_call > 0:
        action = 'call'
    else:
        action = 'fold'

    # Override: premium hands always 4-bet
    if hand_tier == 'premium':
        action = '4bet'

    # Override: bluff 4-bet requires fold equity to be worth it
    if is_bluff and villain_fold_to_4bet < 0.45:
        action = 'fold'
        is_bluff = False
        hand_tier = 'fold'

    # ── Tips ──────────────────────────────────────────────────────────────────
    tips = []
    if hand_tier == 'bluff':
        tips.append(
            f'4-bet bluff with {hand}: ace/king blocker reduces AA/AK combos. '
            f'Villain folds {villain_fold_to_4bet:.0%} — justified.'
        )
    if is_value and villain_3bet_pct < 0.05:
        tips.append(
            f'Villain 3-bets only {villain_3bet_pct:.0%} — they have a very tight range. '
            f'Value 4-bet still correct but be prepared for a flat-call with strong hands.'
        )
    if hand_upper in _VALUE_4BET_VS_WIDE and is_wide_3bet:
        tips.append(
            f'Villain 3-bets {villain_3bet_pct:.0%} (wide). {hand} has value 4-bet equity '
            f'({hero_equity:.0%}) vs their light 3-bet range.'
        )
    if action == 'call' and not in_position:
        tips.append(
            f'Calling 3-bet OOP: proceed carefully postflop. '
            f'Check-call or small donk-bet to retain equity with {hand}.'
        )
    if hand_upper in ('TT', '99') and villain_3bet_pct < 0.07:
        tips.append(
            f'{hand} vs tight 3-bet: equity is ~{hero_equity:.0%}. '
            f'Calling IP is fine; fold OOP vs tight range.'
        )
    if action == '4bet' and fourbet_size >= stack_bb * 0.85:
        tips.append(
            f'4-bet of {fourbet_size:.0f}BB is near stack ({stack_bb:.0f}BB) — '
            f'be prepared to commit stack with {hand}.'
        )
    if not tips:
        tips.append(f'Standard play: {action} with {hand} vs {villain_3bet_pct:.0%} 3-bet range.')

    reasoning = (
        f'{hand} ({hand_tier}) vs {villain_pos} 3-bet of {three_bet_size_bb:.1f}BB. '
        f'Villain 3bet%={villain_3bet_pct:.0%}, fold_to_4bet={villain_fold_to_4bet:.0%}. '
        f'Hero equity={hero_equity:.0%}. '
        f'EV(4bet)={ev_4bet:+.2f} EV(call)={ev_call:+.2f}. '
        f'{"IP" if in_position else "OOP"} 4-bet to {fourbet_size:.1f}BB. '
        f'Action: {action.upper()}.'
    )

    return FourBetResult(
        hand=hand,
        hero_pos=hero_pos,
        villain_pos=villain_pos,
        villain_3bet_pct=villain_3bet_pct,
        three_bet_size_bb=three_bet_size_bb,
        stack_bb=stack_bb,
        in_position=in_position,
        fourbet_size_bb=round(fourbet_size, 1),
        min_fourbet_bb=round(min_4bet, 1),
        max_fourbet_bb=round(max_4bet, 1),
        hero_equity=round(hero_equity, 3),
        villain_fold_to_4bet=round(villain_fold_to_4bet, 3),
        ev_4bet=round(ev_4bet, 2),
        ev_call=round(ev_call, 2),
        ev_fold=0.0,
        hand_tier=hand_tier,
        is_value=is_value,
        is_bluff=is_bluff,
        is_call=is_call,
        action=action,
        reasoning=reasoning,
        tips=tips,
    )


def fourbet_one_liner(result: FourBetResult) -> str:
    """Single-line overlay summary."""
    return (
        f'vs 3bet: {result.action.upper()} {result.hand} [{result.hand_tier}] '
        f'{result.fourbet_size_bb:.0f}BB | '
        f'EV(4b)={result.ev_4bet:+.2f} EV(call)={result.ev_call:+.2f}'
    )
