# -*- coding: utf-8 -*-
"""wtsd_wsd_guide.py -- WTSD and WSD interpretation guide."""

from dataclasses import dataclass, field
from typing import List

WTSD_CATEGORY: dict = {
    'low':      (0.0, 0.23),
    'standard': (0.23, 0.30),
    'high':     (0.30, 1.0),
}

WSD_CATEGORY: dict = {
    'losing':  (0.0,  0.48),
    'neutral': (0.48, 0.52),
    'winning': (0.52, 1.0),
}


def _wtsd_category(wtsd: float) -> str:
    if wtsd < 0.23:
        return 'low'
    if wtsd <= 0.30:
        return 'standard'
    return 'high'


def _wsd_category(wsd: float) -> str:
    if wsd < 0.48:
        return 'losing'
    if wsd <= 0.52:
        return 'neutral'
    return 'winning'


def _combined_profile(wtsd: float, wsd: float) -> str:
    wt = _wtsd_category(wtsd)
    wd = _wsd_category(wsd)
    if wt == 'high' and wd == 'losing':
        return 'calling_station'
    if wt == 'low' and wd == 'winning':
        return 'nit'
    if wt == 'standard' and wd in ('neutral', 'winning'):
        return 'standard'
    if wt == 'low' and wd == 'winning':
        return 'bluff_catcher'
    if wt == 'high' and wd == 'winning':
        return 'hero_caller'
    if wt == 'high' and wd == 'neutral':
        return 'loose_passive'
    if wt == 'low' and wd == 'losing':
        return 'over_folder'
    return 'standard'


def _exploit_advice(wtsd_cat: str, wsd_cat: str) -> str:
    if wtsd_cat == 'high' and wsd_cat == 'losing':
        return "Classic calling station -- value-bet thinly; never bluff."
    if wtsd_cat == 'low' and wsd_cat == 'winning':
        return "Nit -- 3-bet bluff liberally; their folding range is very wide."
    if wtsd_cat == 'high' and wsd_cat == 'winning':
        return "Hero caller -- only 3-bet value hands; they call down but have strong holdings."
    if wtsd_cat == 'low' and wsd_cat == 'losing':
        return "Over-folder -- barrel frequently; they fold too much everywhere."
    return "Standard profile -- play solid GTO; minor exploitations based on specific leaks."


@dataclass
class WtsdWsdResult:
    wtsd: float
    wsd: float
    wtsd_category: str
    wsd_category: str
    combined_profile: str
    exploit_advice: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_wtsd_wsd(
    wtsd: float = 0.26,
    wsd: float = 0.50,
) -> WtsdWsdResult:
    wt_cat = _wtsd_category(wtsd)
    wd_cat = _wsd_category(wsd)
    profile = _combined_profile(wtsd, wsd)
    advice = _exploit_advice(wt_cat, wd_cat)

    tips = []
    tips.append(
        "WTSD 25-30% is typical; deviation in either direction signals exploitable tendency."
    )
    if wtsd > 0.35:
        tips.append(
            "Very high WTSD -- villain is stubborn; cut bluffs and load value hands."
        )
    if wsd < 0.45:
        tips.append(
            "Low WSD -- villain shows down weak hands; they call too light or bluff too much."
        )
    if wtsd < 0.20:
        tips.append(
            "Very low WTSD -- villain folds too much; triple-barrel bluffs can be profitable."
        )
    tips.append(
        "Combine WTSD/WSD with street-by-street fold stats for a complete exploitation plan."
    )

    reasoning = (
        f"WTSD={wtsd:.0%} ({wt_cat}) WSD={wsd:.0%} ({wd_cat}) "
        f"profile='{profile}'. {advice}"
    )
    verdict = profile

    return WtsdWsdResult(
        wtsd=wtsd,
        wsd=wsd,
        wtsd_category=wt_cat,
        wsd_category=wd_cat,
        combined_profile=profile,
        exploit_advice=advice,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def wtsd_wsd_one_liner(r: WtsdWsdResult) -> str:
    return (
        f"[WTSD wtsd={r.wtsd:.0%} wsd={r.wsd:.0%}] profile={r.combined_profile}"
    )
