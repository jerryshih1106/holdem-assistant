"""
Check-Raise Sizing Guide (check_raise_sizing_guide.py)

Calibrates check-raise size based on villain's cbet size, board texture,
and intended hand range (value vs semi-bluff CR).

THEORY:
  CHECK-RAISE SIZING PRINCIPLES:
  CR size must be large enough to: (1) price out draws when value-raising,
  (2) achieve fold equity as semi-bluff, (3) target correct SPR for stacking.

  CR MULTIPLIERS BY CBET SIZE:
  Small cbet (<=33% pot): CR to 3.2-3.5x cbet (absolute size ~60-70% of pot)
  Medium cbet (33-60%):   CR to 2.8-3.2x cbet
  Large cbet (60-85%):    CR to 2.2-2.8x cbet
  Overbet cbet (>85%):    CR to 2.0-2.2x cbet (pot committed after CR)

  ABSOLUTE SIZE TARGETS:
  CR should typically be 50-80% of pot as absolute amount.
  Too small: villain calls profitably with any draw.
  Too large: gives villain wrong price to fold (miss value).

  BOARD TEXTURE:
  Wet board: larger CR (more draws to price out)
  Dry board: smaller CR (no draws; pure value or pure bluff)

  RANGE TYPE:
  Value CR: slightly smaller (want to get called; maximize stacks)
  Bluff CR: slightly larger (need fold equity; make villain fold)
  Semi-bluff CR: medium (balance between fold equity and implied odds if called)

DISTINCT FROM:
  check_raise_frequency_guide.py: HOW OFTEN to check-raise
  check_raise.py:                 General check-raise logic
  checkraise_advisor.py:          Advice on specific CR spots
  THIS MODULE:                    HOW MUCH to CR; multiplier calibration;
                                  absolute size targets; board/range adjustments.
"""

from dataclasses import dataclass, field
from typing import List

CR_MULTIPLIER_BY_CBET_SIZE: dict = {
    'small':    3.3,
    'medium':   2.9,
    'large':    2.4,
    'overbet':  2.1,
}

CBET_SIZE_CATEGORY_THRESHOLDS: dict = {
    'small':   0.33,
    'medium':  0.60,
    'large':   0.85,
    'overbet': 9.99,
}

BOARD_CR_SIZE_MODIFIER: dict = {
    'dry':      -0.15,
    'semi_wet':  0.00,
    'wet':      +0.15,
    'monotone': +0.10,
    'paired':   -0.10,
}

CR_RANGE_TYPE_MODIFIER: dict = {
    'value_cr':       -0.10,
    'semi_bluff_cr':   0.00,
    'bluff_cr':       +0.10,
}

MIN_CR_POT_PCT: float = 0.45
MAX_CR_POT_PCT: float = 2.50


def _cbet_size_category(cbet_pct: float) -> str:
    for cat, thresh in CBET_SIZE_CATEGORY_THRESHOLDS.items():
        if cbet_pct <= thresh:
            return cat
    return 'overbet'


def _cr_size_bb(
    cbet_pct: float,
    pot_bb: float,
    board_texture: str,
    cr_range_type: str,
) -> float:
    cbet_bb = pot_bb * cbet_pct
    cat = _cbet_size_category(cbet_pct)
    multiplier = CR_MULTIPLIER_BY_CBET_SIZE.get(cat, 2.8)
    raw_cr_bb = cbet_bb * multiplier
    board_adj_bb = pot_bb * BOARD_CR_SIZE_MODIFIER.get(board_texture, 0.0)
    range_adj_bb = pot_bb * CR_RANGE_TYPE_MODIFIER.get(cr_range_type, 0.0)
    total_cr_bb = raw_cr_bb + board_adj_bb + range_adj_bb
    min_cr = pot_bb * MIN_CR_POT_PCT
    max_cr = pot_bb * MAX_CR_POT_PCT
    return round(min(max_cr, max(min_cr, total_cr_bb)), 1)


def _spr_after_cr(cr_bb: float, pot_bb: float, stack_bb: float) -> float:
    pot_after_call = pot_bb + cr_bb * 2
    stack_after = stack_bb - cr_bb
    if pot_after_call <= 0:
        return 0.0
    return round(max(0.0, stack_after / pot_after_call), 2)


