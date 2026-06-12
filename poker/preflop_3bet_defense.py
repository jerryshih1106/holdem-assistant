"""
Preflop 3-Bet Defense Advisor (preflop_3bet_defense.py)

When an opponent 3-bets your open raise, determine the optimal response:
  4-bet for value, 4-bet as a bluff, call, or fold.

Key decision factors:
  Position (IP vs OOP)       — IP widens calling range dramatically
  Stack depth                — deeper stacks favor calling spec. hands
  Villain's 3-bet %          — high freq = polarized (light 3-bets present)
  Villain's fold to 4-bet %  — high = +EV to bluff 4-bet
  Hand strength + blockers   — AA/KK always 4-bet; A5s/A4s bluff 4-bet

Recommended defense vs 3-bet (6-max, 100 BB):
  Always 4-bet:   AA, KK
  Value 4-bet:    QQ, AK (+ JJ vs high 3-bet%)
  Bluff 4-bet:    A5s, A4s (AK blocker), KQs IP vs high 3-bet%
  IP call:        JJ-TT, AQs, AJs, KQs, maybe 99, QJs vs wide 3-bets
  OOP call:       JJ+, AQs only (very narrow)
  Fold:           everything else

SPR after 4-bet-call:  ~0.25-0.50 → 4-bet/call commits stack → treat as all-in preflop

Usage:
    from poker.preflop_3bet_defense import defend_vs_3bet, ThreeBetDefenseResult
    result = defend_vs_3bet(
        hero_hand='JJ',
        hero_pos='CO',
        villain_3bet_pct=0.07,
        eff_stack_bb=100.0,
        in_position=True,
    )
    print(result.action, result.reasoning)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# Hand strength tiers: higher = stronger
_VALUE_4BET = {
    'AA': 100, 'KK': 99, 'QQ': 97, 'AKs': 96, 'AKo': 95,
}
_JJ_BORDERLINE = {'JJ': 92}
_BLUFF_4BET_CANDIDATES = {
    'A5s': 85, 'A4s': 84, 'A3s': 83, 'A2s': 82,  # A-blocker + suited
    'KQs': 78,                                      # strong blocker IP only
    'A5o': 70, 'A4o': 69,                           # worse version
}
_IP_CALL = {
    'JJ': 92, 'TT': 88, 'AQs': 90, 'AJs': 87,
    'KQs': 82, 'QJs': 78, '99': 75, 'AQo': 80,
    'JTs': 73, 'TJs': 73,
}
_OOP_CALL = {
    'JJ': 92, 'AQs': 90,   # very narrow OOP
}


def _normalize(hand: str) -> str:
    """Normalize hand string: ranks uppercase, suit marker lowercase."""
    hand = hand.strip()
    if len(hand) == 2:
        r1, r2 = hand[0].upper(), hand[1].upper()
        if r1 == r2:
            return r1 + r2  # pocket pair
        return r1 + r2 + 'o'  # two different ranks, assume offsuit
    if len(hand) == 3:
        r1, r2 = hand[0].upper(), hand[1].upper()
        suit = hand[2].lower()  # 's' or 'o'
        return r1 + r2 + suit
    return hand.upper()


def _hand_tier(hand: str, in_position: bool, villain_3bet_pct: float, fold_to_4bet: float) -> Tuple[str, str, float]:
    """
    Classify optimal action for this hand.
    Returns (action, reason, ev_estimate_relative).
    action: '4bet_value' | '4bet_bluff' | 'call' | 'fold'
    """
    h = hand

    if h in _VALUE_4BET:
        return '4bet_value', f'{h} always 4-bets for value; opponent folds or stacks off dominated.', 0.30

    # JJ: value 4-bet vs wide 3-bet, call vs nit
    if h == 'JJ':
        if villain_3bet_pct >= 0.07 or in_position:
            return '4bet_value', 'JJ 4-bets vs wide 3-bet% or IP; blocks opponents 4-bet shove range.', 0.15
        return 'call', 'JJ calls vs tight 3-bet%; avoid stack-off vs nit who rarely has bluffs.', 0.08

    if h in _BLUFF_4BET_CANDIDATES:
        if fold_to_4bet >= 0.60:
            return '4bet_bluff', f'{h} is an ideal 4-bet bluff: A-blocker + suited + opponent folds often.', 0.10
        return 'fold', f'{h}: bluff 4-bet is -EV when villain calls 4-bets {(1-fold_to_4bet):.0%} of the time.', -0.05

    if in_position and h in _IP_CALL:
        return 'call', f'{h} calls IP; position allows realizing equity with good implied odds.', 0.06

    if not in_position and h in _OOP_CALL:
        return 'call', f'{h} calls OOP; narrow range but strong enough to continue without initiative.', 0.04

    # Wide-range hands: fold everything else
    return 'fold', f'{h} folds — insufficient equity + difficult spot OOP vs likely value range.', -0.03


def _spr_after_4bet(hero_open_bb: float, villain_3bet_bb: float, hero_4bet_bb: float, eff_stack: float) -> float:
    pot = hero_open_bb + villain_3bet_bb + hero_4bet_bb
    remaining = eff_stack - hero_4bet_bb
    return remaining / pot if pot > 0 else 0.0


def _optimal_4bet_size(eff_stack_bb: float, villain_3bet_bb: float, in_position: bool) -> float:
    """Standard 4-bet sizing: ~2.2-2.5x the 3-bet."""
    if in_position:
        size = villain_3bet_bb * 2.2
    else:
        size = villain_3bet_bb * 2.5
    return min(size, eff_stack_bb)


def _eq_vs_range(action: str, villain_3bet_pct: float) -> float:
    """Rough equity estimate based on action and villain 3-bet frequency."""
    # Wider 3-bet range = more bluffs = our calls/4bets work better
    tightness = max(0.0, 1.0 - villain_3bet_pct / 0.12)
    if '4bet' in action:
        return 0.55 + villain_3bet_pct * 0.8   # bluff equity if villain folds
    if action == 'call':
        return 0.42 + (1.0 - tightness) * 0.08
    return 0.0


@dataclass
class ThreeBetDefenseResult:
    """Optimal response to a 3-bet."""
    # Inputs
    hero_hand: str
    hero_pos: str
    villain_3bet_pct: float
    eff_stack_bb: float
    in_position: bool

    # Decision
    action: str          # '4bet_value', '4bet_bluff', 'call', 'fold'
    action_label: str    # human-readable: '4-bet for value', 'fold', etc.

    # Sizing (when applicable)
    hero_open_bb: float              # assumed open size
    villain_3bet_bb: float           # assumed 3-bet size
    recommended_4bet_bb: float       # 0 if calling/folding
    spr_after_4bet_called: float     # stack-to-pot ratio if 4-bet is called

    # Context
    villain_3bet_type: str           # 'value_only', 'balanced', 'wide_bluff'
    hand_in_4bet_value_range: bool
    hand_in_4bet_bluff_range: bool
    hand_in_call_range: bool

    # EV / equity estimate
    estimated_equity: float
    ev_relative: float               # relative EV of chosen action vs folding

    # Guidance
    reasoning: str
    tips: List[str] = field(default_factory=list)
    full_defense_ranges: str = ''


def defend_vs_3bet(
    hero_hand: str,
    hero_pos: str = 'CO',
    villain_pos: str = 'BTN',
    villain_3bet_pct: float = 0.07,
    villain_fold_to_4bet: float = 0.55,
    eff_stack_bb: float = 100.0,
    hero_open_bb: float = 0.0,   # 0 → auto-compute typical open
    villain_3bet_bb: float = 0.0, # 0 → auto-compute
    in_position: Optional[bool] = None,
) -> ThreeBetDefenseResult:
    """
    Determine optimal defense vs a 3-bet.

    Args:
        hero_hand:          e.g. 'JJ', 'AKs', 'KQo', 'A5s'
        hero_pos:           Hero's position ('UTG', 'CO', 'BTN', etc.)
        villain_pos:        Villain's position
        villain_3bet_pct:   Villain's 3-bet frequency (0-1)
        villain_fold_to_4bet: Villain folds to 4-bet (0-1)
        eff_stack_bb:       Effective stack in BB
        hero_open_bb:       Hero's open size (auto if 0)
        villain_3bet_bb:    Villain's 3-bet size (auto if 0)
        in_position:        Hero acts after villain postflop (auto-detect if None)

    Returns:
        ThreeBetDefenseResult
    """
    hand = _normalize(hero_hand)

    # Position: BTN, CO, HJ generally IP vs blinds; SB/BB generally OOP
    if in_position is None:
        pos_upper = hero_pos.upper()
        # Hero opened from pos, villain 3-bet from their pos.
        # If villain is in blinds (SB/BB) and hero is CO/BTN, hero is IP.
        # Simplified: if villain_pos is SB or BB, hero is IP.
        villain_upper = villain_pos.upper()
        in_position = villain_upper in ('SB', 'BB')

    # Auto-size
    if hero_open_bb <= 0:
        hero_open_bb = 2.5  # standard 6-max open
    if villain_3bet_bb <= 0:
        villain_3bet_bb = hero_open_bb * 3.0 if in_position else hero_open_bb * 3.5

    # Villain 3-bet type classification
    if villain_3bet_pct <= 0.05:
        v3b_type = 'value_only'
    elif villain_3bet_pct <= 0.09:
        v3b_type = 'balanced'
    else:
        v3b_type = 'wide_bluff'

    action, reason, ev_rel = _hand_tier(hand, in_position, villain_3bet_pct, villain_fold_to_4bet)

    # Check range memberships
    in_value_4bet = hand in _VALUE_4BET or (hand == 'JJ' and (villain_3bet_pct >= 0.07 or in_position))
    in_bluff_4bet = hand in _BLUFF_4BET_CANDIDATES and villain_fold_to_4bet >= 0.60
    in_call = (hand in _IP_CALL and in_position) or (hand in _OOP_CALL and not in_position)

    # 4-bet sizing
    rec_4bet = 0.0
    if '4bet' in action:
        rec_4bet = _optimal_4bet_size(eff_stack_bb, villain_3bet_bb, in_position)

    spr_after = _spr_after_4bet(hero_open_bb, villain_3bet_bb, rec_4bet, eff_stack_bb) if rec_4bet > 0 else 0.0
    est_eq = _eq_vs_range(action, villain_3bet_pct)

    action_labels = {
        '4bet_value': '4-bet for value',
        '4bet_bluff': '4-bet as a bluff',
        'call': 'call and play postflop',
        'fold': 'fold',
    }

    # Full range text
    ip_str = 'IP' if in_position else 'OOP'
    v3b_label = {'value_only': 'tight (<5%)', 'balanced': 'balanced (5-9%)', 'wide_bluff': 'wide (>9%)'}[v3b_type]
    def_range = (
        f'Defense ranges vs {villain_3bet_pct:.0%} 3-bet [{v3b_label}] {ip_str}: '
        f'4-bet/value: QQ+/AK' + (' + JJ' if villain_3bet_pct >= 0.07 else '') + ' | '
        f'4-bet/bluff: A5s-A2s' + (' + KQs' if in_position else '') + ' (if FvF4B>=60%) | '
        f'Call: ' + ('JJ/TT/AQs/AJs/KQs' if in_position else 'JJ/AQs') + ' | '
        f'Fold: everything else'
    )

    # Tips
    tips = []
    if v3b_type == 'value_only' and action == 'call':
        tips.append(
            f'Villain 3-bets only {villain_3bet_pct:.0%} — tight range. '
            f'Tighten your call range; their range has fewer bluffs to exploit.'
        )
    if spr_after > 0 and spr_after < 0.5:
        tips.append(
            f'SPR after 4-bet called = {spr_after:.2f} — committed. '
            f'4-bet/call is effectively an all-in; ensure hand has 55%+ equity vs calling range.'
        )
    if action == '4bet_bluff':
        fold_eq = villain_fold_to_4bet * villain_3bet_bb
        tips.append(
            f'Bluff 4-bet EV: villain folds {villain_fold_to_4bet:.0%} × {villain_3bet_bb:.0f}BB = '
            f'+{fold_eq:.1f}BB when it works. Need fold equity > call losses.'
        )
    if not in_position and action == 'call':
        tips.append(
            'Calling OOP is difficult. Plan to check-raise flops where you have equity. '
            'Avoid calling again on flop without strong piece or equity.'
        )
    if v3b_type == 'wide_bluff' and action == 'fold':
        tips.append(
            f'Villain 3-bets wide ({villain_3bet_pct:.0%}); consider adding this hand to your call/4-bet range '
            f'if you have position and playability.'
        )

    reasoning = (
        f'Hero: {hand} ({ip_str}) vs {villain_3bet_pct:.0%} 3-bet ({v3b_type}). '
        f'Villain FvF4B={villain_fold_to_4bet:.0%}. '
        f'Optimal: {action_labels[action]}. '
        f'{reason}'
    )

    return ThreeBetDefenseResult(
        hero_hand=hand,
        hero_pos=hero_pos.upper(),
        villain_3bet_pct=villain_3bet_pct,
        eff_stack_bb=eff_stack_bb,
        in_position=in_position,
        action=action,
        action_label=action_labels[action],
        hero_open_bb=round(hero_open_bb, 1),
        villain_3bet_bb=round(villain_3bet_bb, 1),
        recommended_4bet_bb=round(rec_4bet, 1),
        spr_after_4bet_called=round(spr_after, 2),
        villain_3bet_type=v3b_type,
        hand_in_4bet_value_range=in_value_4bet,
        hand_in_4bet_bluff_range=in_bluff_4bet,
        hand_in_call_range=in_call,
        estimated_equity=round(est_eq, 2),
        ev_relative=round(ev_rel, 3),
        reasoning=reasoning,
        tips=tips,
        full_defense_ranges=def_range,
    )


def defense_one_liner(result: ThreeBetDefenseResult) -> str:
    """Single-line overlay summary."""
    size_str = f' → 4B {result.recommended_4bet_bb:.0f}BB' if result.recommended_4bet_bb > 0 else ''
    ip_str = 'IP' if result.in_position else 'OOP'
    return (
        f'{result.hero_hand} {ip_str} vs {result.villain_3bet_pct:.0%} 3-bet [{result.villain_3bet_type}] | '
        f'{result.action_label.upper()}{size_str} | eq~{result.estimated_equity:.0%}'
    )
