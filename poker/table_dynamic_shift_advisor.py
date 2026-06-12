"""
Table Dynamic Shift Advisor (table_dynamic_shift_advisor.py)

When significant events happen at the table (big pot won/lost, new player
joins, player tilts, or stack distributions change dramatically), you must
adjust strategy to exploit the new dynamic.

THEORY:
  TABLE DYNAMIC SHIFTS AND THEIR EFFECTS:

  1. BIG_POT_WON (hero wins a big pot):
     - Hero's image appears strong; opponents may tighten up
     - Use image to steal more; 3-bet wider in next 10-15 hands
     - Opponents may also call/bluff-catch more (targeting the big stack)
     - Adjust: increase steal freq +10%; tighten 3-bet calling range slightly

  2. BIG_POT_LOST (hero loses a big pot):
     - Hero may be on tilt; opponents attack
     - Emotional control is the first priority
     - Opponents may open wider/bluff more into perceived tilt
     - Adjust: tighten preflop -15%; take 3-bet pots away less often

  3. NEW_FISH_JOINS (weak player sits down):
     - Table dynamic changes; must position near fish
     - Fish will pay off draws and calls wide
     - Reduce bluff frequency; increase thin value betting
     - Adjust: left of fish seat is highest EV; play more hands near them

  4. FISH_LEAVES (fish busts or leaves):
     - Table toughens; EV drops
     - Consider leaving for better game
     - Reduce speculative hand range; tighten

  5. PLAYER_TILTS (villain goes on tilt):
     - Tilt player bets erratically, calls too wide, plays too fast
     - Target tilt player directly; isolate with marginal hands
     - Avoid bluffing tilt player; they call too much
     - Adjust: isolate +15% range; no bluffs vs tilt player

  6. STACK_REDISTRIBUTION (many short stacks created):
     - Short stacks affect pot geometry and push-fold dynamics
     - Tighten 3-bet ranges (may face all-in from short stacks)
     - Adjust: reduce 3-bet frequency; call more to set implied odds

  7. AGGRESSION_SPIKE (table suddenly becomes more aggressive):
     - Multiple players 3-betting and raising frequently
     - Tighten opening range; trap more; reduce blind steals
     - Look for squeeze opportunities

DISTINCT FROM:
  villain_adaptation_tracker.py:  Individual player adaptation
  table_image_tracker.py:         Hero's image tracking
  table_analyzer.py:              Table analysis
  THIS MODULE:                    EVENT-DRIVEN adjustments; specific table SHIFTS;
                                  magnitude and duration of adjustment; multi-player effects.
"""

from dataclasses import dataclass, field
from typing import List


SHIFT_ADJUSTMENTS: dict = {
    'big_pot_won': {
        'steal_freq_adj':    +0.10,
        'open_range_adj':    +0.03,
        '3bet_freq_adj':     +0.03,
        'bluff_freq_adj':    +0.05,
        'thin_value_adj':    +0.00,
        'duration_hands':    15,
    },
    'big_pot_lost': {
        'steal_freq_adj':    -0.10,
        'open_range_adj':    -0.05,
        '3bet_freq_adj':     -0.05,
        'bluff_freq_adj':    -0.08,
        'thin_value_adj':    -0.05,
        'duration_hands':    20,
    },
    'new_fish_joins': {
        'steal_freq_adj':    +0.00,
        'open_range_adj':    +0.05,
        '3bet_freq_adj':     -0.03,
        'bluff_freq_adj':    -0.12,
        'thin_value_adj':    +0.15,
        'duration_hands':    999,
    },
    'fish_leaves': {
        'steal_freq_adj':    -0.03,
        'open_range_adj':    -0.05,
        '3bet_freq_adj':     +0.00,
        'bluff_freq_adj':    +0.05,
        'thin_value_adj':    -0.10,
        'duration_hands':    30,
    },
    'player_tilts': {
        'steal_freq_adj':    +0.05,
        'open_range_adj':    +0.03,
        '3bet_freq_adj':     +0.00,
        'bluff_freq_adj':    -0.15,
        'thin_value_adj':    +0.12,
        'duration_hands':    40,
    },
    'stack_redistribution': {
        'steal_freq_adj':    -0.05,
        'open_range_adj':    -0.03,
        '3bet_freq_adj':     -0.08,
        'bluff_freq_adj':    +0.00,
        'thin_value_adj':    +0.05,
        'duration_hands':    25,
    },
    'aggression_spike': {
        'steal_freq_adj':    -0.12,
        'open_range_adj':    -0.05,
        '3bet_freq_adj':     -0.05,
        'bluff_freq_adj':    -0.05,
        'thin_value_adj':    +0.05,
        'duration_hands':    20,
    },
}

SHIFT_SEVERITY: dict = {
    'big_pot_won':          'moderate',
    'big_pot_lost':         'high',
    'new_fish_joins':       'high',
    'fish_leaves':          'moderate',
    'player_tilts':         'high',
    'stack_redistribution': 'low',
    'aggression_spike':     'moderate',
}


def _adjustment_magnitude(adj_dict: dict) -> float:
    abs_sum = sum(abs(v) for k, v in adj_dict.items() if k != 'duration_hands')
    return round(abs_sum, 3)


