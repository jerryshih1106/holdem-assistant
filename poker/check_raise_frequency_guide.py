"""
Check-Raise Frequency Guide (check_raise_frequency_guide.py)

How often to check-raise from OOP when villain c-bets. Balances:
1. Value check-raises (sets, two pair, strong top pair)
2. Semi-bluff check-raises (flush draws, OESDs on wet boards)
3. Polarized protection (prevent villain from betting wide profitably)

THEORY:
  CHECK-RAISE FREQUENCY BY BOARD TEXTURE:
  - Dry board: check-raise less; semi-bluffs rare; only value hands
  - Wet/monotone: check-raise more; strong semi-bluffs (fd+sd combos) available
  - Paired boards: check-raise sparingly (full houses/quads mainly)

  VALUE vs SEMI-BLUFF RATIO IN CHECK-RAISES:
  On wet boards: roughly 50% value, 50% semi-bluff check-raises
  On dry boards: mostly value (70-80%); few semi-bluffs

  WHEN TO CHECK-RAISE:
  1. Strong value: Set, two pair, strong top pair on wet board
  2. Semi-bluff: Combo draw (fd+oesd), nut flush draw with backdoor
  3. Range protection: Prevent villain from betting all their air profitably
  4. Exploit villain's high c-bet frequency: high c-bet freq villain -> check-raise more

  SIZING:
  IP: 2.5-3x the bet
  OOP vs small c-bet: 3x (to build pot correctly)
  OOP vs large c-bet: 2x (already built; reraise small to keep in)

  CHECK-RAISE vs VILLAIN TYPE:
  vs Fish: check-raise less (fish check back too often; lead for value instead)
  vs LAG (high c-bet freq): check-raise more (exploit their wide c-bet range)
  vs Nit: check-raise only very strong hands (nit rarely bluffs; don't bluff-raise nit)

DISTINCT FROM:
  check_raise.py:                 Check-raise mechanics
  facing_check_raise_response.py: Response to villain check-raise
  turn_check_raise.py:            Turn-specific check-raise
  THIS MODULE:                    CHECK-RAISE FREQUENCY calibration; when and
                                  how often to check-raise by texture/villain.
"""

from dataclasses import dataclass, field
from typing import List


BASELINE_CR_FREQ: dict = {
    'dry':      0.09,
    'semi_wet': 0.14,
    'wet':      0.20,
    'monotone': 0.17,
    'paired':   0.07,
}

VILLAIN_CR_ADJUSTMENT: dict = {
    'fish':            -0.06,
    'calling_station': -0.04,
    'rec':             -0.02,
    'nit':             -0.06,
    'lag':             +0.08,
    'reg':              0.00,
}

STREET_CR_MODIFIER: dict = {
    'flop':  1.00,
    'turn':  0.85,
    'river': 0.60,
}

VILLAIN_CBET_FREQ_CR_BOOST: dict = {
    'very_high': +0.08,
    'high':      +0.04,
    'medium':     0.00,
    'low':       -0.06,
    'very_low':  -0.10,
}

CR_SIZING_MULTIPLIER: dict = {
    'small_cbet': 3.2,
    'medium_cbet': 3.0,
    'large_cbet':  2.2,
    'pot_cbet':    2.0,
}

VALUE_CR_THRESHOLD: float = 0.72
SEMI_BLUFF_CR_THRESHOLD: float = 0.45


def _cbet_size_category(cbet_frac: float) -> str:
    if cbet_frac <= 0.35:
        return 'small_cbet'
    if cbet_frac <= 0.60:
        return 'medium_cbet'
    if cbet_frac <= 0.90:
        return 'large_cbet'
    return 'pot_cbet'


def _cr_frequency(
    board_texture: str,
    villain_type: str,
    street: str,
    villain_cbet_tendency: str,
) -> float:
    base = BASELINE_CR_FREQ.get(board_texture, 0.12)
    vil_adj = VILLAIN_CR_ADJUSTMENT.get(villain_type, 0.00)
    str_mod = STREET_CR_MODIFIER.get(street, 1.00)
    cbet_boost = VILLAIN_CBET_FREQ_CR_BOOST.get(villain_cbet_tendency, 0.00)
    result = (base + vil_adj + cbet_boost) * str_mod
    return round(min(0.40, max(0.03, result)), 3)


def _cr_sizing(cbet_frac: float, pot_bb: float) -> float:
    cat = _cbet_size_category(cbet_frac)
    mult = CR_SIZING_MULTIPLIER.get(cat, 3.0)
    bet_amount = cbet_frac * pot_bb
    return round(bet_amount * mult, 1)


def _cr_hand_category(hand_sdv: float, has_draw: bool) -> str:
    if hand_sdv >= VALUE_CR_THRESHOLD:
        return 'VALUE_CR'
    if has_draw and hand_sdv >= SEMI_BLUFF_CR_THRESHOLD:
        return 'SEMI_BLUFF_CR'
    if hand_sdv >= 0.55:
        return 'VALUE_CR_THIN'
    return 'DO_NOT_CR'


