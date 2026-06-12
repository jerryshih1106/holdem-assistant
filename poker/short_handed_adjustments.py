"""
Short-Handed Adjustments (short_handed_adjustments.py)

Adjusts strategy for short-handed play (2-5 players).
Short-handed poker is fundamentally different from full-ring:
  - Ranges widen dramatically (fewer players = less chance of strong hands)
  - Positional value increases (fewer players between you and button)
  - Aggression is more rewarded (fewer players to wake up with monsters)
  - Value thresholds lower (TPWK can be best hand 3-handed)

TABLE SIZE ADJUSTMENTS:
  6-MAX to FULL RING:        Many players use the same ranges -- WRONG
  6-MAX (6 players):         Standard ranges for online cash games
  5-HANDED:                  +5-8% to open/call ranges; widen 3-bet
  4-HANDED:                  +15% ranges; steal more; defend BB wide
  3-HANDED:                  +25% ranges; any ace/pair/broadway is value
  HEADS-UP (2 players):       SB opens 70%+; BB defends 50%+; extreme ranges

POSITION ADJUSTMENTS (short-handed):
  SB (short-handed):          Opens more; position disadvantage is less punishing
  BTN (short-handed):         Super dominant; steal very wide
  BB (short-handed):          Defend extremely wide vs short table

DISTINCT FROM:
  preflop_equilibrium_chart.py:  6-max/full-ring ranges
  heads_up_advisor.py:           Heads-up specific (2 player)
  THIS MODULE:                   Table-size-specific range adjustments;
                                 widening curves for 3/4/5-handed play

Usage:
    from poker.short_handed_adjustments import adjust_for_table_size, TableSizeAdjustment, sha_one_liner

    result = adjust_for_table_size(
        table_size=4,
        hero_position='btn',
        hero_hand_category='middle_pair',
        action_facing='none',
        gto_open_pct=0.45,
        gto_call_pct=0.30,
        gto_3bet_pct=0.10,
        street='preflop',
    )
    print(sha_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Widening multipliers by table size (relative to 6-max baseline)
RANGE_WIDEN_FACTOR = {
    9: 0.75,   # 9-max: tighter than 6-max
    8: 0.80,
    7: 0.88,
    6: 1.00,   # baseline
    5: 1.10,
    4: 1.22,
    3: 1.40,
    2: 1.65,   # heads-up
}

# Position open-range adjustments by table size
SB_OPEN_TABLE = {
    6: 0.42, 5: 0.50, 4: 0.58, 3: 0.65, 2: 0.72
}
BTN_OPEN_TABLE = {
    6: 0.48, 5: 0.55, 4: 0.62, 3: 0.70, 2: 0.75
}
BB_DEFEND_TABLE = {
    6: 0.44, 5: 0.50, 4: 0.58, 3: 0.65, 2: 0.72
}


def _widen_factor(table_size: int) -> float:
    return RANGE_WIDEN_FACTOR.get(max(2, min(9, table_size)), 1.00)


def _adjusted_open_pct(
    gto_open_pct: float,
    hero_position: str,
    table_size: int,
) -> float:
    factor = _widen_factor(table_size)
    pos_table = {
        'btn': BTN_OPEN_TABLE, 'sb': SB_OPEN_TABLE,
    }
    if hero_position in pos_table and table_size in pos_table[hero_position]:
        return round(pos_table[hero_position][table_size], 3)
    adjusted = min(0.90, gto_open_pct * factor)
    return round(adjusted, 3)


def _adjusted_call_pct(
    gto_call_pct: float,
    hero_position: str,
    table_size: int,
) -> float:
    factor = _widen_factor(table_size)
    if hero_position == 'bb' and table_size in BB_DEFEND_TABLE:
        return round(BB_DEFEND_TABLE[table_size], 3)
    adjusted = min(0.85, gto_call_pct * factor)
    return round(adjusted, 3)


def _adjusted_3bet_pct(
    gto_3bet_pct: float,
    table_size: int,
) -> float:
    factor = _widen_factor(table_size)
    adjusted = min(0.35, gto_3bet_pct * factor)
    return round(adjusted, 3)


def _value_threshold(table_size: int, hero_position: str) -> str:
    """Lowest hand category that is a value bet."""
    if table_size <= 3:
        return 'weak_pair_or_better'
    elif table_size == 4:
        return 'middle_pair_or_better'
    elif table_size == 5:
        return 'top_pair_weak_kicker_or_better'
    else:
        return 'top_pair_good_kicker_or_better'


def _aggression_level(table_size: int) -> str:
    """Recommended aggression level for the table size."""
    if table_size <= 2:
        return 'maximum'
    elif table_size <= 3:
        return 'very_high'
    elif table_size <= 4:
        return 'high'
    elif table_size <= 5:
        return 'moderately_high'
    else:
        return 'standard'


@dataclass
class TableSizeAdjustment:
    # Inputs
    table_size: int
    hero_position: str
    hero_hand_category: str
    action_facing: str
    gto_open_pct: float
    gto_call_pct: float
    gto_3bet_pct: float
    street: str

    # Adjustments
    widen_factor: float
    adjusted_open_pct: float
    adjusted_call_pct: float
    adjusted_3bet_pct: float
    value_threshold: str
    aggression_level: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def adjust_for_table_size(
    table_size: int = 6,
    hero_position: str = 'btn',
    hero_hand_category: str = 'middle_pair',
    action_facing: str = 'none',
    gto_open_pct: float = 0.45,
    gto_call_pct: float = 0.30,
    gto_3bet_pct: float = 0.10,
    street: str = 'preflop',
) -> TableSizeAdjustment:
    """
    Adjust strategy for short-handed play.

    Args:
        table_size:        Number of players at table (2-9)
        hero_position:     Position ('btn'/'sb'/'bb'/'utg'/etc.)
        hero_hand_category: Current hand category
        action_facing:     'none' / 'raise' / '3bet'
        gto_open_pct:      GTO open range at 6-max for this position
        gto_call_pct:      GTO call range at 6-max
        gto_3bet_pct:      GTO 3-bet range at 6-max
        street:            'preflop' / 'flop' / 'turn' / 'river'

    Returns:
        TableSizeAdjustment
    """
    factor = _widen_factor(table_size)
    adj_open = _adjusted_open_pct(gto_open_pct, hero_position, table_size)
    adj_call = _adjusted_call_pct(gto_call_pct, hero_position, table_size)
    adj_3bet = _adjusted_3bet_pct(gto_3bet_pct, table_size)
    val_thresh = _value_threshold(table_size, hero_position)
    aggression = _aggression_level(table_size)

    table_label = {
        2: 'HEADS_UP', 3: '3-HANDED', 4: '4-HANDED', 5: '5-HANDED',
        6: '6-MAX', 7: '7-HANDED', 8: '8-HANDED', 9: '9-MAX',
    }.get(table_size, f'{table_size}-HANDED')

    verdict = (
        f'[SHA {table_label}|{hero_position}] '
        f'open={adj_open:.0%} call={adj_call:.0%} 3bet={adj_3bet:.0%} '
        f'| widen={factor:.2f}x aggr={aggression}'
    )

    reasoning = (
        f'Short-handed adjustment for {table_size}-player table at {hero_position}. '
        f'Widen factor={factor:.2f}x vs 6-max baseline. '
        f'Open={adj_open:.0%} (was {gto_open_pct:.0%}). '
        f'Call={adj_call:.0%} (was {gto_call_pct:.0%}). '
        f'3-bet={adj_3bet:.0%} (was {gto_3bet_pct:.0%}). '
        f'Value threshold: {val_thresh}. Aggression: {aggression}.'
    )

    tips = []

    tips.append(
        f'RANGE WIDENING: {table_size}-handed table requires {factor:.2f}x wider ranges '
        f'than 6-max. Open {adj_open:.0%} (GTO={gto_open_pct:.0%}), '
        f'Call {adj_call:.0%} (GTO={gto_call_pct:.0%}), '
        f'3-bet {adj_3bet:.0%} (GTO={gto_3bet_pct:.0%}).'
    )

    tips.append(
        f'VALUE THRESHOLD: At {table_size} players, {val_thresh} is a value bet. '
        f'Villain\'s range is weaker short-handed -- your relative hand strength improves.'
    )

    if table_size <= 3:
        tips.append(
            f'3-HANDED SPECIFIC: Most hands become playable. '
            f'Any ace, any pair, suited connectors, broadway cards are all worth playing. '
            f'Aggression level: {aggression.upper()}. Bet and raise more freely.'
        )

    if table_size == 2:
        tips.append(
            f'HEADS-UP SPECIFIC: SB opens 70%+, BB defends 50%+. '
            f'TPTK, top pair, and even middle pair can be strong hands HU. '
            f'Aggression dominates -- check-calling is often exploitable.'
        )

    if hero_position in ('sb', 'btn') and table_size <= 4:
        tips.append(
            f'POSITIONAL DOMINANCE: {hero_position.upper()} is extremely powerful short-handed. '
            f'Steal blind aggressively. '
            f'Open {adj_open:.0%} of hands from this position at {table_size}-handed.'
        )

    if hero_position == 'bb' and table_size <= 4:
        tips.append(
            f'BB DEFENSE: Short-handed BB must defend very wide. '
            f'Defend {adj_call:.0%} of hands from BB. '
            f'Villain\'s open range is wide -- you have good odds to call and realize equity.'
        )

    return TableSizeAdjustment(
        table_size=table_size,
        hero_position=hero_position,
        hero_hand_category=hero_hand_category,
        action_facing=action_facing,
        gto_open_pct=gto_open_pct,
        gto_call_pct=gto_call_pct,
        gto_3bet_pct=gto_3bet_pct,
        street=street,
        widen_factor=factor,
        adjusted_open_pct=adj_open,
        adjusted_call_pct=adj_call,
        adjusted_3bet_pct=adj_3bet,
        value_threshold=val_thresh,
        aggression_level=aggression,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sha_one_liner(r: TableSizeAdjustment) -> str:
    return (
        f'[SHA {r.table_size}h|{r.hero_position}] '
        f'open={r.adjusted_open_pct:.0%} call={r.adjusted_call_pct:.0%} '
        f'3bet={r.adjusted_3bet_pct:.0%} | widen={r.widen_factor:.2f}x'
    )