def _priority_actions(shift_type: str, adj: dict) -> List[str]:
    actions = []
    if adj.get('bluff_freq_adj', 0) < -0.10:
        actions.append('REDUCE_BLUFFS')
    if adj.get('thin_value_adj', 0) > 0.10:
        actions.append('INCREASE_THIN_VALUE')
    if adj.get('steal_freq_adj', 0) > 0.08:
        actions.append('STEAL_MORE')
    if adj.get('steal_freq_adj', 0) < -0.08:
        actions.append('STEAL_LESS')
    if adj.get('open_range_adj', 0) < -0.03:
        actions.append('TIGHTEN_OPENS')
    if adj.get('open_range_adj', 0) > 0.03:
        actions.append('LOOSEN_OPENS')
    if not actions:
        actions.append('MINOR_ADJUSTMENTS')
    return actions


@dataclass
class TableDynamicResult:
    shift_type: str
    severity: str
    duration_hands: int

    steal_freq_adj: float
    open_range_adj: float
    threbet_freq_adj: float
    bluff_freq_adj: float
    thin_value_adj: float

    adjustment_magnitude: float
    priority_actions: List[str]

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_table_dynamic_shift(
    shift_type: str = 'new_fish_joins',
    hands_since_shift: int = 0,
    pot_size_bb: float = 50.0,
) -> TableDynamicResult:
    """
    Recommend strategic adjustments after a table dynamic shift.

    Args:
        shift_type:        Type of shift ('big_pot_won','big_pot_lost',
                           'new_fish_joins','fish_leaves','player_tilts',
                           'stack_redistribution','aggression_spike')
        hands_since_shift: How many hands have passed since the event
        pot_size_bb:       Size of the triggering pot (if applicable)

    Returns:
        TableDynamicResult
    """
    adj = SHIFT_ADJUSTMENTS.get(shift_type, SHIFT_ADJUSTMENTS['aggression_spike'])
    severity = SHIFT_SEVERITY.get(shift_type, 'moderate')
    duration = adj['duration_hands']
    magnitude = _adjustment_magnitude(adj)
    priority = _priority_actions(shift_type, adj)

    decay = max(0.0, 1.0 - hands_since_shift / max(duration, 1))

    verdict = (
        f'[TDS {shift_type}|{severity}|{hands_since_shift}h ago] '
        f'{priority[0]} decay={decay:.0%} '
        f'steal={adj["steal_freq_adj"]:+.0%} bluff={adj["bluff_freq_adj"]:+.0%}'
    )

    reasoning = (
        f'Table dynamic shift: {shift_type} ({severity} severity). '
        f'Duration: ~{duration} hands. '
        f'Adjustments: steal={adj["steal_freq_adj"]:+.0%} open={adj["open_range_adj"]:+.0%} '
        f'3bet={adj["3bet_freq_adj"]:+.0%} bluff={adj["bluff_freq_adj"]:+.0%} '
        f'thin_value={adj["thin_value_adj"]:+.0%}. '
        f'Priority: {priority}. Magnitude={magnitude:.3f}.'
    )

    tips = []

    tips.append(
        f'TABLE SHIFT: {shift_type.upper().replace("_"," ")} detected ({severity} severity). '
        f'Adjustments active for ~{duration} hands. '
        f'Priority: {", ".join(priority)}.'
    )

    if shift_type == 'new_fish_joins':
        tips.append(
            f'FISH AT TABLE: Reduce bluffs ({adj["bluff_freq_adj"]:+.0%}); '
            f'increase thin value ({adj["thin_value_adj"]:+.0%}). '
            f'Try to sit LEFT of fish (acts after them). '
            f'Play more hands in position vs fish seat; avoid OOP bluffs.'
        )
    elif shift_type == 'player_tilts':
        tips.append(
            f'TILT PLAYER: ISO raise wider; no bluffs vs them ({adj["bluff_freq_adj"]:+.0%}). '
            f'Bet for thin value ({adj["thin_value_adj"]:+.0%}); they call with weak range. '
            f'Avoid fancy plays -- simple value extraction maximizes EV.'
        )
    elif shift_type == 'big_pot_lost':
        tips.append(
            f'EMOTIONAL CONTROL: Tighten preflop ({adj["open_range_adj"]:+.0%}). '
            f'Reduce bluffs and steals ({adj["bluff_freq_adj"]:+.0%}). '
            f'Take a break if feeling tilt; playing tight restores positive EV.'
        )
    elif shift_type == 'aggression_spike':
        tips.append(
            f'AGGRESSION SPIKE: Table has become 3-bet heavy. '
            f'Reduce steals ({adj["steal_freq_adj"]:+.0%}); tighten opens ({adj["open_range_adj"]:+.0%}). '
            f'Look for squeeze spots; trap with premiums; call wider in position.'
        )
    else:
        tips.append(
            f'Adjustments: steal={adj["steal_freq_adj"]:+.0%} | '
            f'open={adj["open_range_adj"]:+.0%} | '
            f'3bet={adj["3bet_freq_adj"]:+.0%} | '
            f'bluff={adj["bluff_freq_adj"]:+.0%} | '
            f'thin_value={adj["thin_value_adj"]:+.0%}.'
        )

    return TableDynamicResult(
        shift_type=shift_type,
        severity=severity,
        duration_hands=duration,
        steal_freq_adj=adj['steal_freq_adj'],
        open_range_adj=adj['open_range_adj'],
        threbet_freq_adj=adj['3bet_freq_adj'],
        bluff_freq_adj=adj['bluff_freq_adj'],
        thin_value_adj=adj['thin_value_adj'],
        adjustment_magnitude=magnitude,
        priority_actions=priority,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tds_one_liner(r: TableDynamicResult) -> str:
    return (
        f'[TDS {r.shift_type}|{r.severity}] '
        f'{r.priority_actions[0]} '
        f'steal={r.steal_freq_adj:+.0%} bluff={r.bluff_freq_adj:+.0%} '
        f'{r.duration_hands}h'
    )
