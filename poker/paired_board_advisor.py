"""
Paired Board Advisor (paired_board_advisor.py)

~17% of all flops contain a pair (e.g., TT5, KK3, 775, AA2).
Strategy shifts dramatically vs unpaired boards:

  High pair board (TT+, KK, AA):
    - PFR (BTN/CO) has massive range advantage: AA, KK, TT, AK
    - C-bet frequency spikes to 70-85%
    - Villain's calling range is capped (can rarely have trips/boat)
    - Bet smaller (merged range) — villain can't call wide

  Mid pair board (66-99, 77-88):
    - Slight PFR range advantage; villain (BB) can have 7x-9x
    - Moderate c-bet frequency (~55-65%)
    - Mixed sizing (small on dry, pot on wet/connected)

  Low pair board (22-55):
    - Range advantage often REVERSES — BB called with 23s, 45s, low pairs
    - PFR c-bets less (45-55%)
    - BB donk-bet frequency rises significantly
    - Villain has many trips, two-pair combos

Villain's range on each paired board:
  PFR range hits:     trips/boats from overpairs (AA→AAK, KK→KK5)
  Caller range hits:  trips/boats from small pairs, suited connectors

Usage:
    from poker.paired_board_advisor import analyze_paired, PairedBoardAdvice
    result = analyze_paired(
        hole_cards=['Ah', 'Kd'],
        community=['Kh', 'Ks', '5c'],
        pot_bb=10.0,
        hero_equity=0.72,
        hero_is_pfr=True,
        hero_pos='BTN',
        villain_vpip=0.28,
        in_position=True,
    )
    print(result.action, result.cbet_freq)
"""

from dataclasses import dataclass, field
from typing import List, Optional


_RANK_ORDER = '23456789TJQKA'
_RANK_NAME  = {r: n for r, n in zip(_RANK_ORDER, [
    '2','3','4','5','6','7','8','9','T','J','Q','K','A'
])}


def _rank_idx(rank: str) -> int:
    return _RANK_ORDER.index(rank.upper()) if rank.upper() in _RANK_ORDER else 0


def _rank_of(card: str) -> str:
    return card[0].upper() if card else '?'


def _detect_pair(community: List[str]) -> Optional[tuple]:
    """
    Detect if the board contains a pair.
    Returns (pair_rank_str, pair_rank_idx) or None.
    For sets (three-of-a-kind on board), returns the rank too.
    """
    from collections import Counter
    ranks = [_rank_of(c) for c in community]
    counts = Counter(ranks)
    pairs = [(r, cnt) for r, cnt in counts.items() if cnt >= 2]
    if not pairs:
        return None
    # Sort by rank index descending (highest pair first)
    pairs.sort(key=lambda x: _rank_idx(x[0]), reverse=True)
    best_rank, best_count = pairs[0]
    return best_rank, _rank_idx(best_rank), best_count


def _hero_trips(hole_cards: List[str], pair_rank: str) -> bool:
    """True if hero holds the matching rank (making trips on paired board)."""
    return any(_rank_of(c) == pair_rank.upper() for c in hole_cards)


def _hero_boat(hole_cards: List[str], pair_rank: str, community: List[str]) -> bool:
    """True if hero's 7-card hand contains a full house."""
    from collections import Counter
    all_cards = list(hole_cards) + list(community)
    counts = Counter(_rank_of(c) for c in all_cards)
    trips_ranks = [r for r, v in counts.items() if v >= 3]
    if not trips_ranks:
        return False
    # Need another rank with 2+ cards, or two different trips ranks
    if len(trips_ranks) >= 2:
        return True
    for r, v in counts.items():
        if r not in trips_ranks and v >= 2:
            return True
    return False


def _pfr_range_advantage(pair_rank_idx: int) -> float:
    """
    How much of a range advantage does the PFR have on this paired board.
    Range: -1.0 (caller has big advantage) to +1.0 (PFR has big advantage).
    """
    # High pair (TT=8, JJ=9, QQ=10, KK=11, AA=12): PFR has massive advantage
    if pair_rank_idx >= 8:      # TT+
        return 0.35 + (pair_rank_idx - 8) * 0.06
    elif pair_rank_idx >= 5:    # 66-99
        return 0.10 + (pair_rank_idx - 5) * 0.05
    else:                       # 22-55: caller has slight advantage
        return -0.05 - (5 - pair_rank_idx) * 0.05


