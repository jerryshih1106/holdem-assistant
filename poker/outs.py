"""
Outs counter and implied odds calculator.

Counts outs for specific draw types (flush draw, straight draw, overcards)
rather than any marginal improvement. Returns the dominant draw type and
the standard poker outs count that players use at the table.

Rule of 2 & 4:
  Turn (1 card to come): equity ≈ outs × 2%
  Flop (2 cards to come): equity ≈ outs × 4%
"""

from dataclasses import dataclass, field
from typing import List
from collections import Counter
from treys import Card

RANKS_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
             'T':10,'J':11,'Q':12,'K':13,'A':14}
SUITS_ALL = ['h','d','c','s']
RANKS_ALL = list(RANKS_VAL.keys())


def _rank(card: str) -> int:
    return RANKS_VAL.get(card[:-1].upper(), 0)

def _suit(card: str) -> str:
    return card[-1].lower()


@dataclass
class OutsResult:
    total_outs:      int       # headline outs number (primary draw)
    flush_outs:      int       # 0 or 9 (or fewer if board-paired flush)
    straight_outs:   int       # 0, 4 (gutshot), or 8 (OESD)
    overcard_outs:   int       # 0-6
    pair_outs:       int       # outs to hit pair (for unpaired hole cards)
    set_outs:        int       # outs to hit a set (for a pocket pair)
    flush_draw:      bool
    oesd:            bool
    gutshot:         bool
    backdoor_flush:  bool
    backdoor_str8:   bool
    cards_to_come:   int       # 1 (turn) or 2 (river)
    pct_next_card:   float     # rule-of-2
    pct_by_river:    float     # rule-of-4  (only valid with 2 cards to come)
    pot_odds_needed: float
    call_amount:     int
    pot_size:        int
    implied_needed:  int
    already_profitable: bool
    draw_names:      List[str] = field(default_factory=list)
    hand_desc:       str = ''


