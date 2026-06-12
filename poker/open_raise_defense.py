"""
Open Raise Defense Advisor (open_raise_defense.py)

When a player in position open-raises and hero is in the blinds,
the defense decision is complex: call, 3-bet, or fold. Each option
has different EV profiles depending on position, ranges, and reads.

Key concepts:
  - BB defends wider than SB (BB already has equity in pot)
  - IP defender (rare) vs OOP defender (usual for blinds)
  - MDF: Minimum Defense Frequency = 1 - fold_equity
  - 3-bet vs call vs fold: depends on hand playability, position, stack

Position-specific defense frequencies:
  SB vs BTN open (2.5BB):
    MDF = 1 - 2.5/(pot+2.5) ≈ 62%
    SB defense split: 3-bet 8-10%, call 22-30%, fold 60-70%
    (SB is OOP vs both BB and BTN)

  BB vs BTN open (2.5BB):
    MDF = 1 - 1.5/(pot+1.5) ≈ 60%  (BB has already invested 1BB)
    BB defense: 3-bet 8-12%, call 45-55%, fold 33-47%
    (BB is OOP only vs BTN)

  BB vs CO open:
    Slightly tighter call range (CO is less positionally abused)
    3-bet range: {AQs+, KQs, QQ+, some bluffs like A5s-A4s, 76s}

  BB vs UTG open:
    Tightest defense (UTG has strongest range)
    3-bet value: {QQ+, AK}; 3-bet bluffs: rare

Defense ranges are affected by:
  - Stack depth: deep (100BB+) → wider call with speculative hands
  - Villain's open freq: tight UTG (8%) vs loose BTN (42%) dramatically
    changes which hands are profitable to defend
  - Villain's cbet freq: high cbet → 3-bet more for fold equity
  - Rake: very high rake reduces calling range profitability

Usage:
    from poker.open_raise_defense import advise_defense, DefenseAdvice
    result = advise_defense(
        hero_pos='BB',
        villain_pos='BTN',
        villain_open_pct=0.42,
        villain_open_bb=2.5,
        hero_hand_class='medium',
        hero_equity=0.48,
        eff_stack_bb=100.0,
    )
    print(result.action, result.call_ev_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _hand_rank(hand_class: str) -> int:
    return {
        'premium': 10, 'strong': 8, 'medium_pair': 6, 'medium': 5,
        'speculative': 3, 'marginal': 2, 'trash': 0,
        'air': 0, 'draw': 3, 'bottom_pair': 2, 'middle_pair': 4,
        'top_pair': 6, 'tptk': 7, 'overpair': 8, 'two_pair': 8, 'set': 9,
    }.get(hand_class.lower(), 4)


# Villain open percentage by position (approximate GTO)
_OPEN_PCT = {'UTG': 0.13, 'UTG1': 0.16, 'HJ': 0.20, 'CO': 0.28, 'BTN': 0.42, 'SB': 0.52}


def _mdf(call_bb: float, pot_before: float) -> float:
    """Minimum Defense Frequency = pot / (pot + call)."""
    return round(pot_before / (pot_before + call_bb), 3)


def _threeBet_size(hero_pos: str, villain_open_bb: float, eff_stack: float) -> float:
    """Optimal 3-bet size in BB."""
    # SB is OOP vs both the opener AND the BB → needs larger 3-bet
    # BB is OOP only vs the opener → slightly smaller
    if hero_pos == 'SB':
        mult = 3.8  # doubly OOP: charge opener heavily
    else:  # BB
        mult = 3.1
    raw = villain_open_bb * mult
    return round(min(eff_stack * 0.20, max(8.0, raw)), 1)


def _ev_call(hero_equity: float, pot_after_call: float, call_bb: float) -> float:
    """EV of calling = equity × pot - call."""
    return round(hero_equity * pot_after_call - call_bb, 2)


def _ev_threeb(hero_equity: float, threeb_bb: float,
               villain_fold_to_3b: float, pot_before: float) -> float:
    """EV of 3-betting."""
    fold_ev = villain_fold_to_3b * pot_before
    call_pot = pot_before + threeb_bb * 2
    call_ev = (1 - villain_fold_to_3b) * (hero_equity * call_pot - threeb_bb)
    return round(fold_ev + call_ev, 2)


def _defense_range_note(villain_pos: str, villain_open_pct: float) -> str:
    """Qualitative defense range description."""
    tightness = 'tight' if villain_open_pct < 0.22 else (
        'standard' if villain_open_pct < 0.38 else 'wide')
    notes = {
        ('UTG', 'tight'): 'vs tight UTG: 3-bet QQ+/AK only. Call AQs-AJs, TT-99, KQs, 87s+',
        ('CO', 'standard'): 'vs CO: 3-bet QQ+/AK + A5s-A4s bluffs. Call JJ-77, AQo-AJo, KQs-KJs',
        ('BTN', 'wide'): 'vs BTN: 3-bet TT+/AQs+ + A5s-A2s/76s bluffs. Call wide (50%+ of hands in BB)',
        ('SB', 'wide'): 'vs SB: defend 3-bet QQ+/AK. Call medium hands. SB often bluff-steals.',
    }
    key = (villain_pos, tightness)
    return notes.get(key, f'vs {villain_pos} ({tightness}): adjust to villain open% = {villain_open_pct:.0%}')


@dataclass
class DefenseAdvice:
    """BB/SB defense advice vs an open raise."""
    hero_pos: str
    villain_pos: str
    villain_open_bb: float
    villain_open_pct: float
    hero_hand_class: str
    hero_equity: float

    # Decision
    action: str           # '3bet', 'call', 'fold'
    threeb_size_bb: float
    call_bb: float        # what hero pays to call

    # Defense math
    mdf: float            # minimum defense frequency
    pot_after_call_bb: float

    # EV comparison
    call_ev_bb: float
    threeb_ev_bb: float

    # Range context
    defense_range_note: str
    villain_fold_to_3b_est: float  # estimated fold to 3-bet

    # Notes
    action_reasoning: str
    strategic_tips: List[str] = field(default_factory=list)


def advise_defense(
    hero_pos: str = 'BB',
    villain_pos: str = 'BTN',
    villain_open_pct: float = 0.42,
    villain_open_bb: float = 2.5,
    hero_hand_class: str = 'medium',
    hero_equity: float = 0.48,
    eff_stack_bb: float = 100.0,
    villain_fold_to_3b: float = 0.55,
    villain_cbet_pct: float = 0.55,
) -> DefenseAdvice:
    """
    Advise on BB/SB defense vs an open raise.

    Args:
        hero_pos:             'BB' or 'SB'
        villain_pos:          Villain's position ('UTG','HJ','CO','BTN','SB')
        villain_open_pct:     Villain's open raise frequency (0-1)
        villain_open_bb:      Villain's open size in BB
        hero_hand_class:      Hero's hand classification
        hero_equity:          Hero's equity vs villain's open range
        eff_stack_bb:         Effective stack depth
        villain_fold_to_3b:   Estimated villain fold to 3-bet (0-1)
        villain_cbet_pct:     Villain's c-bet frequency (influences 3-bet value)

    Returns:
        DefenseAdvice
    """
    rank = _hand_rank(hero_hand_class)

    # Pot before hero acts: SB+BB+villain_open
    if hero_pos == 'BB':
        call_bb = villain_open_bb - 1.0  # BB already paid 1BB
        pot_before = 1.0 + 0.5 + villain_open_bb  # BB + SB + open
    else:  # SB
        call_bb = villain_open_bb - 0.5  # SB already paid 0.5BB
        pot_before = 0.5 + 1.0 + villain_open_bb  # SB + BB + open

    call_bb = round(max(0.5, call_bb), 1)
    pot_after_call = round(pot_before + call_bb, 1)
    mdf = _mdf(call_bb, pot_before)

    threeb_bb = _threeBet_size(hero_pos, villain_open_bb, eff_stack_bb)
    ev_call = _ev_call(hero_equity, pot_after_call, call_bb)
    ev_3b = _ev_threeb(hero_equity, threeb_bb, villain_fold_to_3b, pot_before)

    range_note = _defense_range_note(villain_pos, villain_open_pct)

    # Villain's range tightness affects our equity
    villain_is_tight = villain_open_pct < _OPEN_PCT.get(villain_pos, 0.30) * 0.80
    villain_is_loose = villain_open_pct > _OPEN_PCT.get(villain_pos, 0.30) * 1.25

    # Decision logic
    if rank >= 9:  # premium
        action = '3bet'
        reason = (
            f'Premium {hero_hand_class}: 3-bet to {threeb_bb:.0f}BB. '
            f'Villain folds {villain_fold_to_3b:.0%} → EV = {ev_3b:.1f}BB. '
            f'Do not slow-play vs position-raising range.'
        )
    elif rank >= 8 and ev_3b >= ev_call:  # strong: 3-bet when EV better
        action = '3bet'
        reason = (
            f'Strong hand: 3-bet ({ev_3b:.1f}BB) > call ({ev_call:.1f}BB). '
            f'Build pot in position-favorable spot.'
        )
    elif rank >= 3 and ev_call >= 0:  # medium/speculative: call if +EV
        if hero_pos == 'SB' and rank < 5:
            # SB is doubly OOP — more selective calling
            action = 'fold'
            reason = (
                f'SB: medium-weak hand with double OOP disadvantage. '
                f'Call EV = {ev_call:.1f}BB but position cost is real. '
                f'Fold and wait for better spot.'
            )
        else:
            action = 'call'
            reason = (
                f'Call: {hero_hand_class} has {hero_equity:.0%} equity vs '
                f'{villain_pos} range. EV = {ev_call:.1f}BB. '
                f'Pot odds: {pot_before:.1f}/{call_bb:.1f} = {pot_before/call_bb:.1f}:1.'
            )
    elif rank >= 3 and villain_fold_to_3b >= 0.60 and hero_pos == 'BB':
        # Light 3-bet bluff when villain folds a lot
        action = '3bet'
        reason = (
            f'Light 3-bet: villain folds to 3-bets {villain_fold_to_3b:.0%}. '
            f'Profitable bluff even with {hero_hand_class}. '
            f'3-bet to {threeb_bb:.0f}BB and take it down preflop.'
        )
    else:
        action = 'fold'
        reason = (
            f'Fold: {hero_hand_class} has {hero_equity:.0%} equity vs '
            f'{villain_pos} ({villain_open_pct:.0%} range). '
            f'Call EV = {ev_call:.1f}BB. Not profitable to defend.'
        )

    tips = [f'MDF = {mdf:.0%}: hero must defend at least this often to prevent profit-fold exploit.']
    if villain_is_loose:
        tips.append(
            f'{villain_pos} opens loosely ({villain_open_pct:.0%}): '
            f'call wider than usual, 3-bet-bluff more often. '
            f'Their range includes many weak hands that miss flops.'
        )
    if villain_is_tight:
        tips.append(
            f'{villain_pos} opens tight ({villain_open_pct:.0%}): '
            f'need strong hands to defend. More folding is correct. '
            f'3-bet only premiums — they have a strong range.'
        )
    if villain_cbet_pct > 0.70:
        tips.append(
            f'High c-bet frequency ({villain_cbet_pct:.0%}): '
            f'3-betting pre gives extra fold equity on flop (they continue mechanically). '
            f'Check-raising becomes more effective post-flop.'
        )
    if hero_pos == 'SB':
        tips.append(
            'SB: you are OOP vs everyone postflop. '
            'Only defend with hands that play well multiway or vs 1 opponent.'
        )

    return DefenseAdvice(
        hero_pos=hero_pos,
        villain_pos=villain_pos,
        villain_open_bb=villain_open_bb,
        villain_open_pct=villain_open_pct,
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        action=action,
        threeb_size_bb=threeb_bb,
        call_bb=call_bb,
        mdf=mdf,
        pot_after_call_bb=pot_after_call,
        call_ev_bb=ev_call,
        threeb_ev_bb=ev_3b,
        defense_range_note=range_note,
        villain_fold_to_3b_est=villain_fold_to_3b,
        action_reasoning=reason,
        strategic_tips=tips,
    )


def defense_one_liner(result: DefenseAdvice) -> str:
    return (
        f'[DEF {result.hero_pos}vs{result.villain_pos}] '
        f'{result.action.upper()} | '
        f'MDF={result.mdf:.0%} | '
        f'EV_call={result.call_ev_bb:.1f}BB 3b={result.threeb_ev_bb:.1f}BB | '
        f'eq={result.hero_equity:.0%}'
    )
