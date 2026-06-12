"""
Squeeze Play Advisor (squeeze_advisor.py)

Analyzes squeeze opportunities when facing an open + one or more callers.
Dead money from callers dramatically improves the EV of 3-betting as a squeeze.

Usage:
    from poker.squeeze_advisor import analyze_squeeze, SqueezeResult
    result = analyze_squeeze(
        hand=['As', '5s'],
        hero_pos='BTN',
        opener_pos='UTG',
        callers=['MP', 'CO'],
        open_size_bb=3.0,
        stack_bb=100,
    )
    print(result.reasoning)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Positional ordering for fold equity estimation
_POS_ORDER = ['UTG', 'UTG1', 'UTG2', 'MP', 'MP1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
_POS_OPEN_FOLD_RATE = {
    # How often each position folds to a squeeze (estimated).
    # Early positions open tight ranges and defend more → lower fold rate.
    # Late positions open wide and fold more to squeezes.
    'UTG':  0.35, 'UTG1': 0.37, 'UTG2': 0.39, 'MP': 0.42, 'MP1': 0.44,
    'LJ':   0.46, 'HJ':   0.48, 'CO':   0.52, 'BTN': 0.58,
    'SB':   0.45, 'BB':   0.42,
}
_CALLER_FOLD_RATE = 0.72   # callers have capped ranges — they fold more

# Hand categories for squeeze suitability
_BLOCKER_HANDS = frozenset(['A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'AT',
                             'AJ', 'AQ', 'AK', 'KQ', 'KJ'])
_SUITED_CONNECTORS = frozenset(['A2s', 'A3s', 'A4s', 'A5s', 'A6s', 'A7s', 'A8s',
                                 'A9s', 'ATs', 'AJs', 'AQs',
                                 'KQs', 'KJs', 'QJs', 'JTs',
                                 'T9s', '98s', '87s', '76s', '65s', '54s'])
_PREMIUM = frozenset(['AA', 'KK', 'QQ', 'JJ', 'TT', 'AKo', 'AQo', 'AKs', 'AQs'])


@dataclass
class SqueezeResult:
    """Full squeeze play analysis."""
    hand: str
    hero_pos: str
    opener_pos: str
    num_callers: int

    # Dead money
    dead_money_bb: float      # chips already in pot from open + callers
    pot_before_squeeze_bb: float   # pot including blinds

    # Fold equity
    opener_fold_pct: float
    caller_fold_pct: float    # per caller
    total_fold_equity: float  # prob everyone folds to the squeeze

    # Sizing
    recommended_size_bb: float
    min_size_bb: float
    max_size_bb: float

    # EV components
    ev_if_fold: float         # EV when everyone folds
    ev_if_called: float       # EV when called (approximate postflop)
    total_ev: float

    # Decision
    action: str               # 'squeeze', 'call', 'fold'
    squeeze_ok: bool
    hand_suitability: str     # 'premium', 'bluff', 'value', 'marginal', 'poor'
    blocker_score: float      # 0-1 how well hand blocks villain continuations

    # Reasoning
    reasoning: str
    tips: List[str] = field(default_factory=list)


def _parse_hand(hole_cards: List[str]) -> str:
    """Convert ['As', '5s'] → 'A5s' canonical form."""
    if len(hole_cards) != 2:
        return 'XX'
    ranks = '23456789TJQKA'
    c1, c2 = hole_cards[0], hole_cards[1]
    r1, s1 = c1[0].upper(), c1[1].lower()
    r2, s2 = c2[0].upper(), c2[1].lower()
    suited = s1 == s2
    # Sort by rank descending
    if ranks.index(r1) < ranks.index(r2):
        r1, r2 = r2, r1
    suffix = 's' if suited else 'o'
    return f'{r1}{r2}{suffix}'


def _blocker_score(hand_str: str) -> float:
    """Score 0-1 how well this hand blocks villain's strong continuations."""
    base = hand_str[:2]   # e.g. 'AK' from 'AKs'
    if 'AA' in hand_str or 'KK' in hand_str:
        return 0.3    # we hold aces/kings — villain has fewer combos
    if base in ('AK', 'AQ', 'AJ'):
        return 0.85
    if base in ('KQ', 'KJ', 'QJ'):
        return 0.55
    if base.startswith('A'):
        return 0.70
    if base.startswith('K'):
        return 0.40
    return 0.10


