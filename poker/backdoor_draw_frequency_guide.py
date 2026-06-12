# -*- coding: cp950 -*-
"""backdoor_draw_frequency_guide.py -- Backdoor draw (BD FD / BD SD) frequency and cbet guide."""

from dataclasses import dataclass, field
from typing import List

BD_FD_COMPLETION: float = 0.042
BD_SD_COMPLETION: float = 0.040

BD_EQ_VALUE: dict = {
    'bd_fd':  0.042,
    'bd_sd':  0.040,
    'both':   0.082,
}

CBET_EV_BOOST_PER_BD_OUT: float = 0.035

BD_CBET_FREQ_BONUS: dict = {
    'bd_fd':  0.08,
    'bd_sd':  0.06,
    'both':   0.12,
}

MIN_CBET_FREQ_WITH_BD: float = 0.35

BOARD_TEXTURE_CBET_BASE: dict = {
    'dry':      0.55,
    'static':   0.50,
    'wet':      0.45,
    'monotone': 0.40,
}


def _bd_equity(has_bd_fd: bool, has_bd_sd: bool) -> float:
    if has_bd_fd and has_bd_sd:
        return BD_EQ_VALUE['both']
    if has_bd_fd:
        return BD_EQ_VALUE['bd_fd']
    if has_bd_sd:
        return BD_EQ_VALUE['bd_sd']
    return 0.0


def _cbet_freq_with_bd(base_cbet_freq: float, has_bd_fd: bool, has_bd_sd: bool) -> float:
    bonus = 0.0
    if has_bd_fd and has_bd_sd:
        bonus = BD_CBET_FREQ_BONUS['both']
    elif has_bd_fd:
        bonus = BD_CBET_FREQ_BONUS['bd_fd']
    elif has_bd_sd:
        bonus = BD_CBET_FREQ_BONUS['bd_sd']
    adjusted = base_cbet_freq + bonus
    adjusted = max(MIN_CBET_FREQ_WITH_BD, adjusted)
    return round(min(1.0, adjusted), 4)


def _bd_tip(has_bd_fd: bool, has_bd_sd: bool) -> str:
    if has_bd_fd and has_bd_sd:
        return "Both BD draws present: +12% cbet EV boost -- comfortably fire cbet on most boards."
    if has_bd_fd:
        return "BD flush draw: +8% cbet EV boost -- enough to justify marginal cbets."
    if has_bd_sd:
        return "BD straight draw: +6% cbet EV boost -- minor support for borderline cbets."
    return "No backdoor draws: rely on range advantage and fold equity alone for cbets."


@dataclass
class BackdoorDrawFrequencyResult:
    has_bd_fd: bool
    has_bd_sd: bool
    base_hand_sdv: float
    board_texture: str
    bd_equity: float
    adjusted_cbet_freq: float
    bd_tip: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_backdoor_draw_frequency(
    has_bd_fd: bool = True,
    has_bd_sd: bool = False,
    base_hand_sdv: float = 0.40,
    board_texture: str = 'dry',
) -> BackdoorDrawFrequencyResult:
    bd_equity = _bd_equity(has_bd_fd, has_bd_sd)
    base_cbet = BOARD_TEXTURE_CBET_BASE.get(board_texture, 0.50)
    adjusted_cbet_freq = _cbet_freq_with_bd(base_cbet, has_bd_fd, has_bd_sd)
    tip = _bd_tip(has_bd_fd, has_bd_sd)

    tips = []
    tips.append(
        "Backdoor draws are secondary equity boosters -- never the primary reason to bet."
    )
    tips.append(
        "BD FD completes ~4.2% and BD SD ~4.0% -- small but real equity additions to justify marginal cbets."
    )
    tips.append(tip)
    if has_bd_fd and has_bd_sd:
        tips.append("With both backdoor draws, your cbet EV is boosted by ~3-6%; lean toward betting more often.")
    if board_texture in ('wet', 'monotone'):
        tips.append("Wet/monotone board: adjust cbet sizing down even with backdoor draws -- villain's calling range is strong.")
    if not has_bd_fd and not has_bd_sd:
        tips.append("No backdoor draws: be more selective with cbets -- need range advantage or direct fold equity.")

    reasoning = (
        f"BD FD={has_bd_fd} BD SD={has_bd_sd} bd_equity={bd_equity*100:.1f}% "
        f"board={board_texture} base_cbet={base_cbet*100:.0f}% -> adj_cbet={adjusted_cbet_freq*100:.0f}%."
    )
    verdict = 'CBET' if adjusted_cbet_freq >= MIN_CBET_FREQ_WITH_BD else 'CHECK'

    return BackdoorDrawFrequencyResult(
        has_bd_fd=has_bd_fd,
        has_bd_sd=has_bd_sd,
        base_hand_sdv=base_hand_sdv,
        board_texture=board_texture,
        bd_equity=bd_equity,
        adjusted_cbet_freq=adjusted_cbet_freq,
        bd_tip=tip,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def backdoor_draw_frequency_one_liner(r: BackdoorDrawFrequencyResult) -> str:
    bd_fd = 'Y' if r.has_bd_fd else 'N'
    bd_sd = 'Y' if r.has_bd_sd else 'N'
    return (
        f"[BDD bd_fd={bd_fd} bd_sd={bd_sd}] "
        f"bd_eq={r.bd_equity*100:.1f}% adj_cbet={r.adjusted_cbet_freq*100:.0f}%"
    )
