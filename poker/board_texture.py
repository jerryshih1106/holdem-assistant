"""
Post-flop board texture analysis.

Classifies community cards by flush potential, pairing, connectivity,
high-card density and range advantage; then recommends c-bet frequency
and sizing for the preflop aggressor acting in position.
"""

from dataclasses import dataclass
from typing import List
from collections import Counter

RANK_VAL = {
    '2': 2,  '3': 3,  '4': 4,  '5': 5,  '6': 6,
    '7': 7,  '8': 8,  '9': 9,  'T': 10, 'J': 11,
    'Q': 12, 'K': 13, 'A': 14,
}


def _rank(card: str) -> int:
    return RANK_VAL.get(card[:-1].upper(), 0)

def _suit(card: str) -> str:
    return card[-1].lower()


@dataclass
class BoardTexture:
    cards: List[str]
    n: int                    # number of community cards

    # ── suit analysis ──────────────────────────────────────────────────────
    monotone: bool            # all same suit
    flush_draw: bool          # 2+ same suit (relevant on flop)
    flush_complete: bool      # 4+ same suit — flush already possible

    # ── rank analysis ──────────────────────────────────────────────────────
    has_pair: bool
    has_trips: bool
    top_rank: int             # rank value of highest card (2-14)
    high_count: int           # number of Broadway cards (T+)

    # ── draw analysis ──────────────────────────────────────────────────────
    str8_outs: int            # cards that could complete a straight (rough)
    connected: bool           # at least two cards within 2 ranks of each other

    # ── summary ────────────────────────────────────────────────────────────
    wetness: float            # 0.0 = bone dry  →  1.0 = extremely wet
    texture_name: str         # human-readable label
    range_advantage: str      # 'raiser' | 'caller' | 'neutral'

    # ── c-bet guidance ─────────────────────────────────────────────────────
    cbet_freq: float          # recommended c-bet frequency (IP aggressor)
    cbet_size: float          # recommended size as fraction of pot
    cbet_note: str            # one-line strategic note


# ── straight draw counting ─────────────────────────────────────────────────────

def _straight_draw_outs(rank_vals: List[int]) -> int:
    """How many distinct ranks complete a 5-card straight with the board?"""
    ranks = set(rank_vals)
    if 14 in ranks:           # Ace plays low too
        ranks.add(1)
    outs: set = set()
    for candidate in range(1, 15):
        if candidate in ranks:
            continue
        test = ranks | {candidate}
        for low in range(1, 11):
            if len(set(range(low, low + 5)) & test) >= 5:
                outs.add(candidate)
                break
    return len(outs)


# ── main analysis function ─────────────────────────────────────────────────────

