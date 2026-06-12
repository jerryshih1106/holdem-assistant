"""
Table Image Tracker (table_image_tracker.py)

Tracks which hands hero has shown at the table, classifies hero's current
table image, and generates strategy adjustments that exploit how villains
are likely perceiving hero.

Core insight:
  If hero has shown bluffs recently → villains call more → bet wider for value,
    stop bluffing pure air.
  If hero has shown only monsters → villains fold more → bluff more, slow-play less.
  If hero is new to table (no showdowns) → use population-based defaults.

Table image categories:
  'tight_passive'    : rarely seen, only showed strong hands / folds
  'tight_aggressive' : few showdowns, all strong hands
  'loose_aggressive' : many showdowns, mix of bluffs and value
  'bluff_heavy'      : multiple caught bluffs shown
  'value_heavy'      : multiple strong hands shown, no bluffs caught
  'unknown'          : < 3 showdowns, insufficient data

Strategy adjustments when image is established:
  bluff_heavy    → raise value threshold, stop bluffing air
  value_heavy    → add more bluffs, overbet value (get called lighter)
  tight_passive  → widen opening range, steal more (exploits fold equity)
  loose_aggressive → tighten preflop, fewer bluffs (called too light)

Usage:
    from poker.table_image_tracker import TableImageTracker, ImageResult
    tracker = TableImageTracker()
    tracker.record_showdown(hand_class='top_pair', was_bluff=False, won=True)
    tracker.record_showdown(hand_class='air', was_bluff=True, won=False)
    result = tracker.analyze()
    print(result.image_label, result.bluff_freq_adj)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class ShowdownRecord:
    """One hand hero showed at showdown."""
    hand_class: str     # 'air', 'draw', 'pair', 'two_pair', 'set', etc.
    was_bluff: bool     # hero was bluffing (bet with weak hand)
    won: bool           # hero won the pot
    street: str         # 'flop', 'turn', 'river'
    pot_size_bb: float  # pot size for weighting


@dataclass
class ImageResult:
    """Hero's current table image and recommended adjustments."""
    # Sample info
    n_showdowns: int
    n_bluffs_caught: int     # hero bluffed and villain called + won
    n_value_shown: int       # hero showed strong hands
    n_wins: int

    # Image classification
    image_label: str         # 'tight_passive', 'tight_aggressive', etc.
    image_score: float       # -1 = super tight, +1 = super loose/laggy
    confidence: str          # 'high' (5+ SD), 'medium' (3-4), 'low' (<3)

    # Recommended adjustments
    bluff_freq_adj: float    # delta to bluff frequency (-0.15 = bluff 15% less)
    value_bet_adj: float     # delta to value bet threshold (negative = value wider)
    steal_freq_adj: float    # delta to steal frequency
    call_adj: float          # delta to calling range (positive = call tighter)
    overbet_adj: float       # delta to overbet frequency (positive = overbet more)

    # Narrative
    image_description: str
    top_adjustment: str      # most important thing to change
    recommendations: List[str] = field(default_factory=list)

    # Raw showdowns
    showdowns: List[ShowdownRecord] = field(default_factory=list)


class TableImageTracker:
    """Tracks hero's showdowns and computes table image."""

    def __init__(self):
        self._showdowns: List[ShowdownRecord] = []

    def record_showdown(
        self,
        hand_class: str,
        was_bluff: bool,
        won: bool,
        street: str = 'river',
        pot_size_bb: float = 10.0,
    ) -> None:
        """Record a hand hero showed at showdown."""
        self._showdowns.append(ShowdownRecord(
            hand_class=hand_class,
            was_bluff=was_bluff,
            won=won,
            street=street,
            pot_size_bb=pot_size_bb,
        ))

    def reset(self) -> None:
        """Clear all showdowns (new table/session)."""
        self._showdowns.clear()

    def n_showdowns(self) -> int:
        return len(self._showdowns)

    def analyze(self) -> 'ImageResult':
        return analyze_table_image(self._showdowns)


