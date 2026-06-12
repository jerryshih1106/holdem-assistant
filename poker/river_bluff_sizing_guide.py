"""
River Bluff Sizing Guide (river_bluff_sizing_guide.py)

Calibrates optimal river bluff size to maximize EV given villain's
estimated fold frequency and pot size.

THEORY:
  BLUFF EV FORMULA:
  Bluff_EV = fold_freq * pot - (1 - fold_freq) * bet
  Break-even when: fold_freq * pot = (1 - fold_freq) * bet
  -> fold_freq_needed = bet / (pot + bet)

  OPTIMAL BLUFF SIZE:
  For pure EV: any size works when fold_freq > pot_odds_needed.
  To MAXIMIZE EV: larger size when villain folds frequently; smaller when infrequently.
  Balanced GTO bluff: size to make villain indifferent.

  VILLAIN FOLD FREQUENCY ESTIMATES:
  Nit:              65-75% on river (folds most non-nut hands)
  Fish:             30-45% (calls too wide; bluffing fish is -EV)
  Calling_station:  15-25% (almost never folds; don't bluff)
  LAG:              40-55% (balanced; folds some; calls wide)
  Reg:              48-58% (near MDF; calibrated to avoid exploitation)

  BLOCKER EFFECT:
  Holding a key blocker (e.g., Ace on Ax board) reduces villain's calling range.
  Increases effective fold frequency by ~5-8%.

  BOARD TEXTURE IMPACT:
  Dry river: fewer missed draws in villain range -> lower fold freq
  Wet/completed river: more missed draws -> higher fold freq

DISTINCT FROM:
  river_bluff.py:           General river bluff decision
  value_bluff_ratio_advisor.py: Bluff-to-value ratio calibration
  bluff_planner.py:          Multi-street bluff planning
  THIS MODULE:               SIZING for river bluffs; EV calculation;
                             optimal size vs villain fold frequency.
"""

from dataclasses import dataclass, field
from typing import List

VILLAIN_FOLD_FREQ_RIVER: dict = {
    'fish':            0.38,
    'calling_station': 0.20,
    'nit':             0.70,
    'lag':             0.48,
    'rec':             0.45,
    'reg':             0.53,
}

BOARD_FOLD_ADJ: dict = {
    'dry':          -0.05,
    'semi_wet':      0.00,
    'wet':          +0.08,
    'flush_draw_missed': +0.12,
    'monotone':     +0.06,
    'paired':       -0.03,
}

BLOCKER_FOLD_ADJ: float = 0.07

BLUFF_SIZE_BY_FOLD_FREQ: dict = {
    'very_high': 1.00,   # fold_freq > 0.65: pot-size bluff (very profitable)
    'high':      0.75,   # 0.55-0.65: 3/4 pot
    'medium':    0.55,   # 0.45-0.55: half-pot ish
    'low':       0.33,   # 0.35-0.45: small bluff (marginally profitable)
    'very_low':  0.00,   # < 0.35: don't bluff (not profitable)
}

FOLD_FREQ_THRESHOLDS: dict = {
    'very_high': 0.65,
    'high':      0.55,
    'medium':    0.45,
    'low':       0.35,
    'very_low':  0.00,
}


def _adjusted_fold_freq(
    villain_type: str,
    board_texture: str,
    has_blocker: bool,
) -> float:
    base = VILLAIN_FOLD_FREQ_RIVER.get(villain_type, 0.50)
    board_adj = BOARD_FOLD_ADJ.get(board_texture, 0.00)
    blocker_adj = BLOCKER_FOLD_ADJ if has_blocker else 0.0
    freq = base + board_adj + blocker_adj
    return round(min(0.90, max(0.05, freq)), 3)


def _fold_freq_category(fold_freq: float) -> str:
    for cat, thresh in FOLD_FREQ_THRESHOLDS.items():
        if fold_freq >= thresh:
            return cat
    return 'very_low'


def _optimal_bluff_pct(fold_freq: float) -> float:
    cat = _fold_freq_category(fold_freq)
    return BLUFF_SIZE_BY_FOLD_FREQ.get(cat, 0.0)


def _bluff_ev(fold_freq: float, pot_bb: float, bet_bb: float) -> float:
    return round(fold_freq * pot_bb - (1 - fold_freq) * bet_bb, 2)


def _breakeven_fold_pct(bet_pct: float) -> float:
    if bet_pct <= 0:
        return 1.0
    return round(bet_pct / (1 + bet_pct), 3)