def analyze_board(community_cards: List[str]) -> BoardTexture:
    """Return a BoardTexture for the given community cards (3, 4, or 5 cards)."""
    cards = [c.strip() for c in community_cards if c.strip()]
    n = len(cards)

    if n == 0:
        return _empty_texture()

    rank_vals  = [_rank(c) for c in cards]
    suits      = [_suit(c) for c in cards]
    suit_cnt   = Counter(suits)
    rank_cnt   = Counter(rank_vals)
    max_suit   = max(suit_cnt.values()) if suit_cnt else 0

    monotone         = max_suit == n
    flush_complete   = max_suit >= 4
    flush_draw       = (max_suit >= 2 and n == 3) or (max_suit == 3 and n == 4)

    has_pair         = any(v >= 2 for v in rank_cnt.values())
    has_trips        = any(v >= 3 for v in rank_cnt.values())

    top_rank   = max(rank_vals)
    high_count = sum(1 for r in rank_vals if r >= 10)

    sorted_u   = sorted(set(rank_vals))
    gaps       = [sorted_u[i+1] - sorted_u[i] for i in range(len(sorted_u) - 1)]
    connected  = any(g <= 2 for g in gaps) if gaps else False
    str8_outs  = _straight_draw_outs(rank_vals)

    # ── wetness ────────────────────────────────────────────────────────────
    wet = 0.0
    if monotone or flush_complete: wet += 0.40
    elif flush_draw:               wet += 0.22
    if connected:                  wet += 0.20
    if str8_outs >= 6:             wet += 0.20
    elif str8_outs >= 3:           wet += 0.10
    if has_pair:                   wet -= 0.08   # paired board is less dynamic
    wetness = max(0.0, min(1.0, wet))

    # ── texture name ───────────────────────────────────────────────────────
    if monotone:
        name = 'Monotone'
    elif flush_complete:
        name = 'Flush on board'
    elif flush_draw and connected:
        name = 'Wet — Flush + Straight draws'
    elif flush_draw:
        name = 'Two-tone' + (' Paired' if has_pair else '')
    elif connected:
        name = 'Connected Rainbow' + (' Paired' if has_pair else '')
    elif has_pair:
        name = 'Dry Paired'
    else:
        name = 'Dry Rainbow'

    # ── range advantage ────────────────────────────────────────────────────
    # High boards: raiser has more AK/AQ/KQ combos → advantage
    # Low boards: caller has more small pairs / suited connectors → advantage
    if top_rank >= 12:                        # Q, K, or A on board
        adv = 'raiser'
    elif top_rank <= 8 and not has_pair:      # low unparied board
        adv = 'caller'
    elif top_rank <= 9 and connected:         # low connected (e.g. 6-7-8)
        adv = 'caller'
    else:
        adv = 'neutral'

    # ── c-bet strategy ─────────────────────────────────────────────────────
    # Dry high boards   → high frequency, small size (33%)  — raiser has range advantage, few draws
    # Paired boards     → very low frequency, small size    — range advantage unclear, tricky
    # Wet boards        → low frequency, big size (75%)     — protection, charge draws, polarised
    # Monotone boards   → very low frequency, large size    — danger of dominated flush
    # Connected rainbow → medium frequency, medium size

    if has_trips:
        freq, size = 0.25, 0.35
        note = 'Trip board — mostly check, opponent likely has nothing'
    elif monotone:
        freq, size = 0.30, 0.70
        note = 'Monotone — bet only with strong hands or nut flush draw'
    elif flush_complete:
        freq, size = 0.30, 0.65
        note = 'Flush complete — check range unless you have the flush'
    elif has_pair and wetness < 0.25:
        freq, size = 0.30, 0.40
        note = 'Dry paired — check mostly; bet thinly with top pair+'
    elif wetness > 0.55:
        freq, size = 0.45, 0.75
        note = 'Wet board — polarised: bet strong hands/bluffs, check middle'
    elif wetness > 0.30:
        freq, size = 0.60, 0.50
        note = 'Semi-wet — mix: bet top pair+, check weak pairs/draws'
    else:
        freq, size = 0.78, 0.33
        note = 'Dry board — high-frequency small bet entire range'

    # IP multiplier (this function models IP aggressor; OOP should be more cautious)
    cbet_freq = min(1.0, freq)
    cbet_size = size

    return BoardTexture(
        cards=cards, n=n,
        monotone=monotone, flush_draw=flush_draw, flush_complete=flush_complete,
        has_pair=has_pair, has_trips=has_trips,
        top_rank=top_rank, high_count=high_count,
        str8_outs=str8_outs, connected=connected,
        wetness=wetness, texture_name=name,
        range_advantage=adv,
        cbet_freq=cbet_freq, cbet_size=cbet_size, cbet_note=note,
    )


def _empty_texture() -> BoardTexture:
    return BoardTexture(
        cards=[], n=0,
        monotone=False, flush_draw=False, flush_complete=False,
        has_pair=False, has_trips=False,
        top_rank=0, high_count=0,
        str8_outs=0, connected=False,
        wetness=0.0, texture_name='Pre-flop',
        range_advantage='neutral',
        cbet_freq=0.0, cbet_size=0.0, cbet_note='No community cards yet',
    )


def wetness_bar(wetness: float, width: int = 20) -> str:
    filled = int(wetness * width)
    return '█' * filled + '░' * (width - filled)
