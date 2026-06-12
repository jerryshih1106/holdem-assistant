"""
Preflop 3-Bet Polarization Guide (preflop_3bet_polarization_guide.py)

Teaches the VALUE vs BLUFF composition of a 3-bet range -- the POLARIZATION
principle: 3-bet range should contain strong value hands and selected bluffs,
with the middle-strength hands (TT-QQ) often calling instead of 3-betting.

THEORY:
  3-BET RANGE STRUCTURE:
  A polarized 3-bet range consists of:
  1. VALUE: Top hands (AA, KK, QQ, AKs) -- always 3-bet for value
  2. BLUFF: Selected hands with good attributes (blockers, playability)
  3. CALL: Middle hands that play well in position but don't 3-bet

  WHY POLARIZE (not 3-bet all strong hands):
  - If you 3-bet QQ-TT, your call range becomes capped (no overpairs)
  - Villain can float your 3-bets knowing you lack AA-QQ in call range
  - Mixing QQ into call range protects your call range AND your 3-bet range

  BLUFF HAND SELECTION FOR 3-BET:
  Good 3-bet bluffs have 1+ of these properties:
  1. Blocker to villain's value range (Ace blocks AA; King blocks KK)
  2. Good playability when called (suited connectors can make flushes/straights)
  3. Dominates part of villain's 3-bet call range

  BEST 3-BET BLUFFS BY POSITION:
  - From BTN/CO: A5s-A2s (A-blocker + flush potential)
  - Vs LP steal: A2s-A5s, K2s-K5s (block their value range)
  - Vs EP open: A4s, A3s (block; discard plays if 4-bet comes)
  - Squeeze spots: Any A-x suited, 65s+ (equity if called)

  3-BET SIZING:
  IP: 3.0x opener's raise (or 7-9BB standard)
  OOP: 3.5x opener's raise (need larger to discourage calls)
  vs Limpers: 4x + 1 per limper

  MERGED vs POLARIZED 3-BET:
  vs Fish/Rec: MERGED range (3-bet all strong hands; bluffs less needed)
  vs TAG/REG: POLARIZED (true bluff hands needed; middling hands call)
  vs Tight/Nit: SLIGHTLY MERGED (nit folds too much; can 3-bet wider value)

DISTINCT FROM:
  hero_3bet_range_optimizer.py:  3-bet range optimization
  threbet_bluff.py:              3-bet bluff selection
  threebet_sizing.py:            3-bet sizing
  scenario_range_advisor.py:     Scenario range advice
  THIS MODULE:                   POLARIZATION PRINCIPLE; value vs bluff ratio;
                                 call range protection; hand category assignment.
"""

from dataclasses import dataclass, field
from typing import List, Dict


VALUE_3BET_ALWAYS: Dict[str, list] = {
    'btn': ['AA', 'KK', 'QQ', 'AKs', 'AKo'],
    'co':  ['AA', 'KK', 'QQ', 'AKs', 'AKo'],
    'mp':  ['AA', 'KK', 'QQ', 'AKs'],
    'utg': ['AA', 'KK', 'QQ', 'AKs'],
    'sb':  ['AA', 'KK', 'QQ', 'AKs', 'AKo', 'JJ'],
}

BLUFF_3BET_POOL: Dict[str, list] = {
    'btn': ['A5s', 'A4s', 'A3s', 'A2s', 'K5s', 'K4s', 'JTs', 'T9s', '98s'],
    'co':  ['A5s', 'A4s', 'A3s', 'JTs', 'T9s'],
    'mp':  ['A5s', 'A4s', 'JTs'],
    'utg': ['A5s', 'A4s'],
    'sb':  ['A5s', 'A4s', 'A3s', 'A2s', 'K5s', 'JTs', 'T9s', '98s', '87s'],
}

CALL_3BET_POOL: Dict[str, list] = {
    'btn': ['JJ', 'TT', '99', 'AQs', 'AJs', 'KQs', 'QJs', 'JTs'],
    'co':  ['JJ', 'TT', 'AQs', 'AJs', 'KQs'],
    'mp':  ['JJ', 'TT', 'AQs'],
    'utg': ['JJ', 'TT'],
    'sb':  ['TT', '99', 'AQs', 'AJs'],
}

VILLAIN_RANGE_ADJUSTMENT: dict = {
    'fish':   {'value_add': ['JJ', 'TT', 'AQs'], 'bluff_pct': 0.30},
    'rec':    {'value_add': ['JJ'], 'bluff_pct': 0.40},
    'nit':    {'value_add': [], 'bluff_pct': 0.60},
    'lag':    {'value_add': [], 'bluff_pct': 0.50},
    'reg':    {'value_add': [], 'bluff_pct': 0.50},
}

BLUFF_RATIO_TARGET: float = 0.33


def _bluff_count_needed(value_count: int) -> int:
    return max(1, round(value_count * BLUFF_RATIO_TARGET))


def _range_type(villain_type: str) -> str:
    if villain_type in ('fish', 'rec'):
        return 'merged'
    return 'polarized'