@dataclass
class PairedBoardAdvice:
    """Strategic advice for a paired board."""
    # Board info
    board_pair_rank: str          # e.g. 'K', 'T', '7'
    board_pair_idx: int           # rank index (0=2, 12=A)
    pair_count: int               # 2=pair on board, 3=trips on board
    is_high_pair: bool            # TT+
    is_low_pair: bool             # 22-55

    # Hero's holding vs board
    hero_has_trips: bool
    hero_has_boat: bool

    # Range dynamics
    pfr_range_advantage: float    # +1=PFR huge advantage, -1=caller advantage
    pfr_advantage_label: str      # 'massive', 'moderate', 'slight', 'neutral', 'reverse'

    # C-bet recommendation
    cbet_freq: float              # recommended c-bet frequency (0-1)
    cbet_size_pct: float          # recommended sizing (fraction of pot)
    cbet_size_bb: float           # sizing in BBs

    # Donk bet (if hero is BB/caller)
    donk_freq: float              # how often caller should donk-bet
    donk_size_pct: float

    # EV
    ev_cbet: float
    ev_check: float

    # Decision
    action: str                   # 'bet', 'check-call', 'check-fold', 'raise'
    hero_range: str               # 'trips', 'boat', 'overpair', 'underpair', 'air'

    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_paired(
    hole_cards: List[str],
    community: List[str],
    pot_bb: float,
    hero_equity: float = 0.50,
    hero_is_pfr: bool = True,
    hero_pos: str = 'BTN',
    villain_vpip: float = 0.28,
    villain_fold_to_cbet: float = 0.50,
    in_position: bool = True,
    eff_stack_bb: float = 100.0,
    street: str = 'flop',
) -> PairedBoardAdvice:
    """
    Analyze strategy on a paired board.

    Args:
        hole_cards:          Hero's 2 hole cards
        community:           Board cards (must contain a pair)
        pot_bb:              Current pot in BBs
        hero_equity:         Hero's equity vs villain's range
        hero_is_pfr:         True if hero raised preflop (PFR)
        hero_pos:            Hero's position
        villain_vpip:        Villain's VPIP
        villain_fold_to_cbet: Villain's fold-to-cbet frequency
        in_position:         True if hero acts after villain
        eff_stack_bb:        Effective stack remaining
        street:              'flop', 'turn', 'river'

    Returns:
        PairedBoardAdvice
    """
    pair_info = _detect_pair(community)
    if pair_info is None:
        # Not a paired board — return default advice
        pair_rank, pair_idx, pair_count = 'T', 8, 2  # default
        is_paired_board = False
    else:
        pair_rank, pair_idx, pair_count = pair_info
        is_paired_board = True

    is_high = pair_idx >= 8    # TT+
    is_low  = pair_idx <= 3    # 22-55

    # Hero's holding assessment
    has_trips = _hero_trips(hole_cards, pair_rank)
    has_boat  = _hero_boat(hole_cards, pair_rank, community)

    # Hero range category
    hole_ranks = [_rank_of(c) for c in hole_cards]
    if has_boat:
        hero_range = 'boat'
    elif has_trips:
        hero_range = 'trips'
    elif all(_rank_idx(r) > pair_idx for r in hole_ranks):
        hero_range = 'overpair'
    elif all(_rank_idx(r) < pair_idx for r in hole_ranks):
        hero_range = 'underpair'
    else:
        hero_range = 'air'

    # PFR range advantage on this board (always from PFR's perspective)
    pfr_adv = _pfr_range_advantage(pair_idx)
    # hero_adv: positive = hero has advantage
    hero_adv = pfr_adv if hero_is_pfr else -pfr_adv

    range_adv = hero_adv  # used for local decisions below

    if pfr_adv >= 0.25:
        adv_label = 'massive'
    elif pfr_adv >= 0.10:
        adv_label = 'moderate'
    elif pfr_adv >= 0.02:
        adv_label = 'slight'
    elif pfr_adv >= -0.05:
        adv_label = 'neutral'
    else:
        adv_label = 'reverse'

    # ── C-bet frequency ─────────────────────────────────────────────────────────
    if hero_is_pfr and in_position:
        if is_high:
            cbet_freq = 0.78 + (pair_idx - 8) * 0.02   # KK board = 0.82, AA = 0.84
        elif pair_idx >= 5:
            cbet_freq = 0.60 + (pair_idx - 5) * 0.03
        else:
            cbet_freq = 0.48 - (5 - pair_idx) * 0.02
    elif hero_is_pfr and not in_position:
        if is_high:
            cbet_freq = 0.65 + (pair_idx - 8) * 0.02
        elif pair_idx >= 5:
            cbet_freq = 0.50
        else:
            cbet_freq = 0.38
    else:
        # Hero is caller — c-bet not applicable; use probe frequency
        cbet_freq = 0.20 if is_high else 0.30

    # Adjust for holdings
    if hero_range in ('boat', 'trips'):
        cbet_freq = min(1.0, cbet_freq + 0.10)   # always bet trips/boats

    # Villain adjust: loose villains call more → bet more for value
    cbet_freq += (villain_vpip - 0.28) * 0.20
    cbet_freq = max(0.15, min(1.0, cbet_freq))

    # ── Sizing ─────────────────────────────────────────────────────────────────
    # High paired boards → smaller sizing (villain's range is capped, can't call big)
    # Low paired boards → larger sizing possible (villain has more equity)
    if hero_range in ('boat', 'trips'):
        size_pct = 0.70   # extract maximum value
    elif is_high and hero_is_pfr:
        size_pct = 0.40   # small merged bet (villain has limited trips combos)
    elif is_low:
        size_pct = 0.60   # larger to protect vs caller's equity
    else:
        size_pct = 0.55   # default turn

    # River: larger sizing
    if street == 'river':
        size_pct = min(1.0, size_pct + 0.15)

    cbet_size = pot_bb * size_pct
    cbet_size = min(cbet_size, eff_stack_bb * 0.7)

    # ── Donk bet (caller's perspective) ─────────────────────────────────────────
    donk_freq = 0.05 if is_high else 0.25 if is_low else 0.10
    if has_trips or has_boat:
        donk_freq = min(0.50, donk_freq + 0.15)
    donk_size_pct = 0.45 if is_low else 0.35

    # ── EV calculations ──────────────────────────────────────────────────────────
    total_pot = pot_bb + cbet_size
    ev_if_fold = pot_bb
    ev_if_call = hero_equity * total_pot - (1 - hero_equity) * cbet_size
    ev_cbet = villain_fold_to_cbet * ev_if_fold + (1 - villain_fold_to_cbet) * ev_if_call

    check_realise = 0.88 if in_position else 0.72
    ev_check = hero_equity * pot_bb * check_realise

    # ── Action decision ──────────────────────────────────────────────────────────
    if hero_range in ('boat', 'trips') and hero_is_pfr:
        action = 'bet'
    elif hero_is_pfr and ev_cbet > ev_check and cbet_freq > 0.45:
        action = 'bet'
    elif hero_is_pfr and hero_range == 'overpair':
        action = 'bet' if in_position else 'check-call'
    elif not hero_is_pfr and (has_trips or has_boat):
        action = 'bet'   # donk with trips/boat as caller
    elif hero_equity >= 0.45:
        action = 'check-call'
    else:
        action = 'check-fold'

    # ── Tips ─────────────────────────────────────────────────────────────────────
    tips = []
    if is_high and hero_is_pfr:
        tips.append(
            f'High pair ({pair_rank}{pair_rank}) board: massive PFR range advantage. '
            f'C-bet {cbet_freq:.0%} with small sizing ({size_pct:.0%} pot) — '
            f'villain rarely holds trips and must over-fold.'
        )
    if is_low and not hero_is_pfr:
        tips.append(
            f'Low pair ({pair_rank}{pair_rank}) board: you (BB/caller) have range advantage. '
            f'Consider donk-betting {donk_freq:.0%} of the time with your trips/two-pairs.'
        )
    if hero_range == 'boat':
        tips.append(
            'Full house: slow-play option available. '
            'Mix between fast-playing (bet) and slow-playing (check-raise) to remain balanced.'
        )
    if hero_range == 'trips' and is_high:
        tips.append(
            f'You have trips on {pair_rank}{pair_rank} board — villain almost never has a boat. '
            f'Bet large for maximum value; villain must call with dominated hands.'
        )
    if hero_range == 'underpair' and is_high:
        tips.append(
            f'Underpair on {pair_rank}{pair_rank} board: your hand has little equity. '
            f'Check-fold unless SPR is very low or you have strong reads.'
        )
    if not tips:
        tips.append(
            f'{pair_rank}{pair_rank} board: {adv_label} PFR advantage. '
            f'Cbet {cbet_freq:.0%} at {size_pct:.0%} pot. Action: {action.upper()}.'
        )

    reasoning = (
        f'Board pair: {pair_rank}{pair_rank} (rank={pair_idx}, count={pair_count}). '
        f'Hero: {hero_range} {"PFR" if hero_is_pfr else "caller"} '
        f'{"IP" if in_position else "OOP"}. '
        f'Range adv: {range_adv:+.2f} ({adv_label}). '
        f'equity={hero_equity:.0%} FCbet={villain_fold_to_cbet:.0%}. '
        f'Cbet {cbet_size:.1f}BB ({size_pct:.0%}p) freq={cbet_freq:.0%}. '
        f'EV(bet)={ev_cbet:+.2f} EV(check)={ev_check:+.2f}. '
        f'Action: {action.upper()}.'
    )

    return PairedBoardAdvice(
        board_pair_rank=pair_rank,
        board_pair_idx=pair_idx,
        pair_count=pair_count,
        is_high_pair=is_high,
        is_low_pair=is_low,
        hero_has_trips=has_trips,
        hero_has_boat=has_boat,
        pfr_range_advantage=round(pfr_adv, 3),
        pfr_advantage_label=adv_label,
        cbet_freq=round(cbet_freq, 3),
        cbet_size_pct=round(size_pct, 2),
        cbet_size_bb=round(cbet_size, 1),
        donk_freq=round(donk_freq, 3),
        donk_size_pct=round(donk_size_pct, 2),
        ev_cbet=round(ev_cbet, 2),
        ev_check=round(ev_check, 2),
        action=action,
        hero_range=hero_range,
        reasoning=reasoning,
        tips=tips,
    )


def paired_one_liner(result: PairedBoardAdvice) -> str:
    """Single-line overlay summary."""
    return (
        f'Paired {result.board_pair_rank}{result.board_pair_rank} '
        f'[{result.pfr_advantage_label}] {result.hero_range}: '
        f'{result.action.upper()} {result.cbet_size_bb:.1f}BB '
        f'freq={result.cbet_freq:.0%}'
    )
