"""
Villain Sizing Tell Analyzer (villain_sizing_tell_analyzer.py)

Interprets villain's bet sizing patterns to extract hand-strength
and range information in real time.

THEORY:
  Live players (and many recreational online players) have systematic
  sizing tells that reveal hand strength:

  OVERBET (>pot): Often polarized -- nuts or air. In live games, often = strength.
  LARGE BET (75-100% pot): Strong hand OR big semi-bluff. Villain confident.
  STANDARD BET (50-70% pot): Value range; top pair through sets.
  SMALL BET (25-45% pot): Blocking bet (weak) OR slow-play (trapping).
  MIN BET (<25% pot): Almost always blocking; villain has marginal made hand.
  POT-SIZED BET: Often value by unsophisticated players; rarely a bluff.

  SIZE-HAND CORRELATIONS (population reads):
  - Consistent large sizing = value range (unsophisticated players)
  - Variable sizing based on street = strength indicator
  - Sudden overbet after passivity = very strong hand (slowplay)
  - Sudden small bet after aggression = giving up (trapping or blocking)

  SIZING HISTORY (multi-street patterns):
  - Small-Small-Large: slowplay turned value; villain has strong made hand
  - Large-Large-Small: second and third barrels became blocking bet
  - Increasing sizes: building pot with strong hand
  - Decreasing sizes: giving up or blocking
  - Min-bet all streets: calling station / confused player

  VILLAIN TYPE MODIFIERS:
  - Fish/Rec: sizing tells more reliable (less mixing)
  - Reg: sizing mixes; less reliable tells
  - LAG: deliberate sizing variation; be careful
  - Live players: more reliable sizing tells than online

DISTINCT FROM:
  bet_tell.py:              General bet tell analysis
  villain_reads.py:         HUD-based villain reads
  THIS MODULE:              SIZING-SPECIFIC tells; multi-street patterns;
                            consistency analysis; implied hand range from sizes.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Sizing categories
def _size_category(size_frac: float) -> str:
    if size_frac < 0.25:
        return 'min_bet'
    elif size_frac < 0.45:
        return 'small'
    elif size_frac < 0.55:
        return 'half_pot'
    elif size_frac < 0.75:
        return 'standard'
    elif size_frac < 1.05:
        return 'large'
    elif size_frac < 1.50:
        return 'overbet'
    else:
        return 'jam_overbet'


# Hand range implications by size category
SIZE_RANGE_IMPLICATION: dict = {
    'min_bet':    'blocking_bet_or_slowplay',  # marginal made hand OR trapping
    'small':      'blocking_or_thin_value',    # capped range; medium strength
    'half_pot':   'standard_value_range',      # top pair through two pair
    'standard':   'value_or_semi_bluff',       # standard range; hard to read
    'large':      'strong_value_or_draw',      # strong hand or big draw
    'overbet':    'polarized_nutted_or_air',   # nuts or bluff; rare medium
    'jam_overbet': 'nuts_or_full_tilt',        # very strong or tilting
}

# Confidence in sizing tell by villain type
TELL_CONFIDENCE: dict = {
    'fish':           0.85,
    'rec':            0.80,
    'calling_station': 0.75,
    'live_casual':    0.82,
    'reg':            0.45,
    'lag':            0.35,
    'tag':            0.50,
    'nit':            0.60,
}

# Multi-street pattern analysis
MULTI_STREET_PATTERNS: dict = {
    'small_small_large':  ('slowplay_hit_river', 0.80),
    'large_large_small':  ('giving_up_or_blocking', 0.75),
    'increasing':         ('building_value_pot', 0.70),
    'decreasing':         ('giving_up_or_blocking', 0.65),
    'consistent_large':   ('value_betting_range', 0.80),
    'consistent_small':   ('blocking_or_station', 0.70),
    'min_all':            ('confused_or_station', 0.65),
    'overbet_after_small': ('slowplay_monster', 0.85),
}


def _detect_pattern(size_fracs: list) -> str:
    if not size_fracs:
        return 'insufficient_data'
    cats = [_size_category(s) for s in size_fracs]
    if len(cats) == 1:
        return cats[0]
    if all(c == 'min_bet' for c in cats):
        return 'min_all'
    if cats[-1] in ('overbet', 'jam_overbet') and all(c in ('small', 'half_pot', 'min_bet') for c in cats[:-1]):
        return 'overbet_after_small'
    sizes = list(size_fracs)
    if len(sizes) == 3 and sizes[0] < sizes[1] and sizes[1] < sizes[2]:
        return 'increasing'
    if len(sizes) == 3 and sizes[0] > sizes[1] and sizes[1] > sizes[2]:
        return 'decreasing'
    if len(sizes) >= 2 and sizes[-1] < sizes[-2] * 0.6:
        return 'large_large_small'
    if len(sizes) >= 2 and sizes[-1] > sizes[-2] * 1.5:
        return 'small_small_large'
    if all(s >= 0.65 for s in sizes):
        return 'consistent_large'
    if all(s <= 0.40 for s in sizes):
        return 'consistent_small'
    return 'mixed_no_clear_pattern'


@dataclass
class SizingTellResult:
    current_bet_frac: float
    size_category: str
    range_implication: str
    betting_history: list
    pattern: str
    pattern_read: str
    pattern_confidence: float
    villain_type: str
    adjusted_confidence: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_sizing_tell(
    current_bet_frac: float = 0.67,
    betting_history: Optional[list] = None,
    villain_type: str = 'rec',
    street: str = 'river',
    pot_bb: float = 20.0,
) -> SizingTellResult:
    """
    Analyze villain's sizing tell.

    Args:
        current_bet_frac:  Current bet as fraction of pot
        betting_history:   Previous bets as fractions of pot (oldest first)
        villain_type:      Villain archetype
        street:            Current street
        pot_bb:            Current pot in BB

    Returns:
        SizingTellResult
    """
    if betting_history is None:
        betting_history = []

    all_sizes = list(betting_history) + [current_bet_frac]
    size_cat = _size_category(current_bet_frac)
    range_impl = SIZE_RANGE_IMPLICATION.get(size_cat, 'unknown')
    pattern = _detect_pattern(all_sizes)
    pattern_read, base_conf = MULTI_STREET_PATTERNS.get(
        pattern, ('no_clear_pattern', 0.50)
    )
    tell_conf = TELL_CONFIDENCE.get(villain_type, 0.55)
    adj_conf = round(base_conf * tell_conf, 3)
    bet_bb = round(pot_bb * current_bet_frac, 1)

    verdict = (
        f'[STA {size_cat}|{street}|{villain_type}] '
        f'{range_impl} | conf={adj_conf:.0%} | '
        f'pattern={pattern}'
    )

    reasoning = (
        f'Villain bet {current_bet_frac:.0%}pot ({bet_bb:.1f}BB). '
        f'Size category: {size_cat}. '
        f'Range implication: {range_impl}. '
        f'History: {betting_history}. Pattern: {pattern}. '
        f'Pattern read: {pattern_read}. '
        f'Confidence (adjusted for {villain_type}): {adj_conf:.0%}.'
    )

    tips = []

    tips.append(
        f'SIZE TELL: {current_bet_frac:.0%}pot = {size_cat}. '
        f'Range implication: {range_impl}. '
        f'{"RELIABLE tell vs " + villain_type + "." if adj_conf >= 0.60 else "UNRELIABLE tell vs " + villain_type + "; may be mixing."}'
    )

    if pattern != 'insufficient_data' and len(all_sizes) >= 2:
        tips.append(
            f'MULTI-STREET PATTERN: {pattern} -> {pattern_read}. '
            f'Confidence: {adj_conf:.0%}. '
            f'{"Adjust range read accordingly." if adj_conf >= 0.55 else "Insufficient data to rely on pattern."}'
        )

    if size_cat == 'min_bet':
        tips.append(
            f'MIN BET ({current_bet_frac:.0%}pot): Almost always blocking bet. '
            f'Villain has marginal made hand; cannot call a raise. '
            f'RAISE if you have equity; villain will fold marginal holdings.'
        )
    elif size_cat == 'overbet':
        tips.append(
            f'OVERBET ({current_bet_frac:.0%}pot): Polarized range -- '
            f'{"likely strong (unsophisticated " + villain_type + " rarely bluffs overbets)." if villain_type in ("fish","rec","live_casual") else "could be nuts or bluff; need blockers to call."}'
        )
    elif size_cat in ('small', 'half_pot') and street == 'river':
        tips.append(
            f'SMALL RIVER BET ({current_bet_frac:.0%}pot): Either blocking bet (weak) '
            f'or thin value with made hand. '
            f'{"Call wide; villain capping range." if villain_type in ("fish","rec") else "Proceed with normal equity assessment."}'
        )

    if villain_type in ('lag', 'reg') and adj_conf < 0.50:
        tips.append(
            f'WARNING: Sizing tells unreliable vs {villain_type} (conf={adj_conf:.0%}). '
            f'Good players deliberately vary sizing. '
            f'Rely on range analysis and board texture instead.'
        )

    return SizingTellResult(
        current_bet_frac=current_bet_frac,
        size_category=size_cat,
        range_implication=range_impl,
        betting_history=betting_history,
        pattern=pattern,
        pattern_read=pattern_read,
        pattern_confidence=base_conf,
        villain_type=villain_type,
        adjusted_confidence=adj_conf,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sta_one_liner(r: SizingTellResult) -> str:
    return (
        f'[STA {r.size_category}|{r.villain_type}] '
        f'{r.range_implication} | '
        f'conf={r.adjusted_confidence:.0%} | {r.pattern}'
    )