_STRONG_HANDS = {'full_house', 'flush', 'straight', 'set', 'two_pair', 'top_pair_strong', 'tptk'}
_WEAK_HANDS   = {'air', 'nothing', 'draw', 'missed_draw'}
_MEDIUM_HANDS = {'top_pair', 'top_pair_weak', 'middle_pair', 'bottom_pair', 'pair'}


def _classify_hand_strength(hand_class: str) -> str:
    hc = hand_class.lower()
    if hc in _STRONG_HANDS or 'set' in hc or 'flush' in hc or 'straight' in hc:
        return 'strong'
    if hc in _WEAK_HANDS or 'air' in hc or 'miss' in hc:
        return 'weak'
    return 'medium'


def analyze_table_image(showdowns: List[ShowdownRecord]) -> ImageResult:
    """
    Compute hero's current table image from showdown history.

    Args:
        showdowns: List of hands hero showed at showdown

    Returns:
        ImageResult with adjustments
    """
    n = len(showdowns)
    if n == 0:
        return ImageResult(
            n_showdowns=0, n_bluffs_caught=0, n_value_shown=0, n_wins=0,
            image_label='unknown',
            image_score=0.0,
            confidence='low',
            bluff_freq_adj=0.0,
            value_bet_adj=0.0,
            steal_freq_adj=0.0,
            call_adj=0.0,
            overbet_adj=0.0,
            image_description='No showdowns yet — use population-based defaults.',
            top_adjustment='Play standard ranges until image is established.',
            showdowns=showdowns,
        )

    n_bluffs   = sum(1 for s in showdowns if s.was_bluff)
    n_caught   = sum(1 for s in showdowns if s.was_bluff and not s.won)
    n_value    = sum(1 for s in showdowns if not s.was_bluff and
                     _classify_hand_strength(s.hand_class) == 'strong')
    n_wins     = sum(1 for s in showdowns if s.won)

    bluff_ratio = n_bluffs / n if n > 0 else 0.0
    value_ratio = n_value / n if n > 0 else 0.0
    win_ratio   = n_wins / n if n > 0 else 0.0

    # Image score: +1 = very loose/bluff-heavy, -1 = very tight/value-heavy
    image_score = bluff_ratio * 1.5 - value_ratio * 0.8
    image_score = max(-1.0, min(1.0, image_score))

    # Classify image
    if n < 3:
        label = 'unknown'
    elif n_caught >= 2 or bluff_ratio >= 0.40:
        label = 'bluff_heavy'
    elif value_ratio >= 0.60 and n_caught == 0:
        label = 'value_heavy'
    elif bluff_ratio < 0.15 and value_ratio >= 0.40 and win_ratio >= 0.55:
        label = 'tight_aggressive'
    elif bluff_ratio < 0.10 and win_ratio < 0.45:
        label = 'tight_passive'
    elif bluff_ratio >= 0.20:
        label = 'loose_aggressive'
    else:
        label = 'balanced'

    confidence = 'high' if n >= 5 else ('medium' if n >= 3 else 'low')

    # Recommended adjustments
    bluff_adj  = 0.0
    value_adj  = 0.0
    steal_adj  = 0.0
    call_adj   = 0.0
    overbet_adj = 0.0

    if label == 'bluff_heavy':
        # Villains think we bluff a lot → they call more
        # → stop bluffing air, value-bet wider (get called lighter)
        bluff_adj   = -0.20  # bluff 20% less
        value_adj   = -0.10  # lower value threshold (bet thinner for value)
        overbet_adj = +0.15  # overbet value (they call)
        steal_adj   = -0.10  # steal less (they 3-bet/defend more)
        call_adj    = 0.0

    elif label == 'value_heavy':
        # Villains think we only have it → they fold to bets
        # → add bluffs, slow-play less
        bluff_adj   = +0.20  # bluff 20% more
        value_adj   = +0.05  # raise value threshold (bet less thinly)
        overbet_adj = -0.10  # don't overbet (they fold to big bets)
        steal_adj   = +0.15  # steal relentlessly (they fold)
        call_adj    = 0.0

    elif label == 'tight_passive':
        # Rarely seen → they don't know what to think
        bluff_adj   = +0.10  # can bluff more
        steal_adj   = +0.20  # steal wide
        call_adj    = 0.0

    elif label == 'tight_aggressive':
        # Seen as solid TAG
        bluff_adj   = +0.05  # slight bluff increase (get credit)
        steal_adj   = +0.10  # steal with authority
        overbet_adj = +0.10

    elif label == 'loose_aggressive':
        # Seen as laggy
        bluff_adj   = -0.10
        value_adj   = -0.15
        steal_adj   = -0.05

    # Image description
    desc_map = {
        'bluff_heavy':      f'Bluff-heavy image ({n_caught} bluffs caught). Villains will call you down. Exploit: value-bet thinner, stop air bluffs.',
        'value_heavy':      f'Value-heavy image ({n_value} monsters shown). Villains fold to bets. Exploit: add bluffs, slow-play less.',
        'tight_aggressive': f'Tight-aggressive image. Villains respect your bets. Exploit: 3-bet more light, steal wide.',
        'tight_passive':    f'Tight-passive image. Villains unsure of your range. Exploit: steal more, add light 3-bets.',
        'loose_aggressive': f'Loose-aggressive image ({n_bluffs} bluffs shown). Villains call light. Exploit: value-bet wide, reduce bluffs.',
        'balanced':         f'Balanced image. No major adjustments needed — maintain discipline.',
        'unknown':          f'Insufficient showdown data ({n} SD). Use population defaults.',
    }
    description = desc_map.get(label, f'Image: {label}')

    top_adj_map = {
        'bluff_heavy':      'Stop bluffing air — villains are calling more. Only bluff with strong equity or good blockers.',
        'value_heavy':      'Add more bluffs to your range. Villains fold too much to your bets — exploit it.',
        'tight_aggressive': 'Increase 3-bet frequency and steal range. Your tight image gives your aggression credibility.',
        'tight_passive':    'Open stealing range wider. Villains assume you only play strong hands.',
        'loose_aggressive': 'Value-bet much thinner. Villains are calling you down with weak hands.',
        'balanced':         'Maintain balanced play. Look for specific villain tendencies to exploit.',
        'unknown':          'Play standard strategy until you establish an image.',
    }
    top_adj = top_adj_map.get(label, 'Maintain discipline.')

    # Build recommendation list
    recs = [top_adj]
    if abs(bluff_adj) >= 0.15:
        direction = 'less' if bluff_adj < 0 else 'more'
        recs.append(f'Bluff {abs(bluff_adj):.0%} {direction} in spots where you normally would bluff.')
    if abs(steal_adj) >= 0.10:
        direction = 'wider' if steal_adj > 0 else 'tighter'
        recs.append(f'Open stealing {direction} — villains adjust their defense to your image.')
    if overbet_adj > 0.10:
        recs.append('Consider overbets on rivers — villains are calling you anyway, maximize value.')
    if n < 3:
        recs.append(f'Only {n} showdown(s) — image not established. Revisit after 3+ showdowns.')

    return ImageResult(
        n_showdowns=n,
        n_bluffs_caught=n_caught,
        n_value_shown=n_value,
        n_wins=n_wins,
        image_label=label,
        image_score=round(image_score, 2),
        confidence=confidence,
        bluff_freq_adj=round(bluff_adj, 2),
        value_bet_adj=round(value_adj, 2),
        steal_freq_adj=round(steal_adj, 2),
        call_adj=round(call_adj, 2),
        overbet_adj=round(overbet_adj, 2),
        image_description=description,
        top_adjustment=top_adj,
        recommendations=recs,
        showdowns=showdowns,
    )


def image_one_liner(result: ImageResult) -> str:
    """Single-line overlay summary."""
    adj = f'bluff{result.bluff_freq_adj:+.0%} steal{result.steal_freq_adj:+.0%}'
    return (
        f'Image [{result.image_label}] ({result.n_showdowns} SD, conf={result.confidence}) | '
        f'{adj} | {result.top_adjustment[:40]}'
    )