def _3bet_hands(position: str, villain_type: str) -> Dict[str, list]:
    pos = position.lower()
    value = list(VALUE_3BET_ALWAYS.get(pos, VALUE_3BET_ALWAYS['mp']))
    bluffs = list(BLUFF_3BET_POOL.get(pos, BLUFF_3BET_POOL['mp']))
    calls  = list(CALL_3BET_POOL.get(pos, CALL_3BET_POOL['mp']))

    adj = VILLAIN_RANGE_ADJUSTMENT.get(villain_type, {})
    if _range_type(villain_type) == 'merged':
        value.extend(adj.get('value_add', []))
        bluffs = bluffs[:2]

    n_bluffs = _bluff_count_needed(len(value))
    selected_bluffs = bluffs[:n_bluffs]

    return {
        'value': value,
        'bluff': selected_bluffs,
        'call':  calls,
    }


def _sizing(position: str, opener_size_bb: float) -> float:
    if position in ('sb', 'bb'):
        return round(opener_size_bb * 3.5, 1)
    return round(opener_size_bb * 3.0, 1)


@dataclass
class ThreeBetPolarizationResult:
    position: str
    villain_type: str

    value_hands: List[str]
    bluff_hands: List[str]
    call_hands: List[str]

    range_type: str
    n_value: int
    n_bluffs: int
    bluff_ratio: float
    sizing_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_3bet_polarization(
    position: str = 'btn',
    villain_type: str = 'reg',
    opener_size_bb: float = 3.0,
    stack_bb: float = 100.0,
) -> ThreeBetPolarizationResult:
    """
    Build a polarized 3-bet range with value/bluff/call assignments.

    Args:
        position:       Hero position ('utg','mp','co','btn','sb','bb')
        villain_type:   Villain type ('fish','rec','nit','lag','reg')
        opener_size_bb: Opener's raise size in BB
        stack_bb:       Effective stack in BB

    Returns:
        ThreeBetPolarizationResult
    """
    hand_sets = _3bet_hands(position, villain_type)
    rtype = _range_type(villain_type)
    sizing = _sizing(position, opener_size_bb)

    if stack_bb <= 20:
        hand_sets['bluff'] = []

    n_val   = len(hand_sets['value'])
    n_bluff = len(hand_sets['bluff'])
    ratio   = round(n_bluff / n_val, 2) if n_val > 0 else 0.0

    verdict = (
        f'[3BP {position.upper()}|{villain_type}|{rtype}] '
        f'value={n_val} bluff={n_bluff} '
        f'ratio={ratio:.2f} size={sizing:.1f}BB'
    )

    reasoning = (
        f'3-bet polarization: {position.upper()} vs {villain_type}. '
        f'Range type: {rtype}. '
        f'Value: {hand_sets["value"]}. '
        f'Bluffs: {hand_sets["bluff"]}. '
        f'Call: {hand_sets["call"]}. '
        f'Bluff ratio={ratio:.2f} (target={BLUFF_RATIO_TARGET:.2f}). '
        f'Sizing={sizing:.1f}BB.'
    )

    tips = []

    tips.append(
        f'3-BET RANGE ({rtype.upper()}): {n_val} value hands + {n_bluff} bluffs. '
        f'Bluff ratio={ratio:.2f} (target ~{BLUFF_RATIO_TARGET:.2f}). '
        f'Value: {", ".join(hand_sets["value"][:5])}{"..." if len(hand_sets["value"])>5 else ""}.'
    )

    tips.append(
        f'3-BET SIZING: {sizing:.1f}BB ({position.upper()}). '
        f'IP=3.0x open; OOP=3.5x open. '
        f'Bluff hands: {", ".join(hand_sets["bluff"]) if hand_sets["bluff"] else "none at this stack/position"}.'
    )

    if villain_type in ('fish', 'rec'):
        tips.append(
            f'VS {villain_type.upper()} (MERGED RANGE): 3-bet all strong hands including JJ-TT. '
            f'Fish/Rec call 3-bets too wide -- no need for bluffs to balance. '
            f'Eliminate most bluffs; focus on value extraction.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT (BLUFF MORE): Nit folds to 3-bets frequently. '
            f'3-bet wider with Ax suited bluffs -- high fold equity. '
            f'Bluff ratio {ratio:.2f} may be slightly low vs nit.'
        )

    tips.append(
        f'CALL RANGE PROTECTION: Keep {", ".join(hand_sets["call"][:3])} in your CALL range. '
        f'If you 3-bet all strong hands, your call range becomes capped and exploitable. '
        f'Protect by mixing JJ/TT into call range from {position.upper()}.'
    )

    return ThreeBetPolarizationResult(
        position=position,
        villain_type=villain_type,
        value_hands=hand_sets['value'],
        bluff_hands=hand_sets['bluff'],
        call_hands=hand_sets['call'],
        range_type=rtype,
        n_value=n_val,
        n_bluffs=n_bluff,
        bluff_ratio=ratio,
        sizing_bb=sizing,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tbp_one_liner(r: ThreeBetPolarizationResult) -> str:
    return (
        f'[3BP {r.position.upper()}|{r.villain_type}|{r.range_type}] '
        f'value={r.n_value} bluff={r.n_bluffs} '
        f'ratio={r.bluff_ratio:.2f} size={r.sizing_bb:.1f}BB'
    )
