# -*- coding: utf-8 -*-
"""three_bet_stat_guide.py -- 3-bet percentage stat guide."""

from dataclasses import dataclass, field
from typing import List

THREE_BET_PROFILE: dict = {
    'nit':    (0.0,  0.04),
    'tag':    (0.04, 0.09),
    'lag':    (0.09, 0.15),
    'maniac': (0.15, 1.00),
}

THREE_BET_BY_POSITION: dict = {
    'btn': {'nit': 0.04, 'tag': 0.08, 'lag': 0.14, 'maniac': 0.20},
    'bb':  {'nit': 0.05, 'tag': 0.09, 'lag': 0.16, 'maniac': 0.22},
    'sb':  {'nit': 0.03, 'tag': 0.07, 'lag': 0.12, 'maniac': 0.18},
}


def _3bet_profile(pct: float) -> str:
    if pct < 0.04:
        return 'nit'
    if pct < 0.09:
        return 'tag'
    if pct < 0.15:
        return 'lag'
    return 'maniac'


def _position_adjust(position: str, overall_pct: float) -> str:
    pos = position.lower()
    benchmarks = THREE_BET_BY_POSITION.get(pos, {})
    if not benchmarks:
        return f"No position-specific benchmark for '{position}'."
    # Compare overall to position norms
    if overall_pct < benchmarks.get('nit', 0.04):
        return f"Very low {pos.upper()} 3-bet -- exploitable with wide opens; rarely faces re-raise pressure."
    if overall_pct < benchmarks.get('tag', 0.09):
        return f"Standard {pos.upper()} 3-bet frequency; balanced value/bluff mix."
    if overall_pct < benchmarks.get('lag', 0.15):
        return f"High {pos.upper()} 3-bet -- consider 4-bet light; their 3-bet range is wide."
    return f"Very high {pos.upper()} 3-bet from {pos.upper()} -- 4-bet bluff regularly; they over-3-bet."


def _counter_strategy(profile: str) -> str:
    strats = {
        'nit':    "Open freely vs nit 3-bet; 4-bet only monsters; fold marginal hands.",
        'tag':    "Standard play: mix 4-bet value+bluff; defend with strong hands in position.",
        'lag':    "Widen 4-bet bluff range; flat wide IP with medium pairs and strong aces.",
        'maniac': "4-bet light with any two cards IP; trap with monsters; never cold-call.",
    }
    return strats.get(profile, "Observe more hands before adjusting.")


@dataclass
class ThreeBetStatResult:
    three_bet_pct: float
    position: str
    profile: str
    position_context: str
    counter: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_three_bet_stat(
    three_bet_pct: float = 0.07,
    position: str = 'btn',
) -> ThreeBetStatResult:
    profile = _3bet_profile(three_bet_pct)
    pos_ctx = _position_adjust(position, three_bet_pct)
    counter = _counter_strategy(profile)

    tips = []
    tips.append(
        "Overall 3-bet% less useful than position-specific 3-bet%; always filter by position."
    )
    if three_bet_pct > 0.12:
        tips.append(
            "High 3-bet frequency -- 4-bet bluff with suited blockers; re-raise forces fold."
        )
    if three_bet_pct < 0.04:
        tips.append(
            "Low 3-bet -- villain's 3-bet range is very strong; respect it and fold marginal hands."
        )
    if position.lower() == 'bb':
        tips.append(
            "BB 3-bets are commonly wider (positional defense); discount slightly vs IP raises."
        )
    tips.append(
        "Cold 4-bet range should always be polarized: bluffs + value to avoid being exploited."
    )

    reasoning = (
        f"3-bet={three_bet_pct:.0%} ({profile}) from {position.upper()}. "
        f"{pos_ctx} Counter: {counter}"
    )
    verdict = profile

    return ThreeBetStatResult(
        three_bet_pct=three_bet_pct,
        position=position,
        profile=profile,
        position_context=pos_ctx,
        counter=counter,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def three_bet_stat_one_liner(r: ThreeBetStatResult) -> str:
    return (
        f"[3BET pct={r.three_bet_pct:.0%}] "
        f"profile={r.profile} counter={r.counter[:30]}"
    )