def count_outs(
    hole_cards:      List[str],
    community_cards: List[str],
    pot_size:        int = 0,
    call_amount:     int = 0,
) -> OutsResult:
    """
    Count outs for hero's specific draws on flop or turn.
    Works with 3 or 4 community cards.
    """
    hole  = [c.strip() for c in hole_cards if c.strip()]
    board = [c.strip() for c in community_cards if c.strip()]

    if len(hole) < 2 or len(board) < 3:
        return _empty(pot_size, call_amount)

    all_cards  = hole + board
    cards_left = 5 - len(board)   # 2 on flop, 1 on turn

    h_ranks = [_rank(c) for c in hole]
    b_ranks = [_rank(c) for c in board]
    h_suits = [_suit(c) for c in hole]
    b_suits = [_suit(c) for c in board]
    all_ranks = h_ranks + b_ranks
    all_suits = h_suits + b_suits

    used_ranks = Counter(all_ranks)
    suit_cnt   = Counter(all_suits)

    # ── Flush draw ──────────────────────────────────────────────────────
    flush_outs = 0
    flush_draw = False
    backdoor_flush = False
    dominant_suit = suit_cnt.most_common(1)[0]
    if dominant_suit[1] == 4:
        flush_draw = True
        flush_outs = 13 - dominant_suit[1]  # 9 remaining of that suit
        # minus blocked by board cards
        flush_outs = max(0, 13 - sum(1 for s in all_suits if s == dominant_suit[0]))
    elif dominant_suit[1] == 3 and len(board) == 3:
        backdoor_flush = True   # backdoor: need 2 running

    # ── Straight draw ───────────────────────────────────────────────────
    straight_outs = 0
    oesd = False
    gutshot = False
    backdoor_str8 = False
    # _count_straight_completing_ranks returns NUMBER OF RANKS (not cards)
    # Each rank has up to 4 cards → multiply by 4 for outs count
    str8_rank_count = _count_straight_completing_ranks(all_ranks)
    str8_completing = str8_rank_count * 4   # actual card outs
    if str8_rank_count >= 2:
        oesd = True
        straight_outs = str8_completing
    elif str8_rank_count == 1:
        gutshot = True
        straight_outs = str8_completing   # = 4
    elif str8_rank_count >= 1 and len(board) == 3:
        backdoor_str8 = True

    # ── Overcard outs ───────────────────────────────────────────────────
    max_board_rank = max(b_ranks) if b_ranks else 0
    overcard_outs = 0
    for r in h_ranks:
        if r > max_board_rank:
            # Number of cards of this rank remaining
            remaining = 4 - used_ranks.get(r, 0)
            # Subtract any that are board-paired (would give opponent full house)
            overcard_outs += remaining

    # ── Pair outs (for unpaired hole cards hitting board) ───────────────
    pair_outs = 0
    set_outs  = 0
    if h_ranks[0] == h_ranks[1]:
        # Pocket pair — outs to a set (2 aces remain in deck if we have AA)
        set_outs = max(0, 4 - used_ranks.get(h_ranks[0], 0))
    else:
        # Unpaired — outs to pair either hole card
        for r in h_ranks:
            if r not in b_ranks:   # not already paired on board
                pair_outs += max(0, 4 - used_ranks.get(r, 0))
        pair_outs = max(0, pair_outs)

    # ── Dominant draw & total outs ──────────────────────────────────────
    # Priority: flush > straight > overcards > pair
    if flush_outs >= 8:
        total = flush_outs + min(2, overcard_outs)  # combo draw bonus
    elif straight_outs >= 8:
        total = straight_outs + min(2, overcard_outs)
    elif straight_outs >= 4:
        total = straight_outs + min(3, overcard_outs)
    elif set_outs > 0:
        total = set_outs   # pocket pair: report set outs
    elif overcard_outs >= 4:
        total = overcard_outs
    elif pair_outs > 0:
        total = min(pair_outs, 6)
    else:
        total = 0

    draw_names: List[str] = []
    if flush_draw:     draw_names.append(f'Flush draw ({flush_outs} outs)')
    if oesd:           draw_names.append(f'OESD ({straight_outs} outs)')
    if gutshot:        draw_names.append(f'Gutshot ({straight_outs} outs)')
    if backdoor_flush: draw_names.append('Backdoor flush')
    if backdoor_str8:  draw_names.append('Backdoor straight')
    if overcard_outs and not flush_draw and not oesd:
        draw_names.append(f'{overcard_outs} overcard outs')
    if set_outs:       draw_names.append(f'Set draw ({set_outs} outs)')
    if pair_outs and not flush_draw and not oesd and not gutshot and not overcard_outs:
        draw_names.append(f'Pair outs ({min(pair_outs, 6)} outs)')
    if not draw_names: draw_names.append('No significant draw')

    # ── Probabilities ──────────────────────────────────────────────────
    pct_next  = min(total * 2, 96) / 100
    pct_river = min(total * 4, 96) / 100 if cards_left == 2 else pct_next

    # Use the right probability for the current street
    equity = pct_next if cards_left == 1 else pct_river

    # ── Implied odds ───────────────────────────────────────────────────
    po_threshold = call_amount / (pot_size + call_amount) if (pot_size + call_amount) > 0 else 0
    already_ok   = equity >= po_threshold

    if not already_ok and equity > 0 and call_amount > 0:
        # EV(call) ≥ 0  ↔  equity × (pot + call + implied) ≥ call
        implied = max(0, int(call_amount / equity - pot_size - call_amount))
    else:
        implied = 0

    hand_desc = ''
    if set_outs > 0:
        hand_desc = 'Pocket pair (set mining)'
    elif flush_draw and (oesd or gutshot):
        hand_desc = 'Combo draw'
    elif flush_draw:
        hand_desc = 'Flush draw'
    elif oesd:
        hand_desc = 'Open-ended straight draw'
    elif gutshot:
        hand_desc = 'Gutshot straight draw'
    elif overcard_outs >= 4:
        hand_desc = 'Two overcards'

    return OutsResult(
        total_outs      = total,
        flush_outs      = flush_outs,
        straight_outs   = straight_outs,
        overcard_outs   = overcard_outs,
        pair_outs       = pair_outs,
        set_outs        = set_outs,
        flush_draw      = flush_draw,
        oesd            = oesd,
        gutshot         = gutshot,
        backdoor_flush  = backdoor_flush,
        backdoor_str8   = backdoor_str8,
        cards_to_come   = cards_left,
        pct_next_card   = pct_next,
        pct_by_river    = pct_river,
        pot_odds_needed = po_threshold,
        call_amount     = call_amount,
        pot_size        = pot_size,
        implied_needed  = implied,
        already_profitable = already_ok,
        draw_names      = draw_names,
        hand_desc       = hand_desc,
    )


def _count_straight_completing_ranks(all_ranks: List[int]) -> int:
    """
    How many distinct card ranks complete a 5-card straight
    with the current 4-5 cards?
    Returns the count (typically 0, 4=gutshot, 8=OESD).
    """
    ranks = set(all_ranks)
    if 14 in ranks:
        ranks.add(1)   # Ace plays low

    completing: set = set()
    for candidate in range(1, 15):
        if candidate in ranks:
            continue
        test = ranks | {candidate}
        for low in range(1, 11):
            if set(range(low, low + 5)).issubset(test):
                completing.add(candidate)
                break
    return len(completing)


def _empty(pot: int, call: int) -> OutsResult:
    return OutsResult(
        total_outs=0, flush_outs=0, straight_outs=0,
        overcard_outs=0, pair_outs=0, set_outs=0,
        flush_draw=False, oesd=False, gutshot=False,
        backdoor_flush=False, backdoor_str8=False,
        cards_to_come=2, pct_next_card=0.0, pct_by_river=0.0,
        pot_odds_needed=0.0, call_amount=call, pot_size=pot,
        implied_needed=0, already_profitable=True,
        draw_names=['No draw'], hand_desc='',
    )


def outs_summary(r: OutsResult) -> str:
    """Compact one-line summary for the overlay."""
    if r.total_outs == 0:
        return ''
    street = f'{"Turn" if r.cards_to_come == 1 else "River"}'
    hit_pct = r.pct_next_card if r.cards_to_come == 1 else r.pct_by_river
    parts = [f'{r.total_outs} outs → {hit_pct*100:.0f}% by {street}']
    if r.draw_names:
        parts.append(r.draw_names[0])
    if not r.already_profitable and r.implied_needed > 0:
        parts.append(f'Need {r.implied_needed:,} implied')
    return '  |  '.join(parts)
