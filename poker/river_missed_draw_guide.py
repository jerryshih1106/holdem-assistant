# -*- coding: cp950 -*-
"""river_missed_draw_guide.py -- River missed draw: bluff or give-up strategy guide."""

from dataclasses import dataclass, field
from typing import List

VILLAIN_FOLD_FREQ_MISSED: dict = {
    'nit':             0.68,
    'reg':             0.52,
    'fish':            0.30,
    'lag':             0.45,
    'calling_station': 0.18,
}

BLUFF_SIZE_BY_VILLAIN: dict = {
    'nit':             0.75,
    'reg':             0.65,
    'fish':            0.00,
    'lag':             0.85,
    'calling_station': 0.00,
}

BLOCKER_BLUFF_BONUS: float = 0.08
MISSED_DRAW_BLUFF_EV_MIN: float = 0.0


def _fold_freq(villain_type: str) -> float:
    return VILLAIN_FOLD_FREQ_MISSED.get(villain_type, 0.40)


def _bluff_size_pct(villain_type: str) -> float:
    return BLUFF_SIZE_BY_VILLAIN.get(villain_type, 0.60)


def _bluff_ev(fold_freq: float, bluff_bb: float, pot_bb: float) -> float:
    call_freq = 1.0 - fold_freq
    ev = fold_freq * pot_bb - call_freq * bluff_bb
    return round(ev, 4)


def _missed_draw_action(villain_type: str, has_blocker: bool) -> str:
    fold_f = _fold_freq(villain_type)
    size = _bluff_size_pct(villain_type)
    if size == 0.00:
        return 'GIVE_UP'
    adj_fold = fold_f + (BLOCKER_BLUFF_BONUS if has_blocker else 0.0)
    if adj_fold >= 0.55 and size >= 0.75:
        return 'BLUFF_LARGE'
    if adj_fold >= 0.40:
        return 'BLUFF_MEDIUM'
    return 'GIVE_UP'


@dataclass
class RiverMissedDrawResult:
    villain_type: str
    has_blocker: bool
    pot_bb: float
    stack_bb: float
    fold_freq: float
    bluff_size_pct: float
    bluff_ev: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_river_missed_draw(
    villain_type: str = 'reg',
    has_blocker: bool = False,
    pot_bb: float = 20.0,
    stack_bb: float = 60.0,
) -> RiverMissedDrawResult:
    fold_f = _fold_freq(villain_type)
    size_pct = _bluff_size_pct(villain_type)
    bluff_bb = pot_bb * size_pct
    ev = _bluff_ev(fold_f + (BLOCKER_BLUFF_BONUS if has_blocker else 0.0), bluff_bb, pot_bb)
    action = _missed_draw_action(villain_type, has_blocker)

    tips = []
    tips.append(
        "Missed draw on river = zero equity -- only continue if bluff EV is positive."
    )
    tips.append(
        "MDF (minimum defense frequency) = 1 - 1/(1 + bluff_size/pot) -- villain must defend this % or you profit."
    )
    if has_blocker:
        tips.append("Blocker present: +8% fold equity boost -- preferred bluffing hand vs villain's likely nutted combos.")
    if villain_type in ('fish', 'calling_station'):
        tips.append("vs fish/calling station: give up missed draws -- their fold frequency is too low for bluffs to profit.")
    if villain_type == 'nit':
        tips.append("vs nit: large river bluff has high EV -- nits fold to large bets at 68%+ frequency.")
    if villain_type == 'lag':
        tips.append("vs LAG: medium-to-large bluff can work; LAGs bluff a lot but also call down wide -- use blockers.")
    if size_pct == 0.0:
        tips.append("Recommended action: give up -- bluffing this villain type is not profitable with missed draw.")

    reasoning = (
        f"Missed draw villain={villain_type} blocker={has_blocker} fold_freq={fold_f:.0%} "
        f"bluff_size={size_pct*100:.0f}% bluff_ev={ev:.2f}bb action={action}."
    )
    verdict = action

    return RiverMissedDrawResult(
        villain_type=villain_type,
        has_blocker=has_blocker,
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        fold_freq=fold_f,
        bluff_size_pct=size_pct,
        bluff_ev=ev,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def river_missed_draw_one_liner(r: RiverMissedDrawResult) -> str:
    blocker = 'Y' if r.has_blocker else 'N'
    return (
        f"[RMD vt={r.villain_type} blocker={blocker}] "
        f"fold={r.fold_freq*100:.0f}% bluff_ev={r.bluff_ev:.2f} action={r.action}"
    )