@dataclass
class CheckRaiseFrequencyResult:
    board_texture: str
    villain_type: str
    street: str
    villain_cbet_tendency: str
    cbet_frac: float
    hand_sdv: float
    has_draw: bool

    cr_frequency: float
    cr_sizing_bb: float
    hand_cr_category: str
    sizing_category: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_check_raise_frequency(
    board_texture: str = 'wet',
    villain_type: str = 'reg',
    street: str = 'flop',
    villain_cbet_tendency: str = 'medium',
    cbet_frac: float = 0.50,
    pot_bb: float = 20.0,
    hand_sdv: float = 0.70,
    has_draw: bool = False,
) -> CheckRaiseFrequencyResult:
    """
    Recommend check-raise frequency and sizing.

    Args:
        board_texture:          Board texture ('dry','semi_wet','wet','monotone','paired')
        villain_type:           Villain type ('fish','rec','nit','lag','reg')
        street:                 Current street ('flop','turn','river')
        villain_cbet_tendency:  Villain c-bet frequency ('very_high','high','medium','low','very_low')
        cbet_frac:              Villain's c-bet size as fraction of pot
        pot_bb:                 Current pot in BB (before the c-bet)
        hand_sdv:               Hero hand SDV (0-1)
        has_draw:               Whether hero has a draw component

    Returns:
        CheckRaiseFrequencyResult
    """
    freq = _cr_frequency(board_texture, villain_type, street, villain_cbet_tendency)
    sizing = _cr_sizing(cbet_frac, pot_bb)
    hand_cat = _cr_hand_category(hand_sdv, has_draw)
    size_cat = _cbet_size_category(cbet_frac)

    verdict = (
        f'[CRF {board_texture}|{villain_type}|{street}] '
        f'cr_freq={freq:.0%} size={sizing:.0f}BB category={hand_cat}'
    )

    reasoning = (
        f'Check-raise frequency: {board_texture} board, {villain_type} ({street}). '
        f'Villain c-bet tendency={villain_cbet_tendency}, size={cbet_frac:.0%}pot. '
        f'Hero SDV={hand_sdv:.0%}, draw={has_draw}. '
        f'CR frequency={freq:.0%}. Sizing={sizing:.0f}BB ({size_cat}). '
        f'Hand CR category: {hand_cat}.'
    )

    tips = []

    tips.append(
        f'CHECK-RAISE FREQUENCY: {freq:.0%} of OOP range on {board_texture} {street}. '
        f'Value CRs + semi-bluff CRs = {freq:.0%} of range. '
        f'{"High frequency -- wet board enables many semi-bluff CRs." if freq >= 0.18 else "Moderate CR frequency." if freq >= 0.12 else "Low CR frequency -- mostly value hands only."}'
    )

    tips.append(
        f'SIZING: CR to {sizing:.0f}BB ({size_cat} villain bet = {cbet_frac:.0%}pot). '
        f'Sizing multiplier: {CR_SIZING_MULTIPLIER.get(size_cat, 3.0):.1f}x villain bet. '
        f'{"Small c-bet: raise large (deny equity + build pot)." if size_cat == "small_cbet" else "Large c-bet: smaller multiplier (pot already built)."}'
    )

    tips.append(
        f'YOUR HAND ({hand_cr_cat_desc(hand_cat)}): SDV={hand_sdv:.0%}, draw={has_draw}. '
        f'{"Check-raise for VALUE -- strong hand; build pot." if hand_cat == "VALUE_CR" else "Semi-bluff CR -- draw + some equity; two ways to win." if hand_cat == "SEMI_BLUFF_CR" else "Thin value CR possible." if hand_cat == "VALUE_CR_THIN" else "Do NOT check-raise this hand -- too weak for CR."}'
    )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Increase CR frequency +{VILLAIN_CR_ADJUSTMENT["lag"]:.0%} (total={freq:.0%}). '
            f'LAG c-bets very wide -- your CR gains more fold equity. '
            f'Semi-bluff CRs are profitable vs LAG high c-bet frequency.'
        )
    elif villain_type in ('fish', 'nit'):
        tips.append(
            f'VS {villain_type.upper()}: Reduce CR frequency ({VILLAIN_CR_ADJUSTMENT[villain_type]:+.0%}). '
            f'{"Fish check back too often; lead for value instead of check-raising." if villain_type == "fish" else "Nit bets rarely for value; CR mostly strong value; no semi-bluff CRs."}'
        )

    return CheckRaiseFrequencyResult(
        board_texture=board_texture,
        villain_type=villain_type,
        street=street,
        villain_cbet_tendency=villain_cbet_tendency,
        cbet_frac=cbet_frac,
        hand_sdv=hand_sdv,
        has_draw=has_draw,
        cr_frequency=freq,
        cr_sizing_bb=sizing,
        hand_cr_category=hand_cat,
        sizing_category=size_cat,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hand_cr_cat_desc(cat: str) -> str:
    return {
        'VALUE_CR': 'Value Check-Raise',
        'SEMI_BLUFF_CR': 'Semi-Bluff CR',
        'VALUE_CR_THIN': 'Thin Value CR',
        'DO_NOT_CR': 'Check-Call or Check-Fold',
    }.get(cat, cat)


def crf_one_liner(r: CheckRaiseFrequencyResult) -> str:
    return (
        f'[CRF {r.board_texture}|{r.villain_type}|{r.street}] '
        f'cr_freq={r.cr_frequency:.0%} size={r.cr_sizing_bb:.0f}BB'
    )
