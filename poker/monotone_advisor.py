"""
Monotone Board Advisor (monotone_advisor.py)

When 3 or more board cards share the same suit, standard strategies break down:
  - Overpairs lose significant value (villain may hold 2 suited cards)
  - C-bet frequency drops sharply (IP: 35-45% vs typical 65%)
  - Sizing shrinks (33-50% pot is GTO on mono flops)
  - Bluffing equity comes from blocking the nut flush
  - Check-calling increases (protect equity without charging draws)

Key strategic axes:
  hero_has_nut_flush  →  bet large, block-raise shoves
  hero_has_flush      →  bet value vs villain's weaker flushes/draws
  hero_has_blocker    →  bluff more profitably (Ax in suit)
  hero_has_no_suit    →  check-fold most air; check-call strong but non-flush hands

Usage:
    from poker.monotone_advisor import analyze_monotone, MonotoneAdvice
    result = analyze_monotone(
        hole_cards=['Ah', 'Kd'],
        community=['Jh', '7h', '2h'],
        pot_bb=12.0,
        hero_equity=0.48,
        hero_pos='BTN',
        in_position=True,
        villain_cbet_freq=0.65,
        villain_af=2.0,
    )
    print(result.action, result.bet_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _suit_of(card: str) -> str:
    """Return suit character from a card string like 'Ah' → 'h'."""
    if not card or len(card) < 2:
        return '?'
    return card[-1].lower()


def _rank_of(card: str) -> str:
    return card[0].upper() if card else '?'


_RANK_ORDER = '23456789TJQKA'


def _rank_idx(rank: str) -> int:
    return _RANK_ORDER.index(rank) if rank in _RANK_ORDER else 0


def _is_monotone(community: List[str]) -> tuple:
    """
    Returns (is_monotone, board_suit, num_suited_cards).
    board_suit is the dominant suit if 3+ cards share it, else ''.
    """
    if len(community) < 3:
        return False, '', 0
    suits = [_suit_of(c) for c in community]
    for suit in 'hsdc':
        count = suits.count(suit)
        if count >= 3:
            return True, suit, count
    return False, '', 0


def _has_nut_flush(hole_cards: List[str], board_suit: str) -> bool:
    """True if hero holds the ace of the board suit."""
    for card in hole_cards:
        if _suit_of(card) == board_suit and _rank_of(card) == 'A':
            return True
    return False


def _flush_rank(hole_cards: List[str], board_suit: str) -> Optional[int]:
    """
    Return rank index of hero's highest suited card if it matches board suit.
    Returns None if hero has no suited card matching the board.
    """
    ranks = [_rank_idx(_rank_of(c)) for c in hole_cards if _suit_of(c) == board_suit]
    return max(ranks) if ranks else None


def _has_flush_draw(hole_cards: List[str], board_suit: str) -> bool:
    """True if hero has exactly one card of the board suit (draw to flush)."""
    count = sum(1 for c in hole_cards if _suit_of(c) == board_suit)
    return count == 1


def _has_made_flush(hole_cards: List[str], board_suit: str) -> bool:
    """True if hero holds 2 cards of the board suit (made flush on monotone board)."""
    count = sum(1 for c in hole_cards if _suit_of(c) == board_suit)
    return count >= 2


@dataclass
class MonotoneAdvice:
    """Strategic advice for a monotone (single-suit) board."""
    # Board assessment
    is_monotone: bool
    board_suit: str
    num_suited_board_cards: int

    # Hero's flush holding
    hero_has_nut_flush: bool     # holds Ax of board suit + made flush
    hero_has_made_flush: bool    # holds 2 cards of board suit
    hero_has_blocker: bool       # holds exactly 1 card of board suit (blocker / FD)
    hero_flush_rank: Optional[int]  # rank index of highest suited card (0=2, 12=A)

    # Bet sizing (smaller than usual due to capped ranges)
    bet_size_bb: float
    bet_size_pct: float

    # Adjusted frequencies vs standard boards
    cbet_freq_adj: float         # absolute freq to c-bet (not delta)
    check_call_threshold: float  # equity threshold to check-call vs check-fold

    # EV components
    ev_bet: float
    ev_check: float

    # Decision
    action: str          # 'bet', 'check-call', 'check-fold', 'raise'
    hand_category: str   # 'nut_flush', 'made_flush', 'blocker', 'air', 'strong_non_flush'

    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_monotone(
    hole_cards: List[str],
    community: List[str],
    pot_bb: float,
    hero_equity: float = 0.45,
    hero_pos: str = 'BTN',
    in_position: bool = True,
    villain_cbet_freq: float = 0.60,
    villain_af: float = 2.0,
    villain_fold_to_bet: float = 0.45,
    eff_stack_bb: float = 100.0,
    street: str = 'flop',
) -> MonotoneAdvice:
    """
    Analyze strategy on a monotone (single-suit) board.

    Args:
        hole_cards:           Hero's 2 hole cards (e.g. ['Ah', 'Kd'])
        community:            Board cards (e.g. ['Jh', '7h', '2h'])
        pot_bb:               Current pot in BBs
        hero_equity:          Hero's equity vs villain's range
        hero_pos:             Hero's position
        in_position:          True if hero acts after villain
        villain_cbet_freq:    Villain's c-bet frequency on this board
        villain_af:           Villain's aggression factor
        villain_fold_to_bet:  Villain's fold frequency to a bet
        eff_stack_bb:         Effective stack remaining
        street:               'flop', 'turn', 'river'

    Returns:
        MonotoneAdvice
    """
    is_mono, board_suit, num_suited = _is_monotone(community)

    # Assess hero's flush holding
    nut = _has_nut_flush(hole_cards, board_suit) and _has_made_flush(hole_cards, board_suit)
    made = _has_made_flush(hole_cards, board_suit)
    blocker = _has_flush_draw(hole_cards, board_suit)
    flush_rank = _flush_rank(hole_cards, board_suit)

    # ── Hand category ──────────────────────────────────────────────────────────
    if nut:
        hand_category = 'nut_flush'
    elif made and (flush_rank is not None and flush_rank >= 10):  # Q+ flush
        hand_category = 'made_flush'
    elif made:
        hand_category = 'made_flush'
    elif blocker and flush_rank is not None and flush_rank >= 12:  # A-high blocker
        hand_category = 'blocker'
    elif blocker:
        hand_category = 'blocker'
    elif hero_equity >= 0.60:
        hand_category = 'strong_non_flush'
    else:
        hand_category = 'air'

    # ── Bet sizing ─────────────────────────────────────────────────────────────
    # Monotone boards → smaller sizing (capped range; blocker bets)
    if hand_category == 'nut_flush':
        size_pct = 0.75 if street == 'river' else 0.55
    elif hand_category == 'made_flush':
        size_pct = 0.55 if street != 'river' else 0.65
    elif hand_category == 'blocker':
        size_pct = 0.33  # small blocker bet with nut flush blocker
    elif hand_category == 'strong_non_flush':
        size_pct = 0.40  # bet small to see where we stand, avoid commit
    else:
        size_pct = 0.33  # air can still use a small probe size

    size_pct = max(0.25, min(1.00, size_pct))
    bet_size = pot_bb * size_pct
    bet_size = min(bet_size, eff_stack_bb * 0.6)

    # ── Adjusted c-bet frequency on monotone boards ────────────────────────────
    # IP PFR baseline on monotone flop: ~35-45% (vs 60-70% on dry boards)
    if in_position:
        cbet_freq = 0.40 + (0.10 if hand_category in ('nut_flush', 'made_flush') else 0)
    else:
        cbet_freq = 0.28 + (0.10 if hand_category in ('nut_flush', 'made_flush') else 0)

    # Check-call threshold: need more equity on monotone (many villain hands have equity)
    cc_threshold = 0.30 if hand_category in ('nut_flush', 'made_flush', 'blocker') else 0.40

    # ── EV calculations ─────────────────────────────────────────────────────────
    total_pot = pot_bb + bet_size
    ev_if_fold = pot_bb
    ev_if_call = hero_equity * total_pot - (1 - hero_equity) * bet_size
    ev_bet = villain_fold_to_bet * ev_if_fold + (1 - villain_fold_to_bet) * ev_if_call

    check_realise = 0.88 if in_position else 0.72
    ev_check = hero_equity * pot_bb * check_realise

    # ── Action decision ─────────────────────────────────────────────────────────
    if hand_category == 'nut_flush':
        action = 'bet'
    elif hand_category == 'made_flush' and ev_bet > ev_check:
        action = 'bet'
    elif hand_category == 'blocker' and in_position and villain_fold_to_bet >= 0.45:
        action = 'bet'  # blocker bet with nut flush blocker IP
    elif hand_category == 'strong_non_flush':
        # Strong non-flush on monotone: check more, avoid big pot without flush
        action = 'check-call' if in_position else 'check-call'
    elif hero_equity >= cc_threshold:
        action = 'check-call'
    else:
        action = 'check-fold'

    # Never bet "air" OOP on monotone (too much reverse implied odds)
    if hand_category == 'air' and not in_position:
        action = 'check-fold'

    # ── Tips ─────────────────────────────────────────────────────────────────
    tips = []
    if hand_category == 'nut_flush':
        tips.append(
            'Nut flush on monotone board: bet for value. '
            'Use 50-60% pot (not PSB) to keep villain in with weaker flushes. '
            'Consider slow-playing only if villain is very aggressive.'
        )
    if hand_category == 'made_flush' and flush_rank is not None and flush_rank < 8:
        tips.append(
            f'Low flush ({_RANK_ORDER[flush_rank]}-high): pot control. '
            f'Villain may have a higher flush. Bet small or check-call; do not stack off.'
        )
    if hand_category == 'blocker':
        tips.append(
            'Ace-high flush draw / blocker: small bet (33% pot) serves as a blocker bet. '
            'Villain\'s nut flush combos are reduced — exploit with occasional bluff.'
        )
    if hand_category == 'strong_non_flush':
        tips.append(
            'Strong hand (set/two-pair) but no flush on monotone board: check more. '
            'You\'re in bad shape vs flushes. Keep pot small and see if flush falls off.'
        )
    if hand_category == 'air' and in_position:
        tips.append(
            'No flush holding IP on monotone board: check back and take the free card. '
            'Villain\'s range includes many flush holdings; bluffing here has low EV.'
        )
    if not in_position and hand_category not in ('nut_flush', 'made_flush'):
        tips.append(
            'OOP on monotone board without a flush: minimize losses. '
            'Check-fold to any bet unless your equity justifies a call.'
        )
    if not tips:
        tips.append(
            f'Monotone {board_suit} board: standard adjustments applied. '
            f'Sizing: {size_pct:.0%} pot. Action: {action.upper()}.'
        )

    reasoning = (
        f'Monotone {board_suit} board ({num_suited} suited cards). '
        f'Hero: {hand_category} (flush_rank={flush_rank}). '
        f'equity={hero_equity:.0%} fold_to_bet={villain_fold_to_bet:.0%}. '
        f'Bet {bet_size:.1f}BB ({size_pct:.0%} pot). '
        f'EV(bet)={ev_bet:+.2f} EV(check)={ev_check:+.2f}. '
        f'Cbet freq: {cbet_freq:.0%} (vs standard ~60%). '
        f'Action: {action.upper()}.'
    )

    return MonotoneAdvice(
        is_monotone=is_mono,
        board_suit=board_suit,
        num_suited_board_cards=num_suited,
        hero_has_nut_flush=nut,
        hero_has_made_flush=made,
        hero_has_blocker=blocker,
        hero_flush_rank=flush_rank,
        bet_size_bb=round(bet_size, 1),
        bet_size_pct=round(size_pct, 2),
        cbet_freq_adj=round(cbet_freq, 2),
        check_call_threshold=round(cc_threshold, 2),
        ev_bet=round(ev_bet, 2),
        ev_check=round(ev_check, 2),
        action=action,
        hand_category=hand_category,
        reasoning=reasoning,
        tips=tips,
    )


def monotone_one_liner(result: MonotoneAdvice) -> str:
    """Single-line overlay summary."""
    suit_sym = {'h': 'H', 's': 'S', 'd': 'D', 'c': 'C'}.get(result.board_suit, '?')
    return (
        f'Mono {suit_sym} [{result.hand_category}]: '
        f'{result.action.upper()} {result.bet_size_bb:.1f}BB ({result.bet_size_pct:.0%}p) | '
        f'EV={result.ev_bet:+.2f} cbet_freq={result.cbet_freq_adj:.0%}'
    )
