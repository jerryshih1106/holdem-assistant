"""
Preflop Squeeze Range Builder (preflop_squeeze_range.py)

Builds and analyzes squeeze ranges: 3-betting after a raise + call(s).
Squeezing is powerful because:
  1. Dead money from caller(s) improves pot odds for squeezer
  2. Caller must now face a 3bet cold (much harder than calling a raise)
  3. Original raiser's range is capped (would have 4bet with nuts)
  4. Squeezer gains pot before seeing flop

SQUEEZE MATH:
  Effective squeeze size:
    vs 1 caller:  3.5-4.5x the original raise
    vs 2 callers: 4.5-5.5x (more dead money = larger size)

  Squeeze EV:
    EV = fold_equity * dead_money - (1-fold_equity) * net_call_amount

  Fold equity:
    Raiser has wider range (more foldable hands than a 3bet open)
    Cold caller's range is strong (less foldable) but they're out of position

SQUEEZE HANDS:
  VALUE SQUEEZES:
    Premium hands: AA, KK, QQ, AKs, AKo -- squeezes at ~100% frequency
    Strong hands: JJ, TT, AQs, AQo -- squeeze vs wide raiser

  BLUFF SQUEEZES:
    Suited Aces: A2s-A5s (blocker + flush equity)
    Small suited connectors: 76s, 65s (realize equity when called)
    Blocker combos: K9s (blocks KK, has equity)

  AVOID SQUEEZING:
    Hands that want to see cheap flops: small pairs (22-66) unless deep
    Off-suit hands with no blockers (K8o, Q9o)
    Multi-way pots: squeeze less (more callers = less fold equity)

DISTINCT FROM:
  preflop_equilibrium_chart.py:  General preflop strategy
  three_bet_range.py:            General 3-bet ranges (heads-up)
  THIS MODULE:                   SQUEEZE-specific (open + 1+ callers);
                                 dead money math; multi-caller adjustments

Usage:
    from poker.preflop_squeeze_range import build_squeeze_range, SqueezeDecision, psq_one_liner

    result = build_squeeze_range(
        hero_hand='ATs',
        hero_position='btn',
        villain_position='utg',
        num_callers=1,
        raiser_vpip=0.28,
        raiser_pfr=0.20,
        open_raise_size_bb=3.0,
        stack_bb=100.0,
        hero_history_3bet=0.08,
        pot_bb=8.5,
    )
    print(psq_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Value hands that should squeeze at high frequency
VALUE_SQUEEZE_HANDS = {
    'AA', 'KK', 'QQ', 'JJ', 'TT',
    'AKs', 'AKo', 'AQs', 'AQo',
    'AJs',
}

# Bluff squeeze hands (blockers + equity)
BLUFF_SQUEEZE_HANDS = {
    'A5s', 'A4s', 'A3s', 'A2s',  # ace blockers + nut flush potential
    'KQs', 'K9s',                  # K blocker
    '76s', '65s', '54s',           # suited connectors
    'ATs', 'A9s',                  # semi-value squeeze/bluff
    'KJs',
}

# Hands to NOT squeeze (play differently)
NO_SQUEEZE_HANDS = {
    '22', '33', '44', '55', '66',   # small pairs want cheap flops
    'KTo', 'QJo', 'JTo',            # no blockers, no equity
}


def _hand_category(hand: str) -> str:
    """Categorize hand for squeeze decision."""
    if hand in VALUE_SQUEEZE_HANDS:
        return 'value'
    elif hand in BLUFF_SQUEEZE_HANDS:
        return 'bluff'
    elif hand in NO_SQUEEZE_HANDS:
        return 'avoid'
    elif hand.endswith('s') or 'A' in hand[0]:
        return 'marginal'
    else:
        return 'avoid'


def _squeeze_size_bb(
    open_raise_bb: float,
    num_callers: int,
    stack_bb: float,
) -> float:
    """Recommended squeeze size in BB."""
    # Base: 3x the raise
    multiplier = 3.0 + num_callers * 0.75  # more callers = bigger squeeze
    base = open_raise_bb * multiplier
    # Add 1BB per caller for dead money
    base += num_callers * 1.5
    # Cap at 1/4 of effective stack
    base = min(base, stack_bb * 0.25)
    return round(base, 1)


def _fold_equity(
    raiser_vpip: float,
    raiser_pfr: float,
    num_callers: int,
    hero_position: str,
) -> float:
    """Estimated fold equity for the squeeze."""
    # Raiser folds some of their opens that couldn't 4bet
    raiser_openness = raiser_vpip - raiser_pfr  # passivity gap
    raiser_fold_rate = 0.50 + raiser_openness * 0.5  # wider range = more foldable

    # Each caller makes squeeze harder (they entered voluntarily = strong range)
    caller_fold_rate = 0.45 - (num_callers - 1) * 0.10

    # Position adjustment: IP squeezer = better fold equity
    pos_adj = 0.05 if hero_position in ('btn', 'co') else -0.03

    combined = (raiser_fold_rate * 0.60 + caller_fold_rate * 0.40) + pos_adj
    return round(min(0.75, max(0.30, combined)), 3)


def _squeeze_ev(
    dead_money_bb: float,
    fold_equity: float,
    squeeze_size_bb: float,
    open_raise_bb: float,
) -> float:
    """EV estimate of the squeeze."""
    net_risk = squeeze_size_bb - open_raise_bb  # what we risk beyond calling
    ev = fold_equity * dead_money_bb - (1 - fold_equity) * net_risk
    return round(ev, 2)


def _should_squeeze(
    hand_cat: str,
    fold_equity: float,
    ev: float,
    num_callers: int,
    hero_3bet: float,
) -> bool:
    if hand_cat == 'avoid':
        return False
    if num_callers >= 3:
        return hand_cat == 'value'  # too many callers to bluff
    if hand_cat == 'value':
        return True
    if hand_cat == 'bluff':
        return fold_equity >= 0.45 and ev >= 0
    if hand_cat == 'marginal':
        return fold_equity >= 0.55 and ev >= 2.0
    return False


@dataclass
class SqueezeDecision:
    # Inputs
    hero_hand: str
    hero_position: str
    villain_position: str
    num_callers: int
    raiser_vpip: float
    raiser_pfr: float
    open_raise_size_bb: float
    stack_bb: float
    hero_history_3bet: float
    pot_bb: float

    # Analysis
    hand_category: str        # 'value' / 'bluff' / 'marginal' / 'avoid'
    squeeze_size_bb: float
    fold_equity: float
    squeeze_ev: float
    should_squeeze: bool
    dead_money_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def build_squeeze_range(
    hero_hand: str = 'ATs',
    hero_position: str = 'btn',
    villain_position: str = 'utg',
    num_callers: int = 1,
    raiser_vpip: float = 0.28,
    raiser_pfr: float = 0.20,
    open_raise_size_bb: float = 3.0,
    stack_bb: float = 100.0,
    hero_history_3bet: float = 0.08,
    pot_bb: float = 8.5,
) -> SqueezeDecision:
    """
    Build squeeze range and recommend squeeze decision.

    Args:
        hero_hand:             Hero's hand (e.g., 'ATs', 'KK', 'A5s')
        hero_position:         Hero's position
        villain_position:      Raiser's position
        num_callers:           Number of callers before hero (1+ = squeeze spot)
        raiser_vpip:           Raiser's VPIP stat
        raiser_pfr:            Raiser's PFR stat
        open_raise_size_bb:    Size of original raise in BB
        stack_bb:              Effective stack in BB
        hero_history_3bet:     Hero's 3-bet frequency (affects credibility)
        pot_bb:                Current pot before action

    Returns:
        SqueezeDecision
    """
    hand_cat = _hand_category(hero_hand)
    squeeze_sz = _squeeze_size_bb(open_raise_size_bb, num_callers, stack_bb)
    dead_money = pot_bb - open_raise_size_bb  # callers' contribution
    fold_eq = _fold_equity(raiser_vpip, raiser_pfr, num_callers, hero_position)
    ev = _squeeze_ev(dead_money, fold_eq, squeeze_sz, open_raise_size_bb)
    do_squeeze = _should_squeeze(hand_cat, fold_eq, ev, num_callers, hero_history_3bet)

    action_str = 'SQUEEZE' if do_squeeze else f'{"CALL" if hand_cat != "avoid" else "FOLD"}'

    verdict = (
        f'[PSQ {hero_hand}|{hero_position}|{num_callers}c] '
        f'{action_str} | ev={ev:+.1f}BB fold_eq={fold_eq:.0%} size={squeeze_sz:.1f}BB'
    )

    reasoning = (
        f'Squeeze: {hero_hand} at {hero_position} vs {villain_position} open + {num_callers} caller(s). '
        f'Hand category={hand_cat}. Squeeze size={squeeze_sz:.1f}BB. '
        f'Dead money={dead_money:.1f}BB. Fold equity={fold_eq:.0%}. EV={ev:+.1f}BB. '
        f'Decision: {action_str}.'
    )

    tips = []

    tips.append(
        f'SQUEEZE SIZING: {squeeze_sz:.1f}BB vs {num_callers} caller(s). '
        f'Formula: 3x raise ({open_raise_size_bb:.1f}BB) + {num_callers} * 1.5BB dead money = {squeeze_sz:.1f}BB. '
        f'Bigger squeeze with more callers -- protects hand equity.'
    )

    tips.append(
        f'DEAD MONEY: {dead_money:.1f}BB in pot before your squeeze. '
        f'This improves your immediate odds and pot size. '
        f'Fold equity = {fold_eq:.0%}: expect both villain(s) to fold {fold_eq:.0%} of the time.'
    )

    if hand_cat == 'value':
        tips.append(
            f'VALUE SQUEEZE: {hero_hand} is a premium hand. '
            f'Squeeze at full size to get called with strong premium. '
            f'Raiser\'s range is capped (no 4bet earlier = likely no AA/KK). '
            f'Caller is cold-calling your 3bet with relatively uncapped range.'
        )
    elif hand_cat == 'bluff':
        tips.append(
            f'BLUFF SQUEEZE: {hero_hand} has blocker value. '
            f'Optimal bluff squeeze frequency: around {fold_eq:.0%} of the time. '
            f'If you have ace blocker (A-high), villain is less likely to have AA/AK. '
            f'Mix in folds to avoid being too predictable at low fold_equity.'
        )
    elif hand_cat == 'avoid':
        tips.append(
            f'AVOID SQUEEZING: {hero_hand} is not a good squeeze candidate. '
            f'No blockers + low equity = bad bluff. No premium value = bad value bet. '
            f'Fold and wait for better spots.'
        )

    if num_callers >= 2:
        tips.append(
            f'MULTI-WAY SQUEEZE: {num_callers} callers significantly reduces fold equity. '
            f'Each additional caller reduces your fold equity by ~10%. '
            f'Only squeeze value hands (value category) in multi-way spots.'
        )

    if hero_history_3bet <= 0.04:
        tips.append(
            f'TIGHT 3BET IMAGE (history={hero_history_3bet:.0%}): '
            f'Villains will respect your squeeze more. '
            f'Good time to add some bluff squeezes (A2s-A5s). '
            f'Also means your value squeezes get more action -- good for premium hands.'
        )
    elif hero_history_3bet >= 0.15:
        tips.append(
            f'WIDE 3BET IMAGE (history={hero_history_3bet:.0%}): '
            f'Villains may 4bet light against you. '
            f'Focus on value squeezes. Be more selective with bluff squeezes.'
        )

    return SqueezeDecision(
        hero_hand=hero_hand,
        hero_position=hero_position,
        villain_position=villain_position,
        num_callers=num_callers,
        raiser_vpip=raiser_vpip,
        raiser_pfr=raiser_pfr,
        open_raise_size_bb=open_raise_size_bb,
        stack_bb=stack_bb,
        hero_history_3bet=hero_history_3bet,
        pot_bb=pot_bb,
        hand_category=hand_cat,
        squeeze_size_bb=squeeze_sz,
        fold_equity=fold_eq,
        squeeze_ev=ev,
        should_squeeze=do_squeeze,
        dead_money_bb=dead_money,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def psq_one_liner(r: SqueezeDecision) -> str:
    action = 'SQUEEZE' if r.should_squeeze else 'NO_SQUEEZE'
    return (
        f'[PSQ {r.hero_hand}|{r.hero_position}|{r.num_callers}c] '
        f'{action} | ev={r.squeeze_ev:+.1f}BB fold={r.fold_equity:.0%} size={r.squeeze_size_bb:.1f}BB'
    )
