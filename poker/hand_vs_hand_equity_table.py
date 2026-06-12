"""
Hand vs Hand Equity Table (hand_vs_hand_equity_table.py)

Fast lookup table for equity between hand categories.
Used by other modules that need quick equity estimates without Monte Carlo.

THEORY:
  Pre-computed approximate equity for all common hand category matchups.
  Organized by (hero_category, villain_category) -> equity.
  Street-adjusted: equity varies by flop/turn/river.

  KEY MATCHUPS:
  - Set vs flush draw (flop): set ~65%, draw ~35%
  - Overpair vs two_pair: 55% vs 45%
  - Top pair vs combo_draw: 55% vs 45%
  - Flush vs straight: flush ~70% (depends on board)
  - Nuts vs any: nuts ~95%

  USAGE:
  When hero holds a specific hand category and wants to know equity vs
  villain's estimated hand category, this module provides instant results
  without running Monte Carlo simulation.

DISTINCT FROM:
  equity.py:       Monte Carlo equity for specific cards
  facing_aggression.py: Equity adjustment for villain action
  THIS MODULE:     Fast categorical equity lookup; no simulation needed.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Equity table: (hero_category, villain_category) -> (equity, confidence)
# Equity is hero's equity when hero has hero_category vs villain has villain_category
# Confidence: 1=very_high, 2=high, 3=medium (some variance by specific board)

_EQUITY_TABLE: Dict[tuple, float] = {
    # Hero has nuts vs anything
    ('nuts', 'nuts'):         0.50,
    ('nuts', 'near_nuts'):    0.75,
    ('nuts', 'flush'):        0.90,
    ('nuts', 'straight'):     0.92,
    ('nuts', 'set'):          0.90,
    ('nuts', 'full_house'):   0.80,
    ('nuts', 'two_pair'):     0.95,
    ('nuts', 'overpair'):     0.97,
    ('nuts', 'top_pair'):     0.97,
    ('nuts', 'middle_pair'):  0.98,
    ('nuts', 'combo_draw'):   0.72,
    ('nuts', 'flush_draw'):   0.78,
    ('nuts', 'oesd'):         0.80,
    ('nuts', 'gutshot'):      0.88,
    ('nuts', 'air'):          0.99,

    # Hero has full_house
    ('full_house', 'nuts'):      0.20,
    ('full_house', 'full_house'): 0.50,
    ('full_house', 'flush'):     0.90,
    ('full_house', 'straight'):  0.92,
    ('full_house', 'set'):       0.88,
    ('full_house', 'two_pair'):  0.94,
    ('full_house', 'overpair'):  0.96,
    ('full_house', 'top_pair'):  0.96,
    ('full_house', 'flush_draw'): 0.76,
    ('full_house', 'combo_draw'): 0.70,
    ('full_house', 'air'):       0.98,

    # Hero has flush
    ('flush', 'nuts'):       0.10,
    ('flush', 'full_house'): 0.10,
    ('flush', 'flush'):      0.50,
    ('flush', 'straight'):   0.72,
    ('flush', 'set'):        0.85,
    ('flush', 'two_pair'):   0.92,
    ('flush', 'overpair'):   0.94,
    ('flush', 'top_pair'):   0.94,
    ('flush', 'middle_pair'): 0.96,
    ('flush', 'flush_draw'): 0.68,
    ('flush', 'combo_draw'): 0.58,
    ('flush', 'oesd'):       0.78,
    ('flush', 'gutshot'):    0.86,
    ('flush', 'air'):        0.98,

    # Hero has straight
    ('straight', 'nuts'):        0.08,
    ('straight', 'full_house'):  0.08,
    ('straight', 'flush'):       0.28,
    ('straight', 'straight'):    0.50,
    ('straight', 'set'):         0.80,
    ('straight', 'two_pair'):    0.88,
    ('straight', 'overpair'):    0.91,
    ('straight', 'top_pair'):    0.92,
    ('straight', 'flush_draw'):  0.64,
    ('straight', 'combo_draw'):  0.55,
    ('straight', 'oesd'):        0.75,
    ('straight', 'air'):         0.97,

    # Hero has set
    ('set', 'nuts'):        0.10,
    ('set', 'full_house'):  0.12,
    ('set', 'flush'):       0.15,
    ('set', 'straight'):    0.20,
    ('set', 'set'):         0.50,
    ('set', 'two_pair'):    0.72,
    ('set', 'overpair'):    0.74,
    ('set', 'top_pair'):    0.78,
    ('set', 'middle_pair'): 0.82,
    ('set', 'flush_draw'):  0.65,
    ('set', 'combo_draw'):  0.58,
    ('set', 'oesd'):        0.67,
    ('set', 'gutshot'):     0.75,
    ('set', 'air'):         0.96,

    # Hero has two_pair
    ('two_pair', 'nuts'):        0.05,
    ('two_pair', 'full_house'):  0.06,
    ('two_pair', 'flush'):       0.08,
    ('two_pair', 'straight'):    0.12,
    ('two_pair', 'set'):         0.28,
    ('two_pair', 'two_pair'):    0.50,
    ('two_pair', 'overpair'):    0.62,
    ('two_pair', 'top_pair'):    0.72,
    ('two_pair', 'middle_pair'): 0.78,
    ('two_pair', 'flush_draw'):  0.60,
    ('two_pair', 'combo_draw'):  0.52,
    ('two_pair', 'oesd'):        0.63,
    ('two_pair', 'gutshot'):     0.72,
    ('two_pair', 'air'):         0.92,

    # Hero has overpair
    ('overpair', 'nuts'):        0.03,
    ('overpair', 'full_house'):  0.04,
    ('overpair', 'flush'):       0.06,
    ('overpair', 'straight'):    0.09,
    ('overpair', 'set'):         0.26,
    ('overpair', 'two_pair'):    0.38,
    ('overpair', 'overpair'):    0.50,
    ('overpair', 'top_pair'):    0.68,
    ('overpair', 'middle_pair'): 0.74,
    ('overpair', 'flush_draw'):  0.55,
    ('overpair', 'combo_draw'):  0.46,
    ('overpair', 'oesd'):        0.58,
    ('overpair', 'gutshot'):     0.68,
    ('overpair', 'air'):         0.90,

    # Hero has top_pair
    ('top_pair', 'nuts'):        0.03,
    ('top_pair', 'full_house'):  0.04,
    ('top_pair', 'flush'):       0.06,
    ('top_pair', 'straight'):    0.08,
    ('top_pair', 'set'):         0.22,
    ('top_pair', 'two_pair'):    0.28,
    ('top_pair', 'overpair'):    0.32,
    ('top_pair', 'top_pair'):    0.50,
    ('top_pair', 'middle_pair'): 0.65,
    ('top_pair', 'bottom_pair'): 0.72,
    ('top_pair', 'flush_draw'):  0.55,
    ('top_pair', 'combo_draw'):  0.45,
    ('top_pair', 'oesd'):        0.57,
    ('top_pair', 'gutshot'):     0.66,
    ('top_pair', 'air'):         0.86,

    # Hero has middle_pair
    ('middle_pair', 'nuts'):        0.02,
    ('middle_pair', 'flush'):       0.04,
    ('middle_pair', 'set'):         0.18,
    ('middle_pair', 'two_pair'):    0.22,
    ('middle_pair', 'overpair'):    0.26,
    ('middle_pair', 'top_pair'):    0.35,
    ('middle_pair', 'middle_pair'): 0.50,
    ('middle_pair', 'flush_draw'):  0.52,
    ('middle_pair', 'oesd'):        0.54,
    ('middle_pair', 'air'):         0.78,

    # Hero has flush_draw
    ('flush_draw', 'nuts'):        0.22,
    ('flush_draw', 'full_house'):  0.24,
    ('flush_draw', 'flush'):       0.32,
    ('flush_draw', 'straight'):    0.36,
    ('flush_draw', 'set'):         0.35,
    ('flush_draw', 'two_pair'):    0.40,
    ('flush_draw', 'overpair'):    0.45,
    ('flush_draw', 'top_pair'):    0.45,
    ('flush_draw', 'middle_pair'): 0.48,
    ('flush_draw', 'flush_draw'):  0.50,
    ('flush_draw', 'oesd'):        0.52,
    ('flush_draw', 'gutshot'):     0.55,
    ('flush_draw', 'air'):         0.60,

    # Hero has combo_draw (flush_draw + straight_draw)
    ('combo_draw', 'nuts'):        0.28,
    ('combo_draw', 'full_house'):  0.30,
    ('combo_draw', 'flush'):       0.42,
    ('combo_draw', 'straight'):    0.45,
    ('combo_draw', 'set'):         0.42,
    ('combo_draw', 'two_pair'):    0.48,
    ('combo_draw', 'overpair'):    0.54,
    ('combo_draw', 'top_pair'):    0.55,
    ('combo_draw', 'middle_pair'): 0.58,
    ('combo_draw', 'flush_draw'):  0.48,
    ('combo_draw', 'oesd'):        0.52,
    ('combo_draw', 'air'):         0.68,

    # Hero has oesd
    ('oesd', 'nuts'):        0.20,
    ('oesd', 'full_house'):  0.22,
    ('oesd', 'flush'):       0.25,
    ('oesd', 'straight'):    0.25,
    ('oesd', 'set'):         0.33,
    ('oesd', 'two_pair'):    0.37,
    ('oesd', 'overpair'):    0.42,
    ('oesd', 'top_pair'):    0.43,
    ('oesd', 'middle_pair'): 0.46,
    ('oesd', 'flush_draw'):  0.48,
    ('oesd', 'oesd'):        0.50,
    ('oesd', 'gutshot'):     0.55,
    ('oesd', 'air'):         0.55,

    # Hero has gutshot
    ('gutshot', 'nuts'):        0.12,
    ('gutshot', 'set'):         0.25,
    ('gutshot', 'two_pair'):    0.28,
    ('gutshot', 'overpair'):    0.32,
    ('gutshot', 'top_pair'):    0.34,
    ('gutshot', 'flush_draw'):  0.45,
    ('gutshot', 'oesd'):        0.45,
    ('gutshot', 'gutshot'):     0.50,
    ('gutshot', 'air'):         0.40,

    # Hero has air
    ('air', 'air'):          0.50,
    ('air', 'nuts'):         0.01,
    ('air', 'flush'):        0.02,
    ('air', 'set'):          0.04,
    ('air', 'two_pair'):     0.08,
    ('air', 'overpair'):     0.10,
    ('air', 'top_pair'):     0.14,
    ('air', 'flush_draw'):   0.40,
    ('air', 'oesd'):         0.45,
}

# Street equity multiplier for draw hands (draws have lower equity later)
_DRAW_STREET_MULT: Dict[str, float] = {
    'flop':  1.00,
    'turn':  0.80,  # on turn, draw has only 1 card to come
    'river': 0.00,  # river: draw either hit or missed; use hit/miss category
}

DRAW_CATEGORIES = frozenset({'flush_draw', 'combo_draw', 'oesd', 'gutshot', 'air'})


def get_equity(
    hero_category: str,
    villain_category: str,
    street: str = 'flop',
) -> float:
    """
    Get hero's approximate equity when hero has hero_category vs villain's villain_category.

    Args:
        hero_category:    Hero's hand category
        villain_category: Villain's hand category
        street:           'flop' / 'turn' / 'river'

    Returns:
        Hero equity [0.0, 1.0]
    """
    key = (hero_category, villain_category)
    if key in _EQUITY_TABLE:
        eq = _EQUITY_TABLE[key]
    else:
        # Try reversed lookup and invert
        rev_key = (villain_category, hero_category)
        if rev_key in _EQUITY_TABLE:
            eq = 1.0 - _EQUITY_TABLE[rev_key]
        else:
            eq = 0.50  # unknown matchup = assume even

    # Adjust for street: draws lose equity as fewer cards remain
    # Turn: ~1 card to come -> equity roughly halved vs flop
    # River: draw either hit (already made) or missed; pure miss = low equity
    if hero_category in DRAW_CATEGORIES:
        if street == 'turn':
            eq = max(0.0, eq - 0.12)   # flop 2-card draws -> 1-card on turn
        elif street == 'river':
            eq = max(0.0, eq - 0.20)   # river: miss is complete; slight fold equity only

    return round(min(1.0, max(0.0, eq)), 3)


def equity_advantage(
    hero_category: str,
    villain_category: str,
    street: str = 'flop',
) -> str:
    """Return qualitative equity advantage label."""
    eq = get_equity(hero_category, villain_category, street)
    if eq >= 0.80:
        return 'massive_hero_advantage'
    elif eq >= 0.65:
        return 'hero_ahead'
    elif eq >= 0.55:
        return 'slight_hero_advantage'
    elif eq >= 0.45:
        return 'neutral'
    elif eq >= 0.35:
        return 'slight_villain_advantage'
    else:
        return 'hero_behind'


@dataclass
class EquityMatchup:
    hero_category: str
    villain_category: str
    street: str
    hero_equity: float
    villain_equity: float
    advantage: str
    action_implications: List[str] = field(default_factory=list)
    tips: List[str] = field(default_factory=list)


def analyze_equity_matchup(
    hero_category: str = 'top_pair',
    villain_category: str = 'flush_draw',
    street: str = 'flop',
    pot_bb: float = 20.0,
    bet_size_pct: float = 0.60,
) -> EquityMatchup:
    """
    Analyze equity matchup and derive action implications.

    Args:
        hero_category:    Hero's hand category
        villain_category: Estimated villain hand category
        street:           Current street
        pot_bb:           Current pot in BB
        bet_size_pct:     Bet size as fraction of pot

    Returns:
        EquityMatchup
    """
    hero_eq = get_equity(hero_category, villain_category, street)
    adv = equity_advantage(hero_category, villain_category, street)

    action_implications = []
    tips = []

    if hero_eq >= 0.65:
        action_implications.append(
            f'Hero is ahead ({hero_eq:.0%} equity). Bet for value and deny equity.'
        )
    elif hero_eq >= 0.50:
        action_implications.append(
            f'Hero is slight favorite ({hero_eq:.0%}). Bet or check based on stack depth and opponent type.'
        )
    elif hero_eq >= 0.35:
        action_implications.append(
            f'Hero is behind ({hero_eq:.0%}). Consider pot control or folding to pressure.'
        )
    else:
        action_implications.append(
            f'Hero is far behind ({hero_eq:.0%}). Fold unless pot odds are excellent.'
        )

    # Draw-specific tips
    if villain_category in DRAW_CATEGORIES:
        tips.append(
            f'VILLAIN HAS DRAW: Bet to deny equity. '
            f'At {bet_size_pct:.0%} pot, villain needs {bet_size_pct/(1+bet_size_pct):.0%} equity. '
            f'Hero equity: {hero_eq:.0%}. {"BET: hero is favorite." if hero_eq >= 0.55 else "CHECK: hero behind even vs draw."}'
        )
    elif hero_category in DRAW_CATEGORIES:
        tips.append(
            f'HERO HAS DRAW: Hero needs to hit to win. '
            f'Current equity: {hero_eq:.0%}. '
            f'{"Semi-bluff viable: equity above break-even." if hero_eq >= 0.33 else "Pot odds needed to continue."}'
        )

    if adv in ('massive_hero_advantage', 'hero_ahead'):
        tips.append(
            f'BUILD POT: Hero dominates {villain_category}. '
            f'Large bet (65-90%) for maximum value. '
            f'Villain needs to call with only {1-hero_eq:.0%} equity.'
        )
    elif adv in ('slight_villain_advantage', 'hero_behind'):
        tips.append(
            f'POT CONTROL: Hero is behind {villain_category} ({hero_eq:.0%}). '
            f'Check or bet small on {"draw" if hero_category in DRAW_CATEGORIES else "bluff"} streets. '
            f'Fold to large pressure unless pot odds justify continued play.'
        )

    tips.append(
        f'MATCHUP: {hero_category} vs {villain_category} on {street} = {hero_eq:.0%} hero equity. '
        f'Category: {adv.replace("_", " ")}.'
    )

    return EquityMatchup(
        hero_category=hero_category,
        villain_category=villain_category,
        street=street,
        hero_equity=hero_eq,
        villain_equity=round(1.0 - hero_eq, 3),
        advantage=adv,
        action_implications=action_implications,
        tips=tips,
    )


def hvhe_one_liner(r: EquityMatchup) -> str:
    return (
        f'[HVHE {r.hero_category}|{r.villain_category}|{r.street}] '
        f'hero_eq={r.hero_equity:.0%} | {r.advantage}'
    )