def _hand_suitability(hand_str: str, hero_pos: str, opener_pos: str) -> str:
    """Classify hand suitability for squeezing."""
    base = hand_str[:2]
    suited = hand_str.endswith('s')
    if base in ('AA', 'KK', 'QQ', 'JJ', 'AK'):
        return 'premium'
    if base in ('TT', '99', 'AQ') and suited:
        return 'value'
    if base in ('AJ', 'AT', 'KQ') and suited:
        return 'value'
    if suited and hand_str in _SUITED_CONNECTORS:
        return 'bluff'
    if base.startswith('A') and suited:
        return 'bluff'
    if base in ('AJ', 'AT', 'AQ', 'KQ', 'KJ'):
        return 'marginal'
    return 'poor'


def analyze_squeeze(
    hand: List[str],
    hero_pos: str,
    opener_pos: str,
    callers: List[str],
    open_size_bb: float = 3.0,
    stack_bb: float = 100.0,
    sb_bb: float = 0.5,
    bb_bb: float = 1.0,
    hero_in_blinds: bool = False,
    villain_pfr: float = 0.20,
) -> SqueezeResult:
    """
    Analyze a squeeze play opportunity.

    Args:
        hand:          Hero's hole cards e.g. ['As', '5s']
        hero_pos:      Hero's position
        opener_pos:    Position of the original raiser
        callers:       List of positions that called (e.g. ['MP', 'CO'])
        open_size_bb:  Size of the open raise in BBs
        stack_bb:      Hero's effective stack in BBs
        sb_bb:         Small blind posted (default 0.5)
        bb_bb:         Big blind posted (default 1.0)
        hero_in_blinds: True if hero is SB or BB
        villain_pfr:   Opener's PFR (affects fold rate estimate)

    Returns:
        SqueezeResult
    """
    hand_str = _parse_hand(hand)
    n_callers = len(callers)

    # ── Dead money & pot ───────────────────────────────────────────────────
    dead_money = open_size_bb + n_callers * open_size_bb
    pot_before = dead_money + sb_bb + bb_bb

    # ── Fold equity ────────────────────────────────────────────────────────
    opener_fold = _POS_OPEN_FOLD_RATE.get(opener_pos, 0.50)
    # Adjust opener fold rate for PFR (tight opener folds less)
    if villain_pfr < 0.15:
        opener_fold *= 0.80   # tight players defend more
    elif villain_pfr > 0.25:
        opener_fold *= 1.10   # loose openers fold more

    opener_fold = min(0.95, opener_fold)
    caller_fold = _CALLER_FOLD_RATE

    # P(all fold) = P(opener folds) * P(each caller folds)
    total_fold_eq = opener_fold * (caller_fold ** n_callers)

    # ── Squeeze sizing ─────────────────────────────────────────────────────
    # Standard: 3.5x open + 1.5BB per caller — monotonically increases with callers
    squeeze_size = 3.5 * open_size_bb + n_callers * 1.5
    squeeze_size = max(squeeze_size, open_size_bb * 3.0)
    squeeze_size = min(squeeze_size, stack_bb * 0.35)  # don't commit >35% of stack light

    min_size = open_size_bb * 3.0 + n_callers * 0.5
    max_size = min(stack_bb, open_size_bb * 5.0 + n_callers * 1.5)

    # ── EV calculation ─────────────────────────────────────────────────────
    # EV if fold: win the pot
    ev_if_fold = pot_before

    # EV if called: rough postflop edge (depends on hand quality)
    suitability = _hand_suitability(hand_str, hero_pos, opener_pos)
    blocker = _blocker_score(hand_str)

    postflop_edge = {
        'premium':  0.60,
        'value':    0.55,
        'bluff':    0.48,
        'marginal': 0.50,
        'poor':     0.44,
    }.get(suitability, 0.48)

    called_pot = pot_before + squeeze_size
    ev_if_called = postflop_edge * called_pot - (1 - postflop_edge) * squeeze_size

    total_ev = total_fold_eq * ev_if_fold + (1 - total_fold_eq) * ev_if_called

    # ── Decision ────────────────────────────────────────────────────────────
    squeeze_ok = (
        total_ev > 0
        and total_fold_eq > 0.45
        and stack_bb >= squeeze_size * 2   # SPR sanity check
        and suitability != 'poor'
    )

    # Always squeeze premiums; use EV + fold equity for others
    if suitability == 'premium':
        action = 'squeeze'
    elif suitability == 'poor' and total_ev < 2.0:
        action = 'fold'
    elif total_ev > 3.0 and suitability not in ('poor',):
        action = 'squeeze'
    elif suitability == 'marginal' and total_fold_eq >= 0.35:
        action = 'call'
    elif total_fold_eq < 0.30 and suitability in ('bluff',):
        action = 'fold'   # too little fold equity to run pure bluff
    elif squeeze_ok:
        action = 'squeeze'
    else:
        action = 'fold'

    # ── Reasoning ───────────────────────────────────────────────────────────
    reasoning = (
        f'{hand_str} from {hero_pos} vs {opener_pos}+{n_callers} caller(s).\n'
        f'Dead money: {dead_money:.1f}BB  Fold equity: {total_fold_eq:.0%}.\n'
        f'Recommended squeeze: {squeeze_size:.1f}BB.\n'
        f'EV: {total_ev:.2f}BB  Action: {action.upper()}.'
    )

    tips = []
    if n_callers >= 2:
        tips.append(f'Multi-caller squeeze: {n_callers} callers folding rate '
                    f'{caller_fold:.0%} each gives high dead-money EV.')
    if suitability == 'bluff' and blocker > 0.60:
        tips.append(f'{hand_str} has blocker score {blocker:.0%} — blocks key villain continuations.')
    if suitability == 'premium':
        tips.append('Premium hand: squeeze for max value. Size bigger to protect equity.')
    if total_fold_eq < 0.40:
        tips.append('Low fold equity: squeeze less attractive. Prefer calling with speculative hands.')
    if opener_pos in ('UTG', 'UTG1', 'MP') and suitability == 'bluff':
        tips.append(f'Caution: {opener_pos} opens tight. Their 4-bet range is stronger.')

    return SqueezeResult(
        hand=hand_str,
        hero_pos=hero_pos,
        opener_pos=opener_pos,
        num_callers=n_callers,
        dead_money_bb=dead_money,
        pot_before_squeeze_bb=pot_before,
        opener_fold_pct=opener_fold,
        caller_fold_pct=caller_fold,
        total_fold_equity=total_fold_eq,
        recommended_size_bb=round(squeeze_size, 1),
        min_size_bb=round(min_size, 1),
        max_size_bb=round(max_size, 1),
        ev_if_fold=round(ev_if_fold, 2),
        ev_if_called=round(ev_if_called, 2),
        total_ev=round(total_ev, 2),
        action=action,
        squeeze_ok=squeeze_ok,
        hand_suitability=suitability,
        blocker_score=blocker,
        reasoning=reasoning,
        tips=tips,
    )


def squeeze_one_liner(result: SqueezeResult) -> str:
    """Single-line overlay summary."""
    return (f'{result.hand} {result.hero_pos} squeeze: {result.action.upper()} '
            f'{result.recommended_size_bb:.1f}BB | '
            f'fold_eq={result.total_fold_equity:.0%} | '
            f'EV={result.total_ev:+.1f}BB')
