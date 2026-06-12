"""
River Call Advisor (river_advisor.py)

Analyzes river call/fold decisions using:
  - Pot odds (minimum equity needed)
  - MDF (minimum defense frequency to prevent profitable bluffs)
  - Blocker analysis (do we hold cards that block villain's value combos?)
  - Villain's river bet frequency and sizing patterns

Usage:
    from poker.river_advisor import analyze_river_call, RiverCallResult
    result = analyze_river_call(
        hole_cards=['Kh', 'Qh'],
        community=['Ah', '7c', '2d', 'Jh', '5s'],
        pot_bb=20.0,
        villain_bet_bb=15.0,
        villain_river_bet_freq=0.35,
        villain_vpip=0.28,
    )
    print(result.action, result.reasoning)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class RiverCallResult:
    """Complete river call/fold analysis."""
    # Input context
    pot_bb: float
    villain_bet_bb: float
    total_pot_bb: float    # pot + villain_bet

    # Pot odds
    pot_odds: float        # bet / (pot + bet) — min equity to call
    bet_fraction: float    # bet / pot

    # MDF
    mdf: float             # pot / (pot + bet) — fraction of range to defend
    hero_call_freq: float  # recommended call frequency (may be < MDF if blocker bad)

    # Blocker analysis
    blocker_score: float   # 0-1: how well we block villain's value range
    blocking_combos: List[str]   # which value hands we block
    unblocking_combos: List[str] # which bluffs we don't block (bluff-catchers)

    # Villain bet frequency adjustment
    villain_bet_freq: float
    adjusted_call_threshold: float  # adjusted pot odds after freq normalization

    # EV calculation
    ev_call: float
    ev_fold: float   # always 0

    # Decision
    action: str       # 'call', 'fold', 'indifferent'
    confidence: str   # 'high', 'medium', 'low'
    edge: float       # ev_call - ev_fold (positive = call)

    # Reasoning
    reasoning: str
    key_factors: List[str] = field(default_factory=list)


def _parse_hand(hole_cards: List[str]) -> str:
    """Convert ['Kh', 'Qh'] -> 'KQs'."""
    if len(hole_cards) != 2:
        return 'XX'
    ranks = '23456789TJQKA'
    c1, c2 = hole_cards[0], hole_cards[1]
    r1, s1 = c1[0].upper(), c1[1].lower()
    r2, s2 = c2[0].upper(), c2[1].lower()
    suited = s1 == s2
    if ranks.index(r1) < ranks.index(r2):
        r1, r2 = r2, r1
    return f'{r1}{r2}{"s" if suited else "o"}'


def _blocker_analysis(hole_cards: List[str], community: List[str]) -> Dict:
    """
    Analyze which value/bluff combos the hero's hand blocks.
    Returns blocker_score (0-1), blocking_combos, unblocking_combos.
    """
    if not hole_cards or len(hole_cards) != 2:
        return {'score': 0.0, 'blocking': [], 'unblocking': []}

    hero_ranks = {c[0].upper() for c in hole_cards}
    hero_suits = {c[1].lower() for c in hole_cards}
    board_ranks = {c[0].upper() for c in community}
    board_suits = {c[1].lower(): sum(1 for bc in community if bc[1].lower() == c[1].lower())
                   for c in community}

    blocking = []
    unblocking = []
    score = 0.0

    # Check if we block top pair hands
    if community:
        board_rank_list = [c[0].upper() for c in community]
        top_board_rank = max(board_rank_list, key=lambda r: '23456789TJQKA'.index(r))
        if top_board_rank in hero_ranks:
            blocking.append(f'top-pair ({top_board_rank}x combos reduced)')
            score += 0.25

    # Check if we block nut flush
    for suit, count in board_suits.items():
        if count >= 3 and suit in hero_suits:
            blocking.append(f'nut-flush blocker ({suit.upper()} suit)')
            score += 0.35

    # Check if we block aces (villain can't have AA/AK/Ax)
    if 'A' in hero_ranks:
        blocking.append('Ace blocker (fewer AK/AQ combos)')
        score += 0.20
    if 'K' in hero_ranks:
        blocking.append('King blocker (fewer KK/KQ combos)')
        score += 0.10

    # Unblocking: we don't hold bluff-catcher cards
    # Hands villain might bluff with: low suited connectors, backdoor flush draws
    bluff_ranks = {'2', '3', '4', '5', '6', '7', '8'}
    if not (hero_ranks & bluff_ranks):
        unblocking.append('Does not block villain bluff combos (low cards free)')
        # This is slightly good for calling bluffs but neutral for value calls

    score = min(1.0, score)
    return {'score': score, 'blocking': blocking, 'unblocking': unblocking}


def analyze_river_call(
    hole_cards: List[str],
    community: List[str],
    pot_bb: float,
    villain_bet_bb: float,
    villain_river_bet_freq: float = 0.35,
    villain_vpip: float = 0.30,
    villain_af: float = 1.5,
    hero_equity: Optional[float] = None,
    hero_is_bluff_catcher: bool = False,
) -> RiverCallResult:
    """
    Analyze whether to call or fold to a river bet.

    Args:
        hole_cards:            Hero's hole cards
        community:             All 5 community cards
        pot_bb:                Pot before villain's bet
        villain_bet_bb:        Size of villain's bet
        villain_river_bet_freq: How often villain bets the river overall (0-1)
        villain_vpip:          Villain VPIP for range estimation
        villain_af:            Villain aggression factor
        hero_equity:           If known from Monte Carlo (optional)
        hero_is_bluff_catcher: True if hero has a bluff-catching hand (no showdown otherwise)

    Returns:
        RiverCallResult
    """
    total_pot = pot_bb + villain_bet_bb
    pot_odds = villain_bet_bb / total_pot          # min equity needed
    bet_fraction = villain_bet_bb / pot_bb if pot_bb > 0 else 1.0
    mdf = pot_bb / total_pot                       # min defense frequency

    # ── Blocker analysis ──────────────────────────────────────────────────
    blocker_data = _blocker_analysis(hole_cards, community)
    blocker_score = blocker_data['score']
    blocking_combos = blocker_data['blocking']
    unblocking_combos = blocker_data['unblocking']

    # ── Villain bet frequency adjustment ──────────────────────────────────
    # If villain bets river less than their balanced alpha, they have more value
    # alpha = bet / (pot + bet) = pot_odds
    balanced_bluff_freq = pot_odds     # GTO: bluff ratio = alpha
    villain_bluff_est = villain_river_bet_freq * (1 - villain_vpip * 0.5)

    # When villain bets more than expected, they have more bluffs in range
    freq_adjustment = (villain_river_bet_freq - 0.30) * 0.15
    adjusted_threshold = max(0.05, pot_odds - freq_adjustment - blocker_score * 0.10)

    # ── Hero equity estimate ───────────────────────────────────────────────
    if hero_equity is None:
        # Estimate from hand strength indicators
        hand_str = _parse_hand(hole_cards)
        rank_vals = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10}
        r1 = rank_vals.get(hand_str[0], int(hand_str[0]) if hand_str[0].isdigit() else 7)
        r2 = rank_vals.get(hand_str[1], int(hand_str[1]) if hand_str[1].isdigit() else 6)
        suited = hand_str.endswith('s')
        base_eq = 0.35 + (r1 + r2) / 56 * 0.30 + (0.05 if suited else 0)
        hero_equity = min(0.90, base_eq + blocker_score * 0.10)

    # ── Call frequency (hero's strategy) ──────────────────────────────────
    # Start with MDF, adjust for blockers
    hero_call_freq = mdf + blocker_score * 0.08
    hero_call_freq = min(1.0, hero_call_freq)

    # ── EV of calling ─────────────────────────────────────────────────────
    # EV_call = hero_equity * total_pot - (1 - hero_equity) * villain_bet
    ev_call = hero_equity * total_pot - (1 - hero_equity) * villain_bet_bb
    ev_fold = 0.0

    # ── Decision ──────────────────────────────────────────────────────────
    edge = ev_call - ev_fold
    indiff_zone = villain_bet_bb * 0.12   # within 12% of bet size = indifferent

    if ev_call > indiff_zone:
        action = 'call'
    elif ev_call < -indiff_zone:
        action = 'fold'
    else:
        action = 'indifferent'

    # Override: if blocker is very strong and freq is high, call more
    if blocker_score > 0.60 and villain_river_bet_freq > 0.40:
        if action == 'indifferent':
            action = 'call'

    # Confidence based on information quality
    if hero_equity is not None and (bet_fraction <= 1.0):
        confidence = 'high'
    elif villain_river_bet_freq > 0.0:
        confidence = 'medium'
    else:
        confidence = 'low'

    # ── Reasoning ─────────────────────────────────────────────────────────
    hand_str = _parse_hand(hole_cards)
    reasoning_parts = [
        f'{hand_str} facing {villain_bet_bb:.1f}BB into {pot_bb:.1f}BB pot '
        f'({bet_fraction:.0%} pot bet).',
        f'Pot odds: {pot_odds:.0%} — need {pot_odds:.0%} equity to break even.',
        f'MDF: {mdf:.0%} — must defend {mdf:.0%} of our range.',
        f'Blocker score: {blocker_score:.0%}.',
        f'EV of call: {ev_call:+.2f}BB  Action: {action.upper()}.',
    ]
    reasoning = ' '.join(reasoning_parts)

    key_factors = []
    if bet_fraction > 1.0:
        key_factors.append(f'Overbet ({bet_fraction:.0%} pot) — polarised range; call only strong hands.')
    if bet_fraction < 0.35:
        key_factors.append(f'Small bet ({bet_fraction:.0%} pot) — low MDF ({mdf:.0%}); villain has wide range.')
    if blocker_score > 0.50:
        key_factors.append(f'Strong blocker ({blocker_score:.0%}): {", ".join(blocking_combos[:2])}.')
    if villain_river_bet_freq > 0.50:
        key_factors.append(f'Villain bets river often ({villain_river_bet_freq:.0%}) — more bluffs in range.')
    if villain_river_bet_freq < 0.20:
        key_factors.append(f'Villain rarely bets river ({villain_river_bet_freq:.0%}) — more value-heavy.')
    if unblocking_combos:
        key_factors.append(unblocking_combos[0])
    if not key_factors:
        key_factors.append('Standard spot — use pot odds vs estimated equity.')

    return RiverCallResult(
        pot_bb=pot_bb,
        villain_bet_bb=villain_bet_bb,
        total_pot_bb=total_pot,
        pot_odds=pot_odds,
        bet_fraction=bet_fraction,
        mdf=mdf,
        hero_call_freq=hero_call_freq,
        blocker_score=blocker_score,
        blocking_combos=blocking_combos,
        unblocking_combos=unblocking_combos,
        villain_bet_freq=villain_river_bet_freq,
        adjusted_call_threshold=adjusted_threshold,
        ev_call=round(ev_call, 2),
        ev_fold=0.0,
        action=action,
        confidence=confidence,
        edge=round(edge, 2),
        reasoning=reasoning,
        key_factors=key_factors,
    )


def river_one_liner(result: RiverCallResult) -> str:
    """Single-line overlay summary."""
    return (f'River {result.action.upper()} | '
            f'pot_odds={result.pot_odds:.0%} mdf={result.mdf:.0%} '
            f'blocker={result.blocker_score:.0%} | '
            f'EV={result.ev_call:+.1f}BB')


def analyze_sizing_tell(pot_bb: float, villain_bet_bb: float) -> str:
    """
    Quick read on what villain's sizing typically indicates.
    Returns a one-line interpretation string.
    """
    frac = villain_bet_bb / pot_bb if pot_bb > 0 else 0
    if frac < 0.30:
        return f'Small bet ({frac:.0%} pot): often thin value or blocking bet; call wide.'
    elif frac < 0.60:
        return f'Standard bet ({frac:.0%} pot): balanced range; use MDF.'
    elif frac < 1.0:
        return f'Large bet ({frac:.0%} pot): polarised; fold bluff-catchers without blockers.'
    else:
        return f'Overbet ({frac:.0%} pot): maximally polarised; call only top of range.'
