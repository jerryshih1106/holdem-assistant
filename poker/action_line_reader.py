"""
Action Line Reader (action_line_reader.py)

Interprets villain's betting action sequence across streets to estimate
their most likely hand range and category.  The key skill in hand reading:
translate what villain DOES into what villain HAS.

Common action lines and their meanings:
  Preflop open → Flop c-bet → Turn c-bet → River bet:
    3-street barreler: polarized (nuts or bluffs)

  Preflop open → Flop c-bet → Turn check → River bet:
    Turn checked back (medium hand, pot control), river bet = value or blocker

  Preflop open → Flop check → Turn bet:
    Delayed c-bet: typically strong (set/two-pair checking flop, betting turn)
    OR backdoor draw that developed

  Preflop call → Flop check → Turn bet (donk):
    Donk lead: often two pair/set on a card that helps caller; sometimes float

  Any street raise (after betting):
    Strong hand or draw on a board where draws are present

  Preflop open → Flop c-bet large → Turn check → River small bet:
    Likely a missed draw bluffing small; turned weak hand

Usage:
    from poker.action_line_reader import read_action_line, ActionLineReading
    reading = read_action_line(
        actions=[('preflop','open',3.0), ('flop','cbet',0.60), ('turn','check',0),
                 ('river','bet',0.33)],
        board_type='dry',
        villain_vpip=0.25,
        villain_af=2.0,
    )
    print(reading.likely_range, reading.hand_category_estimate)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# Action tuple: (street, action_type, size_pct_or_bb)
# action_type: 'open', 'cbet', 'check', 'call', 'raise', 'bet', 'fold', 'shove'
Action = Tuple[str, str, float]


_AGGRESSIVE = {'cbet', 'bet', 'raise', 'open', 'shove'}
_PASSIVE    = {'check', 'call', 'fold'}

_BOARD_TYPE_WEIGHTS = {
    'dry':      {'value': 1.3, 'bluff': 0.7, 'draw': 0.2},
    'wet':      {'value': 1.0, 'bluff': 1.0, 'draw': 1.5},
    'monotone': {'value': 0.8, 'bluff': 0.7, 'draw': 0.8},
    'paired':   {'value': 1.1, 'bluff': 0.8, 'draw': 0.5},
    'semi_wet': {'value': 1.1, 'bluff': 0.9, 'draw': 1.2},
}


def _aggression_score(actions: List[Action]) -> float:
    """Score 0-1: fraction of postflop actions that are aggressive."""
    postflop = [(s, a, sz) for s, a, sz in actions if s != 'preflop']
    if not postflop:
        return 0.5
    agg = sum(1 for s, a, sz in postflop if a in _AGGRESSIVE)
    return agg / len(postflop)


def _avg_size(actions: List[Action]) -> float:
    """Average bet size (as fraction of pot) across all bets/cbets."""
    sizes = [sz for s, a, sz in actions if a in _AGGRESSIVE and sz > 0]
    return sum(sizes) / len(sizes) if sizes else 0.5


def _line_pattern(actions: List[Action]) -> str:
    """Reduce action sequence to a compact pattern string."""
    parts = []
    for s, a, sz in actions:
        if a in ('open', 'cbet', 'bet'):
            label = 'B'
        elif a == 'raise':
            label = 'R'
        elif a == 'check':
            label = 'X'
        elif a == 'call':
            label = 'C'
        elif a == 'shove':
            label = 'S'
        elif a == 'fold':
            label = 'F'
        else:
            label = '?'
        parts.append(label)
    return ''.join(parts)


# Pattern → (hand category, confidence, description)
_PATTERNS: dict = {
    # 3 streets of aggression
    'BBB':   ('value_or_bluff',  'medium', '3-barrel: nuts or pure bluff (polarized)'),
    'BBXB':  ('value_or_blocker','medium', 'Bet-bet-check-bet: pot control turn, river blocker or thin value'),
    'BXB':   ('strong_or_draw',  'high',   'Bet-check-bet: delayed barrel; often strong made or draw that improved'),
    'BXBR':  ('nut_or_semi',     'high',   'Turn check-call, river bet-raise: very strong (set, two pair+)'),
    # Turn delayed cbet
    'XB':    ('delayed_value',   'medium', 'Check-bet: trap or missed c-bet getting aggressive on turn'),
    'XBB':   ('value_heavy',     'high',   'Check-bet-bet: 2+ streets aggression after checking; typically strong'),
    # River only bet
    'XXB':   ('bluff_or_thin',   'medium', 'Two checks then river bet: blocker bet, missed draw, or thin value'),
    'XXBR':  ('air_or_monster',  'medium', 'Raise on river after two checks: typically nuts or pure air'),
    # Check-raise
    'XR':    ('strong_or_semi',  'high',   'Check-raise: strong made hand or strong semi-bluff (sets, OESD+FD)'),
    'BXRR':  ('nuts',            'high',   'Flop c-bet called, turn check, river raise: very strong'),
    # Calls
    'BC':    ('medium_wide',     'low',    'Villain called one bet: wide range, medium hands and draws'),
    'BCC':   ('medium_narrow',   'medium', 'Two calls without raising: typically medium-strength, giving up or waiting'),
    # Size tells
    'BsB':   ('value',           'medium', 'Small bet then bet: merged value range, thin bets'),
    'BlB':   ('polarized',       'medium', 'Large bet then bet: polarized strong value or draw bluff'),
}


def _classify_size(size_pct: float) -> str:
    """Classify bet size."""
    if size_pct <= 0.0:
        return 'none'
    elif size_pct <= 0.35:
        return 'small'
    elif size_pct <= 0.70:
        return 'medium'
    else:
        return 'large'


def _pattern_match(pattern: str) -> tuple:
    """Find best matching pattern from _PATTERNS."""
    if pattern in _PATTERNS:
        return _PATTERNS[pattern]
    # Try prefix matches
    for length in (4, 3, 2):
        if len(pattern) >= length and pattern[:length] in _PATTERNS:
            return _PATTERNS[pattern[:length]]
    return ('unknown', 'low', 'Unusual line — insufficient data')


@dataclass
class ActionLineReading:
    """Estimated villain range from action sequence analysis."""
    # Pattern analysis
    action_pattern: str            # compact pattern like 'BXB'
    aggression_score: float        # 0-1 fraction of bets/raises
    avg_bet_size_pct: float        # average bet size relative to pot

    # Range estimate
    hand_category_estimate: str    # 'value', 'bluff', 'draw', 'medium', etc.
    likely_range: str              # human-readable range description
    confidence: str                # 'high', 'medium', 'low'

    # Strength estimate
    estimated_equity_vs_hero: float  # villain's estimated equity
    is_likely_bluffing: bool
    is_likely_value: bool

    # Street-by-street notes
    street_notes: List[str] = field(default_factory=list)

    # Action recommendation for hero
    hero_recommendation: str = ''
    reasoning: str = ''


def read_action_line(
    actions: List[Action],
    board_type: str = 'semi_wet',
    villain_vpip: float = 0.25,
    villain_af: float = 2.0,
    villain_wtsd: float = 0.32,
    hero_equity: float = 0.50,
    pot_bb: float = 10.0,
    current_bet_bb: float = 0.0,
) -> ActionLineReading:
    """
    Estimate villain's hand category from their betting line.

    Args:
        actions:       List of (street, action_type, size_pct) tuples
        board_type:    'dry', 'wet', 'monotone', 'paired', 'semi_wet'
        villain_vpip:  Villain's VPIP (higher = wider range = more draws/bluffs)
        villain_af:    Aggression factor (higher = more likely their bets = value)
        villain_wtsd:  Went-to-showdown frequency
        hero_equity:   Hero's equity (used for hero recommendation)
        pot_bb:        Current pot (used for EV estimates)
        current_bet_bb: If villain just bet, size in BB

    Returns:
        ActionLineReading
    """
    pattern = _line_pattern(actions)
    agg_score = _aggression_score(actions)
    avg_size = _avg_size(actions)

    hand_cat, confidence, description = _pattern_match(pattern)

    # Board-type adjustments
    board_weights = _BOARD_TYPE_WEIGHTS.get(board_type, _BOARD_TYPE_WEIGHTS['semi_wet'])

    # Adjust for villain type
    if villain_vpip > 0.35:
        # Loose player: more likely to have draws/weak hands
        bluff_adjust = +0.15
        value_adjust = -0.05
    elif villain_vpip < 0.20:
        # Tight player: more likely to have value
        bluff_adjust = -0.20
        value_adjust = +0.20
    else:
        bluff_adjust = 0.0
        value_adjust = 0.0

    # High AF = bets for value; low AF = passive player betting = stronger
    if villain_af >= 3.0:
        # High aggression: bets include more bluffs
        bluff_adjust += 0.10
    elif villain_af <= 1.0:
        # Passive: when they bet, it's value
        value_adjust += 0.20

    # Estimate villain's equity vs hero
    if hand_cat == 'value_or_bluff':
        # Polarized line: start at 50%, pull toward value for tight/passive, toward bluff for loose/aggro
        est_equity = 0.50
        est_equity += value_adjust * 0.30
        est_equity -= bluff_adjust * 0.20
        if villain_af >= 3.0:
            est_equity -= 0.08   # high aggression = more bluffs in range
        elif villain_af <= 1.0:
            est_equity += 0.15   # passive player betting = strong
    elif 'bluff' in hand_cat or 'air' in hand_cat:
        est_equity = 0.20 + bluff_adjust * 0.3
    elif 'value' in hand_cat or 'strong' in hand_cat or 'nut' in hand_cat:
        est_equity = 0.70 + value_adjust * 0.2
    elif 'draw' in hand_cat or 'semi' in hand_cat:
        est_equity = 0.35 + board_weights.get('draw', 1.0) * 0.05
    else:
        est_equity = 0.50

    est_equity = max(0.05, min(0.95, est_equity))

    is_bluffing = est_equity < 0.35
    is_value    = est_equity > 0.55

    # ── Likely range text ────────────────────────────────────────────────────
    range_map = {
        'value_or_bluff':   'Polarized: top 15% (two pair+) or bottom 15% (missed draws)',
        'value_or_blocker': 'Value hand (top pair+) or blocker bet with medium holding',
        'strong_or_draw':   'Strong made hand (set/two pair) or combo draw',
        'delayed_value':    'Strong hand checking flop for deception (set/two pair)',
        'value_heavy':      'Value-heavy: two pair or better with high probability',
        'bluff_or_thin':    'Possible missed draw or thin value (top pair weak kicker)',
        'strong_or_semi':   'Check-raise: strong hand (set) or strong semi-bluff (FD+SD)',
        'nuts':             'Near-nut hand: two pair, set, straight or better',
        'medium_wide':      'Wide medium range: top pair through strong draw',
        'medium_narrow':    'Narrowing to: medium hand (top pair, two pair), giving up unlikely',
        'value':            'Value hand: merged thin value bets',
        'polarized':        'Polarized: strong value or bluff',
        'air_or_monster':   'Either nut hand or complete air (check-raise bluff)',
        'nut_or_semi':      'Nut hand or strong semi-bluff with equity',
        'value_or_bluff':   'Polarized range: very strong or complete air',
        'unknown':          'Insufficient data — consider villain stats and board',
    }
    likely_range = range_map.get(hand_cat, description)

    # ── Street notes ─────────────────────────────────────────────────────────
    street_notes = []
    for i, (street, action, size) in enumerate(actions):
        size_label = _classify_size(size)
        if action in _AGGRESSIVE and size > 0:
            street_notes.append(
                f'{street.capitalize()}: {action} {size:.0%} pot ({size_label}) → '
                f'{"value/semi" if size_label == "large" else "probing/merged"}'
            )
        elif action == 'check':
            street_notes.append(
                f'{street.capitalize()}: check → '
                f'{"pot control or trap" if i > 0 else "check-back or positional"}'
            )
        elif action == 'shove':
            street_notes.append(f'{street.capitalize()}: SHOVE → nut hand or pure bluff')
        elif action == 'raise':
            street_notes.append(f'{street.capitalize()}: raise → strong hand or semi-bluff')

    # ── Hero recommendation ───────────────────────────────────────────────────
    pot_odds = current_bet_bb / (pot_bb + current_bet_bb) if current_bet_bb > 0 else 0
    if hero_equity > est_equity + 0.10 and hero_equity > pot_odds:
        hero_rec = 'CALL / raise — hero has significant equity edge over estimated villain range'
    elif hero_equity < est_equity - 0.10:
        hero_rec = 'FOLD — villain appears to have equity advantage; avoid committing more chips'
    elif is_bluffing and hero_equity >= pot_odds:
        hero_rec = 'CALL — villain likely bluffing based on action line; pot odds justify call'
    elif is_value and hero_equity < 0.45:
        hero_rec = 'FOLD — villain likely has value hand; do not commit without strong equity'
    else:
        hero_rec = 'MARGINAL — use pot odds and specific reads to decide'

    reasoning = (
        f'Pattern: {pattern} ({hand_cat}, conf={confidence}). '
        f'Board: {board_type}. Villain VPIP={villain_vpip:.0%} AF={villain_af:.1f}. '
        f'Agg score={agg_score:.0%} avg_size={avg_size:.0%}. '
        f'Est villain equity={est_equity:.0%}. '
        f'Hero equity={hero_equity:.0%}. '
        f'Likely: {likely_range[:50]}.'
    )

    return ActionLineReading(
        action_pattern=pattern,
        aggression_score=round(agg_score, 2),
        avg_bet_size_pct=round(avg_size, 2),
        hand_category_estimate=hand_cat,
        likely_range=likely_range,
        confidence=confidence,
        estimated_equity_vs_hero=round(est_equity, 2),
        is_likely_bluffing=is_bluffing,
        is_likely_value=is_value,
        street_notes=street_notes,
        hero_recommendation=hero_rec,
        reasoning=reasoning,
    )


def action_line_one_liner(result: ActionLineReading) -> str:
    """Single-line overlay summary."""
    return (
        f'Line [{result.action_pattern}] → {result.hand_category_estimate} '
        f'(conf={result.confidence}) | '
        f'est_eq={result.estimated_equity_vs_hero:.0%} | '
        f'{result.hero_recommendation[:30]}'
    )
