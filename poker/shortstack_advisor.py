"""
Short-Stack Advisor (shortstack_advisor.py)

Covers the 15-50 BB effective stack range where standard full-ring / deep
strategy breaks down.  pushfold.py handles the extreme jam-or-fold zone
(<15 BB); this module handles the more nuanced 15-50 BB decisions.

Key strategic shifts vs 100 BB play:
  Effective 15-25 BB (jam-or-fold territory):
    - Preflop: open-shove or fold; calling opens is dominated
    - Postflop: SPR ≈ 1 → almost always committed; check-raise = shove
    - 3-bet calling requires 70%+ equity; otherwise fold

  Effective 25-40 BB (short stack):
    - Preflop: still tighten ranges significantly
    - 3-bet mostly for value; bluff 3-bets burn too much equity
    - Postflop SPR ≈ 1.5-3 → top pair+ is committed on most boards
    - Float bets require nut-type hands; speculative plays have poor RoI
    - Set mining: only profitable if implied odds exceed 15:1 (rare)

  Effective 40-60 BB (medium stack):
    - Preflop: close to standard, but fewer speculative calls
    - 3-bet pot SPR ≈ 1.5 → handle like short stack postflop
    - Implied odds exist for strong hands but not speculative ones

Usage:
    from poker.shortstack_advisor import analyze_shortstack, ShortStackAdvice
    result = analyze_shortstack(
        eff_stack_bb=30.0,
        pot_bb=8.0,
        hero_pos='BTN',
        villain_pos='BB',
        hero_equity=0.65,
        hand_class='top_pair',
        street='flop',
        hero_is_pfr=True,
    )
    print(result.action, result.reasoning)
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional


_STACK_ZONES = [
    (0,  15, 'jam_fold',   'Jam-or-fold zone (<15 BB): shove or fold only'),
    (15, 25, 'very_short', 'Very short stack (15-25 BB): shove or tight open/fold'),
    (25, 40, 'short',      'Short stack (25-40 BB): limited speculative play'),
    (40, 60, 'medium',     'Medium stack (40-60 BB): modified standard play'),
    (60, 999,'deep',       'Standard deep-stack play (60+ BB)'),
]


def _zone(eff_stack: float) -> tuple:
    for lo, hi, key, desc in _STACK_ZONES:
        if lo <= eff_stack < hi:
            return key, desc
    return 'deep', 'Standard deep-stack play (60+ BB)'


def _spr(pot_bb: float, eff_stack_bb: float) -> float:
    return eff_stack_bb / pot_bb if pot_bb > 0 else 99.0


def _commitment_threshold(spr: float) -> float:
    """Minimum equity to commit remaining stack given SPR."""
    if spr <= 1.0:
        return 0.33   # deeply committed
    elif spr <= 2.0:
        return 0.40
    elif spr <= 3.0:
        return 0.48
    else:
        return 0.55


def _cbet_size(pot_bb: float, eff_stack_bb: float, spr: float) -> float:
    """
    Optimal c-bet size at short stacks.
    At SPR < 2: bet/shove (don't leave an awkward stack)
    At SPR 2-4: 50-70% pot
    """
    if spr <= 1.5:
        return eff_stack_bb   # jam the rest
    elif spr <= 2.5:
        return min(pot_bb * 0.75, eff_stack_bb)
    else:
        return min(pot_bb * 0.60, eff_stack_bb)


def _preflop_open_range_pct(eff_stack: float, position: str) -> float:
    """
    What % of hands to open-raise (or shove) from each position at short stacks.
    Ranges tighten as stack shrinks; shove ranges widen at very short stacks.
    """
    base_pct = {
        'UTG': 0.12, 'UTG1': 0.13, 'MP': 0.16, 'HJ': 0.20,
        'CO': 0.26, 'BTN': 0.40, 'SB': 0.35, 'BB': 0.0,
    }.get(position.upper(), 0.20)

    if eff_stack <= 15:
        # Jam-or-fold: shove ranges are wider than open ranges
        return min(1.0, base_pct * 1.6)
    elif eff_stack <= 25:
        return base_pct * 0.80   # tighten 20%
    elif eff_stack <= 40:
        return base_pct * 0.90   # tighten 10%
    return base_pct


def _should_set_mine(call_bb: float, eff_stack_bb: float) -> bool:
    """
    Set mining is only profitable with 15:1+ implied odds.
    Required stack = 15 * call_bb
    """
    return eff_stack_bb >= 15 * call_bb


@dataclass
class ShortStackAdvice:
    """Strategic advice tuned for 15-60 BB effective stacks."""
    # Stack context
    eff_stack_bb: float
    pot_bb: float
    spr: float
    stack_zone: str         # 'jam_fold', 'very_short', 'short', 'medium', 'deep'
    zone_description: str

    # Preflop
    open_range_pct: float           # % of hands to open from this position
    should_set_mine: bool           # profitable set mining at this depth?
    threebet_guideline: str         # guidance on 3-bet range

    # Postflop
    commitment_threshold: float     # min equity to get it all in
    is_committed: bool              # hero's equity triggers commitment
    cbet_size_bb: float             # recommended c-bet size (may = all-in)
    cbet_is_allin: bool

    # Action
    action: str                     # 'jam', 'bet', 'check-call', 'check-fold', 'fold'
    ev_bet: float
    ev_check: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_shortstack(
    eff_stack_bb: float,
    pot_bb: float,
    hero_pos: str = 'BTN',
    villain_pos: str = 'BB',
    hero_equity: float = 0.55,
    hand_class: str = 'top_pair',   # 'air','pair','top_pair','two_pair','set','draw'
    street: str = 'flop',
    hero_is_pfr: bool = True,
    villain_fold_to_cbet: float = 0.45,
    in_position: bool = True,
) -> ShortStackAdvice:
    """
    Analyze optimal strategy for short-stack situations.

    Args:
        eff_stack_bb:         Effective stack remaining (BB)
        pot_bb:               Current pot size (BB)
        hero_pos:             Hero's position
        villain_pos:          Villain's position
        hero_equity:          Hero's equity vs villain range
        hand_class:           'air', 'pair', 'top_pair', 'two_pair', 'set', 'draw'
        street:               'flop', 'turn', 'river'
        hero_is_pfr:          True if hero raised preflop
        villain_fold_to_cbet: Villain's fold frequency to c-bet
        in_position:          Hero acts last

    Returns:
        ShortStackAdvice
    """
    zone_key, zone_desc = _zone(eff_stack_bb)
    spr = _spr(pot_bb, eff_stack_bb)
    commit_thresh = _commitment_threshold(spr)
    is_committed = hero_equity >= commit_thresh

    open_pct = _preflop_open_range_pct(eff_stack_bb, hero_pos)
    set_mine_ok = _should_set_mine(pot_bb * 0.20, eff_stack_bb)  # assume ~20% pot call

    # ── Preflop 3-bet guidance ────────────────────────────────────────────────
    if eff_stack_bb <= 20:
        threebet = '3-bet/shove only with top 8-10% of hands (AA-TT, AK-AQ). 3-bet/fold is losing play.'
    elif eff_stack_bb <= 35:
        threebet = '3-bet for value only (AA-JJ, AK). Bluff 3-bets require sufficient fold equity; rare.'
    else:
        threebet = '3-bet value (AA-JJ, AK, AQs) + selective bluffs with good blockers (A5s, A4s).'

    # ── C-bet size ────────────────────────────────────────────────────────────
    cbet_size = _cbet_size(pot_bb, eff_stack_bb, spr)
    is_allin = cbet_size >= eff_stack_bb * 0.92

    # ── EV calculations ───────────────────────────────────────────────────────
    total_pot_if_call = pot_bb + cbet_size * 2
    ev_fold_opp  = pot_bb
    ev_call_opp  = hero_equity * total_pot_if_call - cbet_size
    ev_bet = villain_fold_to_cbet * ev_fold_opp + (1 - villain_fold_to_cbet) * ev_call_opp

    realise = 0.85 if in_position else 0.72
    ev_check = hero_equity * pot_bb * realise

    # ── Action ───────────────────────────────────────────────────────────────
    hand_rank = {'air': 0, 'draw': 1, 'pair': 2, 'top_pair': 3,
                 'two_pair': 4, 'set': 5}.get(hand_class.lower(), 3)

    if zone_key == 'jam_fold':
        # Only jam or fold
        action = 'jam' if hero_equity >= 0.38 else 'fold'
    elif spr <= 1.5 and hero_equity >= 0.35:
        action = 'jam'
    elif hand_rank >= 3 and is_committed and hero_is_pfr:
        action = 'bet' if not is_allin else 'jam'
    elif hand_rank >= 3 and ev_bet > ev_check:
        action = 'bet'
    elif hand_rank >= 2 and hero_equity >= 0.45:
        action = 'check-call'
    elif hand_rank >= 4:   # two pair+ always fight back
        action = 'bet'
    else:
        action = 'check-fold'

    # ── Tips ──────────────────────────────────────────────────────────────────
    tips = []
    if zone_key in ('jam_fold', 'very_short'):
        tips.append(
            f'At {eff_stack_bb:.0f}BB effective: avoid c-bet/fold lines. '
            f'Every c-bet should be ready to call off the rest. '
            f'Shove ranges: top {open_pct:.0%} of hands from {hero_pos}.'
        )
    if not set_mine_ok and hand_class in ('pair',):
        tips.append(
            f'Set mining is NOT profitable at {eff_stack_bb:.0f}BB. '
            f'Need 15x call size in stack ({15*pot_bb*0.2:.0f}BB). Fold small pairs vs raises.'
        )
    if spr <= 2.0 and hand_class == 'top_pair':
        tips.append(
            f'SPR={spr:.1f}: top pair is effectively committed. '
            f'C-bet and call any shove. Do not check-fold TPGK at SPR < 2.'
        )
    if is_allin and action == 'bet':
        tips.append(
            f'Bet = shove ({cbet_size:.1f}BB into {pot_bb:.1f}BB pot). '
            f'Use this to deny equity to draws while getting maximum value.'
        )
    if zone_key == 'medium' and hand_class == 'draw':
        tips.append(
            f'At {eff_stack_bb:.0f}BB with a draw: calling is usually wrong '
            f'(no implied odds at shallow stacks). Semi-bluff raise or fold.'
        )
    if not tips:
        tips.append(
            f'{zone_desc}. SPR={spr:.1f}. Commit threshold={commit_thresh:.0%}. '
            f'C-bet {cbet_size:.1f}BB. Action: {action.upper()}.'
        )

    reasoning = (
        f'Stack {eff_stack_bb:.0f}BB effective [{zone_key}]. '
        f'SPR={spr:.1f} → commit@{commit_thresh:.0%}. '
        f'Hero equity={hero_equity:.0%} ({hand_class}). '
        f'C-bet {cbet_size:.1f}BB ({"all-in" if is_allin else "partial"}). '
        f'EV(bet)={ev_bet:+.2f} EV(check)={ev_check:+.2f}. '
        f'Action: {action.upper()}.'
    )

    return ShortStackAdvice(
        eff_stack_bb=round(eff_stack_bb, 1),
        pot_bb=round(pot_bb, 1),
        spr=round(spr, 2),
        stack_zone=zone_key,
        zone_description=zone_desc,
        open_range_pct=round(open_pct, 3),
        should_set_mine=set_mine_ok,
        threebet_guideline=threebet,
        commitment_threshold=round(commit_thresh, 2),
        is_committed=is_committed,
        cbet_size_bb=round(cbet_size, 1),
        cbet_is_allin=is_allin,
        action=action,
        ev_bet=round(ev_bet, 2),
        ev_check=round(ev_check, 2),
        reasoning=reasoning,
        tips=tips,
    )


def shortstack_one_liner(result: ShortStackAdvice) -> str:
    """Single-line overlay summary."""
    allin = ' [SHOVE]' if result.cbet_is_allin else ''
    return (
        f'SS {result.eff_stack_bb:.0f}BB [{result.stack_zone}] SPR={result.spr:.1f} | '
        f'{result.action.upper()}{allin} {result.cbet_size_bb:.1f}BB | '
        f'commit@{result.commitment_threshold:.0%}'
    )
