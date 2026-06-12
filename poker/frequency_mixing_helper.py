"""
Frequency Mixing Helper (frequency_mixing_helper.py)

Helps poker players implement MIXED STRATEGIES in practice.
GTO often requires mixing: e.g., "bet 60%, check 40% with top pair on dry flop."
But humans must decide: bet OR check this specific hand. This module
converts a GTO frequency into a concrete bet/check decision for the current hand.

THEORY:
  Mixed strategies are required because:
  - If you always bet top pair, villain can over-fold against you
  - If you always check top pair, villain can probe freely
  - Mixing at the right frequency maximizes EV against GTO-aware opponents

  IMPLEMENTATION VIA FINGERPRINTING:
    Instead of true randomness (impractical at the table), we use
    deterministic pseudo-randomization based on:
    - Hand cards (suit/rank)
    - Board texture
    - Pot size bucket
    - Street
    This makes the strategy appear random to opponents but is consistent
    for the same inputs.

    FORMULA:
    fingerprint = (card1_rank * 17 + card2_rank * 31 + board_hash * 97 +
                   street_num * 13 + pot_bucket * 7) % 100
    if fingerprint < freq * 100: action = 'bet'
    else: action = 'check'

  FREQUENCY TABLE (GTO approximate):
    - Top pair dry IP: bet 65%
    - Top pair wet IP: bet 45%
    - Top pair OOP: bet 50%
    - Set dry IP: bet 70%, check 30% (trap)
    - Flush draw IP: bet 55%
    - Air dry IP: bet 20%
    - Two pair dry: bet 80%
    - Overpair dry: bet 65%

  WHY FINGERPRINTING WORKS:
    The inputs are unique per hand, so the output appears random.
    Across many hands, the distribution converges to GTO frequencies.
    Unlike "always bet top pair," different top pair hands will take
    different actions based on card ranks/suits.

DISTINCT FROM:
  mixed_strategy_advisor.py:  Shows GTO frequencies (not the decision)
  gto_deviation.py:           Audits deviations from GTO
  THIS MODULE:                Converts a GTO frequency into the ACTUAL DECISION
                              for THIS specific hand via deterministic pseudo-randomization.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


# GTO base frequencies for common spots
# (hand_category, board_texture, position) -> bet_frequency
GTO_MIX_FREQ: Dict[tuple, float] = {
    # Value hands
    ('nuts',       'dry',     'ip'):  0.80,
    ('nuts',       'dry',     'oop'): 0.75,
    ('nuts',       'wet',     'ip'):  0.70,
    ('nuts',       'wet',     'oop'): 0.65,
    ('set',        'dry',     'ip'):  0.70,  # trap check 30%
    ('set',        'dry',     'oop'): 0.60,  # more trapping OOP
    ('set',        'wet',     'ip'):  0.85,  # protect on wet
    ('set',        'wet',     'oop'): 0.78,
    ('two_pair',   'dry',     'ip'):  0.80,
    ('two_pair',   'dry',     'oop'): 0.72,
    ('two_pair',   'wet',     'ip'):  0.88,
    ('two_pair',   'wet',     'oop'): 0.80,
    ('overpair',   'dry',     'ip'):  0.65,
    ('overpair',   'dry',     'oop'): 0.55,
    ('overpair',   'wet',     'ip'):  0.72,
    ('overpair',   'wet',     'oop'): 0.60,
    ('top_pair',   'dry',     'ip'):  0.65,
    ('top_pair',   'dry',     'oop'): 0.50,
    ('top_pair',   'wet',     'ip'):  0.50,
    ('top_pair',   'wet',     'oop'): 0.38,
    ('middle_pair','dry',     'ip'):  0.30,
    ('middle_pair','dry',     'oop'): 0.22,
    ('middle_pair','wet',     'ip'):  0.20,
    ('middle_pair','wet',     'oop'): 0.15,
    # Draw hands
    ('combo_draw', 'wet',     'ip'):  0.72,
    ('combo_draw', 'wet',     'oop'): 0.60,
    ('flush_draw', 'wet',     'ip'):  0.50,
    ('flush_draw', 'wet',     'oop'): 0.38,
    ('flush_draw', 'dry',     'ip'):  0.35,
    ('flush_draw', 'dry',     'oop'): 0.28,
    ('oesd',       'dry',     'ip'):  0.38,
    ('oesd',       'dry',     'oop'): 0.28,
    ('oesd',       'wet',     'ip'):  0.45,
    ('oesd',       'wet',     'oop'): 0.35,
    ('gutshot',    'dry',     'ip'):  0.22,
    ('gutshot',    'dry',     'oop'): 0.15,
    ('air',        'dry',     'ip'):  0.20,
    ('air',        'dry',     'oop'): 0.12,
    ('air',        'wet',     'ip'):  0.15,
    ('air',        'wet',     'oop'): 0.08,
}

DEFAULT_FREQ = 0.50


def _get_gto_freq(hand_category: str, board_texture: str, position: str) -> float:
    key = (hand_category, board_texture, position)
    if key in GTO_MIX_FREQ:
        return GTO_MIX_FREQ[key]
    # Try matching without texture
    for pos in (position, 'ip', 'oop'):
        for tex in (board_texture, 'dry', 'wet'):
            if (hand_category, tex, pos) in GTO_MIX_FREQ:
                return GTO_MIX_FREQ[(hand_category, tex, pos)]
    return DEFAULT_FREQ


def _card_rank_int(card_str: str) -> int:
    """Convert card string like 'As', 'Kh', '7d' to rank int."""
    rank_map = {
        'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
        '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2,
    }
    if not card_str:
        return 7
    return rank_map.get(card_str[0].upper(), 7)


def _card_suit_int(card_str: str) -> int:
    suit_map = {'s': 1, 'h': 2, 'd': 3, 'c': 4}
    if len(card_str) < 2:
        return 1
    return suit_map.get(card_str[-1].lower(), 1)


def _board_hash(community_cards: list) -> int:
    h = 0
    for i, card in enumerate(community_cards[:3]):
        h += _card_rank_int(card) * (7 + i) + _card_suit_int(card) * (3 + i)
    return h


def _pot_bucket(pot_bb: float) -> int:
    if pot_bb < 5:
        return 0
    elif pot_bb < 15:
        return 1
    elif pot_bb < 30:
        return 2
    elif pot_bb < 60:
        return 3
    else:
        return 4


def _fingerprint(
    hole_card1: str,
    hole_card2: str,
    community_cards: list,
    street: str,
    pot_bb: float,
) -> int:
    street_num = {'flop': 1, 'turn': 2, 'river': 3}.get(street, 1)
    r1 = _card_rank_int(hole_card1)
    r2 = _card_rank_int(hole_card2)
    s1 = _card_suit_int(hole_card1)
    s2 = _card_suit_int(hole_card2)
    bh = _board_hash(community_cards)
    pb = _pot_bucket(pot_bb)

    fp = (r1 * 17 + r2 * 31 + s1 * 7 + s2 * 11 +
          bh * 97 + street_num * 13 + pb * 43) % 100
    return fp


def decide_action(
    hole_card1: str,
    hole_card2: str,
    community_cards: list,
    hand_category: str,
    board_texture: str,
    position: str,
    street: str,
    pot_bb: float,
    frequency_override: Optional[float] = None,
) -> tuple:
    """
    Decide bet or check via deterministic fingerprinting.

    Args:
        hole_card1, hole_card2:  Hero's hole cards (e.g., 'As', 'Kh')
        community_cards:          Board cards (e.g., ['7s', '8h', '2c'])
        hand_category:            Hero's hand category
        board_texture:            Board texture
        position:                 'ip' / 'oop'
        street:                   'flop' / 'turn' / 'river'
        pot_bb:                   Current pot
        frequency_override:       Override GTO frequency (0-1)

    Returns:
        (action, frequency, fingerprint) where action='bet' or 'check'
    """
    freq = frequency_override if frequency_override is not None else _get_gto_freq(hand_category, board_texture, position)
    fp = _fingerprint(hole_card1, hole_card2, community_cards, street, pot_bb)
    action = 'bet' if fp < (freq * 100) else 'check'
    return action, freq, fp


@dataclass
class MixDecision:
    # Inputs
    hole_card1: str
    hole_card2: str
    hand_category: str
    board_texture: str
    position: str
    street: str
    pot_bb: float

    # Analysis
    gto_bet_freq: float
    fingerprint: int
    decision: str       # 'bet' or 'check'
    mixing_ratio: str   # e.g., "65% bet / 35% check"

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_frequency_mix(
    hole_card1: str = 'Ah',
    hole_card2: str = 'Kd',
    community_cards: Optional[list] = None,
    hand_category: str = 'top_pair',
    board_texture: str = 'dry',
    position: str = 'ip',
    street: str = 'flop',
    pot_bb: float = 15.0,
    villain_af: float = 2.0,
    frequency_override: Optional[float] = None,
) -> MixDecision:
    """
    Determine the mixed strategy decision for this specific hand.

    Returns:
        MixDecision with the concrete action (bet or check) for THIS hand.
    """
    if community_cards is None:
        community_cards = ['7s', '8h', '2c']

    action, freq, fp = decide_action(
        hole_card1, hole_card2, community_cards,
        hand_category, board_texture, position, street, pot_bb,
        frequency_override,
    )

    # Adjust frequency for villain aggression
    adj_freq = freq
    if villain_af >= 3.0 and hand_category in ('set', 'overpair', 'top_pair'):
        adj_freq = max(0.05, freq - 0.10)   # check more to trap aggressive villain
    elif villain_af < 1.5 and hand_category in ('flush_draw', 'top_pair'):
        adj_freq = min(0.90, freq + 0.10)   # bet more vs passive (won't bet for you)

    mixing_ratio = f'{freq:.0%} bet / {1-freq:.0%} check'
    verdict = (
        f'[MIX {hand_category}|{board_texture}|{position}] '
        f'{"BET" if action == "bet" else "CHECK"} | '
        f'fp={fp}/100 gto_freq={freq:.0%}'
    )

    reasoning = (
        f'Mixed strategy: {hand_category} on {board_texture} {street}. '
        f'GTO bet frequency: {freq:.0%}. '
        f'Fingerprint: {fp}/100. '
        f'{"fp < {:.0f}: BET.".format(freq*100) if action == "bet" else "fp >= {:.0f}: CHECK.".format(freq*100)}'
    )

    tips = []
    tips.append(
        f'MIXED STRATEGY: {hand_category} on {board_texture} {street} {position.upper()}. '
        f'GTO freq: bet={freq:.0%} check={1-freq:.0%}. '
        f'THIS HAND: fingerprint={fp} -> {"BET" if action == "bet" else "CHECK"} '
        f'(fp {"<" if action == "bet" else ">="} {freq*100:.0f}).'
    )

    tips.append(
        f'FINGERPRINT BASIS: Cards {hole_card1}/{hole_card2}, board={community_cards[:3]}, '
        f'street={street}, pot={pot_bb:.0f}BB. '
        f'Deterministic but appears random to opponents. '
        f'Consistent: same cards+board = same action.'
    )

    if adj_freq != freq:
        tips.append(
            f'VILLAIN ADJUSTMENT: AF={villain_af:.1f} -> '
            f'adjusted freq to {adj_freq:.0%} (from {freq:.0%}). '
            + ('Trap check more vs aggressive villain.' if villain_af >= 3.0 else 'Bet more vs passive (they will not bet for you).')
        )

    tips.append(
        f'WHY MIX: If you always {"bet" if freq >= 0.60 else "check"} {hand_category}, '
        f'villain can {"over-fold" if freq >= 0.60 else "probe freely"}. '
        f'Mixing at {freq:.0%} maximizes EV.'
    )

    return MixDecision(
        hole_card1=hole_card1,
        hole_card2=hole_card2,
        hand_category=hand_category,
        board_texture=board_texture,
        position=position,
        street=street,
        pot_bb=pot_bb,
        gto_bet_freq=freq,
        fingerprint=fp,
        decision=action,
        mixing_ratio=mixing_ratio,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def fmh_one_liner(r: MixDecision) -> str:
    return (
        f'[FMH {r.hand_category}|{r.street}] '
        f'{"BET" if r.decision == "bet" else "CHECK"} | '
        f'fp={r.fingerprint}/100 freq={r.gto_bet_freq:.0%}'
    )
