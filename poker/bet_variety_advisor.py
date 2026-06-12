"""
Bet Variety Advisor (bet_variety_advisor.py)

Guides players to MIX bet sizes (small/standard/large) for balance and
unexploitability. Using one size for all situations makes you exploitable.

THEORY:
  BET SIZE MIXING = using multiple sizes in the same spot to prevent exploitation.

  WHY MIX SIZES?
  - If you always bet 60% pot with strong hands, villain knows to fold
  - If you always bet small with weak hands, villain knows to call/raise
  - Mixing: villain cannot assign hand strength based on bet size alone

  STANDARD SIZE CATEGORIES:
  - SMALL:    25-40% pot (thin value, board coverage, protection)
  - STANDARD: 50-70% pot (baseline; good for most situations)
  - LARGE:    75-100% pot (polarized; strong value or pure bluff)
  - OVERBET:  120-200% pot (maximum polarization; nut hands or air)

  MIXING STRATEGY (GTO APPROXIMATE):
  On DRY boards (low texture):
  - Small bet: medium pairs, weak top pairs (non-polarized)
  - Standard: top pair, overpairs
  - Large: nut draws, sets, 2-pair (polarized range)

  On WET boards (high texture):
  - Small bet: protection bets with made hands
  - Large/overbet: strong draws (sets), nutted hands

  POSITION EFFECTS:
  - IP: can use smaller sizes (more control; more streets to get value)
  - OOP: need larger sizes (one-shot; cannot see reaction before committing)

  VILLAIN-BASED MIXING:
  - vs Fish/Calling Station: value bet LARGE (they call regardless)
  - vs Nit: value bet STANDARD (they fold to large; extract with standard)
  - vs LAG: mix more (they adjust to sizes; must vary to prevent exploitation)

  FREQUENCY TARGETS (for balanced range):
  Small: ~30-40% of bets
  Standard: ~40-50% of bets
  Large: ~15-25% of bets
  Overbet: ~5-10% of bets

DISTINCT FROM:
  adaptive_sizing.py:        Adaptive bet sizing
  bet_sizing.py:             General bet sizing
  bet_sizing_strategy.py:    Sizing strategy
  THIS MODULE:               MIXING FREQUENCIES; why/when to use each size;
                             exploitability prevention; board-texture-based mixing.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


SIZE_CATEGORIES: dict = {
    'small':    (0.25, 0.40),
    'standard': (0.50, 0.68),
    'large':    (0.75, 1.00),
    'overbet':  (1.20, 2.00),
}

DRY_BOARD_MIX: dict = {
    'nuts':           {'small': 0.10, 'standard': 0.20, 'large': 0.50, 'overbet': 0.20},
    'strong_value':   {'small': 0.15, 'standard': 0.45, 'large': 0.30, 'overbet': 0.10},
    'top_pair_gk':    {'small': 0.30, 'standard': 0.50, 'large': 0.20, 'overbet': 0.00},
    'top_pair_wk':    {'small': 0.55, 'standard': 0.35, 'large': 0.10, 'overbet': 0.00},
    'middle_pair':    {'small': 0.70, 'standard': 0.25, 'large': 0.05, 'overbet': 0.00},
    'bluff':          {'small': 0.20, 'standard': 0.35, 'large': 0.30, 'overbet': 0.15},
    'draw_nut':       {'small': 0.10, 'standard': 0.30, 'large': 0.45, 'overbet': 0.15},
    'draw_standard':  {'small': 0.30, 'standard': 0.50, 'large': 0.20, 'overbet': 0.00},
}

WET_BOARD_MIX: dict = {
    'nuts':           {'small': 0.05, 'standard': 0.15, 'large': 0.45, 'overbet': 0.35},
    'strong_value':   {'small': 0.10, 'standard': 0.35, 'large': 0.40, 'overbet': 0.15},
    'top_pair_gk':    {'small': 0.40, 'standard': 0.40, 'large': 0.20, 'overbet': 0.00},
    'top_pair_wk':    {'small': 0.65, 'standard': 0.30, 'large': 0.05, 'overbet': 0.00},
    'middle_pair':    {'small': 0.80, 'standard': 0.20, 'large': 0.00, 'overbet': 0.00},
    'bluff':          {'small': 0.15, 'standard': 0.30, 'large': 0.35, 'overbet': 0.20},
    'draw_nut':       {'small': 0.05, 'standard': 0.20, 'large': 0.50, 'overbet': 0.25},
    'draw_standard':  {'small': 0.35, 'standard': 0.45, 'large': 0.20, 'overbet': 0.00},
}

VILLAIN_SIZE_ADJUSTMENT: dict = {
    'fish':   {'small': -0.10, 'standard': -0.10, 'large': +0.15, 'overbet': +0.05},
    'nit':    {'small': +0.15, 'standard': +0.10, 'large': -0.15, 'overbet': -0.10},
    'lag':    {'small': +0.10, 'standard': +0.00, 'large': +0.00, 'overbet': -0.10},
    'rec':    {'small': -0.05, 'standard': +0.05, 'large': +0.00, 'overbet': +0.00},
    'reg':    {'small': +0.00, 'standard': +0.00, 'large': +0.00, 'overbet': +0.00},
}


def _mixing_frequencies(
    hand_strength: str,
    board_texture: str,
    villain_type: str,
) -> dict:
    """Return dict of size->frequency after villain adjustments."""
    base = WET_BOARD_MIX if board_texture in ('wet', 'monotone') else DRY_BOARD_MIX
    hand_mix = base.get(hand_strength, base.get('top_pair_gk', {}))
    adj = VILLAIN_SIZE_ADJUSTMENT.get(villain_type, {})

    result = {}
    for size in ('small', 'standard', 'large', 'overbet'):
        raw = hand_mix.get(size, 0.0) + adj.get(size, 0.0)
        result[size] = max(0.0, raw)

    total = sum(result.values())
    if total > 0:
        result = {k: round(v / total, 2) for k, v in result.items()}
    return result


def _primary_size(mixing_freq: dict) -> str:
    return max(mixing_freq, key=mixing_freq.get)


def _size_bb(pot_bb: float, size_name: str) -> float:
    lo, hi = SIZE_CATEGORIES[size_name]
    midpoint = (lo + hi) / 2.0
    return round(pot_bb * midpoint, 1)


def _exploit_score(mixing_freq: dict) -> int:
    """Lower entropy = more exploitable. Higher score = better mixing."""
    max_freq = max(mixing_freq.values()) if mixing_freq else 1.0
    if max_freq >= 0.80:
        return 2
    elif max_freq >= 0.65:
        return 5
    elif max_freq >= 0.50:
        return 7
    return 9


@dataclass
class BetVarietyResult:
    hand_strength: str
    board_texture: str
    villain_type: str

    mixing_frequencies: dict
    primary_size: str
    primary_size_bb: float
    exploit_score: int

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_bet_variety(
    hand_strength: str = 'top_pair_gk',
    board_texture: str = 'semi_wet',
    villain_type: str = 'reg',
    pot_bb: float = 20.0,
    position: str = 'ip',
    street: str = 'flop',
) -> BetVarietyResult:
    """
    Recommend bet size mixing frequencies for balanced strategy.

    Args:
        hand_strength:  Hand category ('nuts','strong_value','top_pair_gk',
                        'top_pair_wk','middle_pair','bluff','draw_nut','draw_standard')
        board_texture:  Board texture ('dry','semi_wet','wet','monotone')
        villain_type:   Villain type ('fish','rec','nit','lag','reg')
        pot_bb:         Current pot in BB
        position:       Hero position ('ip'/'oop')
        street:         Current street ('flop','turn','river')

    Returns:
        BetVarietyResult
    """
    mix = _mixing_frequencies(hand_strength, board_texture, villain_type)
    primary = _primary_size(mix)
    size_bb = _size_bb(pot_bb, primary)
    score = _exploit_score(mix)

    verdict = (
        f'[BVA {hand_strength}|{board_texture}|{villain_type}] '
        f'primary={primary} ({mix[primary]:.0%}) size={size_bb:.1f}BB '
        f'exploit_score={score}/10'
    )

    reasoning = (
        f'Bet variety: {hand_strength} on {board_texture} vs {villain_type} ({street}). '
        f'Mixing: small={mix["small"]:.0%} std={mix["standard"]:.0%} '
        f'large={mix["large"]:.0%} obet={mix["overbet"]:.0%}. '
        f'Primary: {primary} at {mix[primary]:.0%}. '
        f'Exploit score: {score}/10 (higher = less exploitable).'
    )

    tips = []

    tips.append(
        f'MIXING FREQUENCIES: small={mix["small"]:.0%} | standard={mix["standard"]:.0%} | '
        f'large={mix["large"]:.0%} | overbet={mix["overbet"]:.0%}. '
        f'Primary choice: {primary} ({mix[primary]:.0%} of time).'
    )

    tips.append(
        f'EXPLOIT SCORE: {score}/10. '
        f'{"Good mixing -- hard for villain to read your sizing." if score >= 7 else "Decent mixing." if score >= 5 else "Too predictable -- add more size variety to prevent exploitation."}'
    )

    if villain_type in ('fish', 'calling_station'):
        tips.append(
            f'VS {villain_type.upper()}: Shift toward LARGE/OVERBET sizes. '
            f'They call regardless of size -- capture maximum value with bigger bets. '
            f'Mixing is less important; focus on capturing value.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT: Shift toward SMALL/STANDARD sizes. '
            f'Nit folds to large bets even with made hands. '
            f'Bet small to get called; large bets just take dead money from this player type.'
        )
    elif villain_type == 'lag':
        tips.append(
            f'VS LAG: Mix sizes aggressively. '
            f'LAG players adjust to sizing tells -- must vary to prevent exploitation. '
            f'Use all four size categories based on hand; do not give away strength.'
        )

    if hand_strength in ('nuts', 'strong_value') and mix.get('overbet', 0) >= 0.10:
        tips.append(
            f'OVERBET OPPORTUNITY: {hand_strength} on {board_texture} -- consider overbet {mix["overbet"]:.0%} of the time. '
            f'Overbets with nuts are balanced if you include some air/bluffs at same sizing.'
        )

    return BetVarietyResult(
        hand_strength=hand_strength,
        board_texture=board_texture,
        villain_type=villain_type,
        mixing_frequencies=mix,
        primary_size=primary,
        primary_size_bb=size_bb,
        exploit_score=score,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bva_one_liner(r: BetVarietyResult) -> str:
    return (
        f'[BVA {r.hand_strength}|{r.board_texture}|{r.villain_type}] '
        f'primary={r.primary_size} ({r.mixing_frequencies[r.primary_size]:.0%}) '
        f'{r.primary_size_bb:.1f}BB exploit={r.exploit_score}/10'
    )
