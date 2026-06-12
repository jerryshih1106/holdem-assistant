# -*- coding: utf-8 -*-
"""cbet_fold_stat_guide.py -- Fold-to-cbet stat exploitation guide."""

from dataclasses import dataclass, field
from typing import List

FOLD_TO_CBET_CATEGORY: dict = {
    'very_low': (0.0,  0.30),
    'low':      (0.30, 0.42),
    'standard': (0.42, 0.55),
    'high':     (0.55, 0.68),
    'very_high':(0.68, 1.00),
}

# Breakeven fold % by cbet size (fraction of pot)
BE_FOLD_BY_SIZE: dict = {
    0.33: 0.25,
    0.50: 0.33,
    0.67: 0.40,
    1.0:  0.50,
}


def _fold_cat(f2c: float) -> str:
    if f2c < 0.30:
        return 'very_low'
    if f2c < 0.42:
        return 'low'
    if f2c < 0.55:
        return 'standard'
    if f2c < 0.68:
        return 'high'
    return 'very_high'


def _be_fold_pct(cbet_pct: float) -> float:
    """Return breakeven fold % for a cbet of cbet_pct of pot."""
    # BE = cbet_size / (pot + cbet_size) = cbet_pct / (1 + cbet_pct)
    return round(cbet_pct / (1.0 + cbet_pct), 3)


def _cbet_bluff_ev(f2c: float, cbet_bb: float, pot_bb: float) -> float:
    """EV of a pure bluff cbet in BB."""
    win = pot_bb * f2c
    lose = cbet_bb * (1.0 - f2c)
    return round(win - lose, 2)


def _bluff_recommendation(f2c_cat: str) -> str:
    recs = {
        'very_low':  'NO_BLUFF',
        'low':       'MINIMAL_BLUFF',
        'standard':  'SELECTIVE_BLUFF',
        'high':      'BLUFF_FREELY',
        'very_high': 'BLUFF_HEAVILY',
    }
    return recs.get(f2c_cat, 'SELECTIVE_BLUFF')


@dataclass
class CbetFoldResult:
    fold_to_cbet: float
    cbet_bb: float
    pot_bb: float
    f2c_category: str
    bluff_recommendation: str
    bluff_ev: float
    be_fold_pct: float
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_cbet_fold_stat(
    fold_to_cbet: float = 0.50,
    cbet_bb: float = 5.0,
    pot_bb: float = 10.0,
    cbet_size_fraction: float = 0.50,
) -> CbetFoldResult:
    cat = _fold_cat(fold_to_cbet)
    rec = _bluff_recommendation(cat)
    ev = _cbet_bluff_ev(fold_to_cbet, cbet_bb, pot_bb)
    be = _be_fold_pct(cbet_size_fraction)

    tips = []
    tips.append(
        f"Min fold for profitability at {cbet_size_fraction:.0%} pot cbet is ~{be:.0%}."
    )
    if fold_to_cbet > 0.55:
        tips.append(
            "Villain folds to cbet often -- barrel with draws and air on favorable runouts."
        )
    if fold_to_cbet < 0.42:
        tips.append(
            "Villain calls down too much -- downsize cbets with value; eliminate bluffs."
        )
    if ev > 0:
        tips.append(
            f"Bluff cbet EV = +{ev:.1f} BB -- profitable to fire at current sizing."
        )
    tips.append(
        "Board texture matters: fold-to-cbet stat is more reliable on dry boards."
    )

    reasoning = (
        f"Fold to cbet={fold_to_cbet:.0%} ({cat}): {rec}. "
        f"Bluff EV={ev:+.1f} BB. BE fold={be:.0%} for {cbet_size_fraction:.0%} pot sizing."
    )
    verdict = rec

    return CbetFoldResult(
        fold_to_cbet=fold_to_cbet,
        cbet_bb=cbet_bb,
        pot_bb=pot_bb,
        f2c_category=cat,
        bluff_recommendation=rec,
        bluff_ev=ev,
        be_fold_pct=be,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def cbet_fold_one_liner(r: CbetFoldResult) -> str:
    return (
        f"[FCBET f2c={r.fold_to_cbet:.0%}] "
        f"cat={r.f2c_category} bluff={r.bluff_recommendation}"
    )