@dataclass
class RiverBluffSizingResult:
    villain_type: str
    board_texture: str
    has_blocker: bool
    pot_bb: float

    estimated_fold_freq: float
    fold_category: str
    optimal_bluff_pct: float
    optimal_bluff_bb: float
    bluff_ev_bb: float
    breakeven_fold_pct: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_river_bluff_sizing(
    villain_type: str = 'reg',
    board_texture: str = 'semi_wet',
    has_blocker: bool = False,
    pot_bb: float = 20.0,
) -> RiverBluffSizingResult:
    """
    Calculate optimal river bluff size.

    Args:
        villain_type:   Villain type ('fish','nit','lag','reg','calling_station')
        board_texture:  River board texture ('dry','semi_wet','wet','flush_draw_missed',etc.)
        has_blocker:    True if hero holds a key blocker card
        pot_bb:         Pot size in BB before villain bet/hero bets

    Returns:
        RiverBluffSizingResult
    """
    fold_freq = _adjusted_fold_freq(villain_type, board_texture, has_blocker)
    fold_cat = _fold_freq_category(fold_freq)
    opt_pct = _optimal_bluff_pct(fold_freq)
    opt_bb = round(pot_bb * opt_pct, 1)
    ev = _bluff_ev(fold_freq, pot_bb, opt_bb) if opt_pct > 0 else 0.0
    be_fold = _breakeven_fold_pct(opt_pct)

    verdict = (
        f'[RBS {villain_type}|{board_texture}|blocker={has_blocker}] '
        f'fold_est={fold_freq:.0%} opt_bluff={opt_pct:.0%}pot={opt_bb:.1f}BB EV={ev:+.1f}BB'
    )

    reasoning = (
        f'River bluff size vs {villain_type}: '
        f'base_fold={VILLAIN_FOLD_FREQ_RIVER.get(villain_type, 0.50):.0%} '
        f'board_adj={BOARD_FOLD_ADJ.get(board_texture, 0):+.0%} '
        f'blocker_adj={BLOCKER_FOLD_ADJ if has_blocker else 0:+.0%}. '
        f'Est_fold={fold_freq:.0%} ({fold_cat}). '
        f'Optimal size={opt_pct:.0%} pot = {opt_bb:.1f}BB. '
        f'EV={ev:+.1f}BB. Breakeven fold={be_fold:.0%}.'
    )

    tips = []

    tips.append(
        f'River bluff sizing vs {villain_type}: estimated fold={fold_freq:.0%}. '
        f'Optimal bluff: {opt_pct:.0%} pot = {opt_bb:.1f}BB (breakeven={be_fold:.0%} fold). '
        f'{"PROFITABLE bluff: fold_freq > breakeven" if fold_freq > be_fold else "MARGINAL/UNPROFITABLE bluff: reconsider"}.'
    )

    if fold_cat in ('very_low', 'low') or opt_pct == 0.0:
        tips.append(
            f'DO NOT BLUFF vs {villain_type}: fold_freq={fold_freq:.0%} too low. '
            f'{"NEVER bluff calling_station; they call 80%+ of range" if villain_type == "calling_station" else "Fish calls too wide; use value bets only"}. '
            f'Check back air on river; save bluffs for spots with better fold equity.'
        )
    elif fold_cat == 'very_high':
        tips.append(
            f'LARGE BLUFF recommended vs {villain_type}: fold_freq={fold_freq:.0%}. '
            f'Pot-size bluff ({opt_pct:.0%}) maximizes EV. '
            f'vs NIT: polarize range; bluff big (nit folds most non-nut hands).'
        )
    else:
        tips.append(
            f'Bluff at {opt_pct:.0%} pot vs {villain_type}. '
            f'EV = +{ev:.1f}BB per attempt when fold_freq={fold_freq:.0%}. '
            f'{"Blocker reduces villain call freq -- slightly larger size OK" if has_blocker else "No blocker: stick to calibrated sizing"}.'
        )

    if has_blocker:
        tips.append(
            f'BLOCKER ADVANTAGE: +{BLOCKER_FOLD_ADJ:.0%} effective fold rate. '
            f'Holding key card reduces villain nut combos; '
            f'opponent calls with fewer strong hands -> fold freq increases.'
        )

    return RiverBluffSizingResult(
        villain_type=villain_type,
        board_texture=board_texture,
        has_blocker=has_blocker,
        pot_bb=pot_bb,
        estimated_fold_freq=fold_freq,
        fold_category=fold_cat,
        optimal_bluff_pct=opt_pct,
        optimal_bluff_bb=opt_bb,
        bluff_ev_bb=ev,
        breakeven_fold_pct=be_fold,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rbs_one_liner(r: RiverBluffSizingResult) -> str:
    return (
        f'[RBS {r.villain_type}|{r.board_texture}] '
        f'fold={r.estimated_fold_freq:.0%} bluff={r.optimal_bluff_pct:.0%}pot EV={r.bluff_ev_bb:+.1f}BB'
    )