@dataclass
class CheckRaiseSizingResult:
    cbet_pct: float
    pot_bb: float
    board_texture: str
    cr_range_type: str
    stack_bb: float

    cbet_category: str
    cr_multiplier: float
    optimal_cr_bb: float
    cr_as_pct_pot: float
    spr_if_called: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_check_raise_sizing(
    cbet_pct: float = 0.50,
    pot_bb: float = 10.0,
    board_texture: str = 'semi_wet',
    cr_range_type: str = 'semi_bluff_cr',
    stack_bb: float = 100.0,
) -> CheckRaiseSizingResult:
    """
    Calibrate check-raise size vs villain's cbet.

    Args:
        cbet_pct:       Villain's cbet as fraction of pot (0.33, 0.50, 0.75, etc.)
        pot_bb:         Pot size in BB before villain cbets
        board_texture:  Board texture ('dry','semi_wet','wet','monotone','paired')
        cr_range_type:  CR intent ('value_cr','semi_bluff_cr','bluff_cr')
        stack_bb:       Effective stack in BB

    Returns:
        CheckRaiseSizingResult
    """
    cat = _cbet_size_category(cbet_pct)
    multiplier = CR_MULTIPLIER_BY_CBET_SIZE.get(cat, 2.8)
    cr_bb = _cr_size_bb(cbet_pct, pot_bb, board_texture, cr_range_type)
    cr_pct = round(cr_bb / max(pot_bb, 1), 3)
    spr = _spr_after_cr(cr_bb, pot_bb, stack_bb)

    verdict = (
        f'[CRS cbet={cbet_pct:.0%}pot|{board_texture}|{cr_range_type}] '
        f'CR={cr_bb:.1f}BB={cr_pct:.0%}pot mult={multiplier:.1f}x SPR={spr}'
    )

    reasoning = (
        f'CR sizing vs {cbet_pct:.0%} pot cbet ({cat}): '
        f'cbet={pot_bb*cbet_pct:.1f}BB * {multiplier:.1f}x mult = {pot_bb*cbet_pct*multiplier:.1f}BB '
        f'board_adj={BOARD_CR_SIZE_MODIFIER.get(board_texture, 0):+.0%}pot '
        f'range_adj={CR_RANGE_TYPE_MODIFIER.get(cr_range_type, 0):+.0%}pot. '
        f'Final CR={cr_bb:.1f}BB ({cr_pct:.0%} pot). SPR if called={spr}.'
    )

    tips = []

    tips.append(
        f'CR to {cr_bb:.1f}BB ({cr_pct:.0%} pot) vs {cbet_pct:.0%} cbet ({cat}). '
        f'Multiplier {multiplier:.1f}x. SPR if called={spr}. '
        f'{"Low SPR: often committed to stacking off" if spr < 2 else "Good SPR: room for river decisions" if spr < 5 else "High SPR: avoid bloating pot with marginal hands"}.'
    )

    if cr_range_type == 'value_cr':
        tips.append(
            f'VALUE CR: {cr_bb:.1f}BB ({cr_pct:.0%} pot). '
            f'Slightly smaller vs {board_texture} board; want villain to call. '
            f'vs {"wet" if board_texture == "wet" else board_texture} board: '
            f'{"size up to price out villain draws" if board_texture == "wet" else "standard value CR; villain limited draws"}.'
        )
    elif cr_range_type == 'bluff_cr':
        tips.append(
            f'BLUFF CR: {cr_bb:.1f}BB ({cr_pct:.0%} pot). '
            f'Larger size needed for fold equity vs {board_texture} board. '
            f'Villain must fold draws and medium pairs to make this profitable. '
            f'SPR={spr}: {"if called, barrel off with equity" if spr > 1.5 else "small SPR; bluff CR often commits"}.'
        )
    else:
        tips.append(
            f'SEMI-BLUFF CR: {cr_bb:.1f}BB. Balanced fold equity + implied odds. '
            f'If called with draw: continue planning based on SPR={spr}. '
            f'vs {board_texture}: {"many draws benefit from semi-bluff CR" if board_texture in ("wet", "monotone") else "limited draws; CR is more value-focused"}.'
        )

    return CheckRaiseSizingResult(
        cbet_pct=cbet_pct,
        pot_bb=pot_bb,
        board_texture=board_texture,
        cr_range_type=cr_range_type,
        stack_bb=stack_bb,
        cbet_category=cat,
        cr_multiplier=multiplier,
        optimal_cr_bb=cr_bb,
        cr_as_pct_pot=cr_pct,
        spr_if_called=spr,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def crs_one_liner(r: CheckRaiseSizingResult) -> str:
    return (
        f'[CRS cbet={r.cbet_pct:.0%}|{r.board_texture}] '
        f'CR={r.optimal_cr_bb:.1f}BB={r.cr_as_pct_pot:.0%}pot SPR={r.spr_if_called}'
    )
