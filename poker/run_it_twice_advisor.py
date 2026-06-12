"""
Run It Twice Advisor (run_it_twice_advisor.py)

In live poker, all-in situations can sometimes be "run twice"
(deal two boards and split the pot accordingly). This module
advises on whether to accept or decline a run-it-twice offer.

KEY MATH:
  Expected Value (EV) is identical whether you run it once or twice.
  The difference is VARIANCE:
    Var(run_once)  = equity * (1-equity) * pot^2
    Var(run_twice) = (1/2) * Var(run_once)
    Std_once = pot * sqrt(equity*(1-equity))
    Std_twice = Std_once / sqrt(2)

  Running twice cuts variance by ~29% (1 - 1/sqrt(2) = 29.3%).

WHEN TO RUN TWICE:
  - Short bankroll: always RIT (variance reduction protects bankroll)
  - On tilt or large upswing/downswing: RIT to stabilize
  - Holding small edge (~52-60%): RIT preserves edge more consistently
  - NEVER if: you have huge equity advantage (80%+) and deep bankroll

WHEN TO DECLINE:
  - Very deep bankroll: variance barely matters, decline if you prefer
  - Huge equity favorite (85%+): let the fish run it once and win rarely
  - Opponent is tilted and wants to RIT to stabilize: decline strategically

SOCIAL/STRATEGIC NOTES:
  RIT is often offered by the player who is behind (wants to reduce variance).
  The player AHEAD has no financial incentive to RIT but may do so for goodwill.
  Opponents tracking your RIT patterns can exploit: know when they're offering for reads.

Usage:
    from poker.run_it_twice_advisor import advise_run_it_twice, RunItTwiceAdvice, rit_one_liner

    advice = advise_run_it_twice(
        pot_bb=200.0,
        hero_equity=0.65,
        bankroll_bb=2000.0,
        tilt_score=0.3,
        is_tournament=False,
        is_hero_offering=False,
    )
    print(rit_one_liner(advice))
"""

import math
from dataclasses import dataclass, field
from typing import List


def _variance_run_once(pot: float, equity: float) -> float:
    return round(equity * (1 - equity) * pot ** 2, 2)


def _std_run_once(pot: float, equity: float) -> float:
    return round(pot * math.sqrt(equity * (1 - equity)), 2)


def _std_run_twice(pot: float, equity: float) -> float:
    return round(_std_run_once(pot, equity) / math.sqrt(2), 2)


def _variance_reduction_pct() -> float:
    """Running twice reduces std dev by (1 - 1/sqrt(2)) ~ 29.3%."""
    return round(1 - 1 / math.sqrt(2), 4)


@dataclass
class RunItTwiceAdvice:
    # Inputs
    pot_bb: float
    hero_equity: float
    bankroll_bb: float
    tilt_score: float
    is_tournament: bool
    is_hero_offering: bool

    # Math
    ev_either_way: float            # same either way
    std_run_once: float             # std dev in BB, run once
    std_run_twice: float            # std dev in BB, run twice
    variance_reduction_pct: float   # how much variance is reduced (~29.3%)

    # Risk metrics
    bankroll_risk_pct_once: float   # pot/bankroll * std_once (bankroll at risk pct)
    bankroll_risk_pct_twice: float

    # Decision
    recommendation: str     # 'accept_rit', 'decline_rit', 'indifferent'
    confidence: str         # 'strong', 'moderate', 'marginal'
    reasoning_code: str     # 'short_bankroll', 'huge_favorite', 'tilt', 'standard', etc.

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_run_it_twice(
    pot_bb: float = 100.0,
    hero_equity: float = 0.65,
    bankroll_bb: float = 1500.0,
    tilt_score: float = 0.2,
    is_tournament: bool = False,
    is_hero_offering: bool = False,
) -> RunItTwiceAdvice:
    """
    Advise whether to accept or decline a run-it-twice offer.

    Args:
        pot_bb:          Total pot at stake in BB
        hero_equity:     Hero's equity fraction (0-1) going to showdown
        bankroll_bb:     Hero's total bankroll in BB
        tilt_score:      Hero's tilt level (0=none, 1=severe)
        is_tournament:   True if in a tournament (ICM makes RIT math different)
        is_hero_offering: True if hero is the one offering RIT (vs accepting)

    Returns:
        RunItTwiceAdvice
    """
    ev = round(hero_equity * pot_bb, 2)
    std_once = _std_run_once(pot_bb, hero_equity)
    std_twice = _std_run_twice(pot_bb, hero_equity)
    var_red = _variance_reduction_pct()

    br_risk_once = round(std_once / max(bankroll_bb, 1.0), 4)
    br_risk_twice = round(std_twice / max(bankroll_bb, 1.0), 4)

    buyins = bankroll_bb / 100.0  # approximate BI at 100BB

    # --- Decision logic ---
    reasons = []
    score = 0  # positive = accept RIT, negative = decline

    # Short bankroll strongly favors RIT
    if br_risk_once > 0.15:
        score += 3
        reasons.append('short_bankroll')
    elif br_risk_once > 0.08:
        score += 1
        reasons.append('moderate_bankroll_risk')

    # Huge favorite: declining RIT may be fine (or even smart vs tilted fish)
    if hero_equity >= 0.80:
        score -= 2
        reasons.append('huge_favorite')
    elif hero_equity >= 0.65:
        score -= 0  # slight edge doesn't change much
    else:
        score += 1
        reasons.append('underdog_or_even')

    # Tilt: if tilting, reduce variance
    if tilt_score > 0.5:
        score += 2
        reasons.append('tilt')
    elif tilt_score > 0.3:
        score += 1
        reasons.append('slight_tilt')

    # Tournament: RIT affects ICM differently (usually still good if short-stacked)
    if is_tournament:
        if is_hero_offering:
            score += 1
            reasons.append('tournament_short_stack')
        reasons.append('tournament')

    # Hero offering vs accepting
    if is_hero_offering and hero_equity >= 0.65:
        # Hero is ahead and offering -- this is generous
        score -= 1
        reasons.append('offering_when_ahead')

    # Decision
    if score >= 2:
        rec = 'accept_rit'
        conf = 'strong' if score >= 3 else 'moderate'
    elif score == 1:
        rec = 'accept_rit'
        conf = 'marginal'
    elif score == 0:
        rec = 'indifferent'
        conf = 'marginal'
    elif score == -1:
        rec = 'decline_rit'
        conf = 'marginal'
    else:
        rec = 'decline_rit'
        conf = 'strong' if score <= -3 else 'moderate'

    reason_code = reasons[0] if reasons else 'standard'

    variance_saved_bb = round((std_once - std_twice), 2)

    verdict = (
        f'EV={ev:+.1f}BB either way. '
        f'Std dev: once={std_once:.1f}BB twice={std_twice:.1f}BB (-{var_red:.0%} std). '
        f'BR risk: once={br_risk_once:.1%} twice={br_risk_twice:.1%}. '
        f'Recommendation: {rec.upper()} ({conf}).'
    )

    reasoning = (
        f'Pot={pot_bb:.0f}BB equity={hero_equity:.0%}. '
        f'EV identical={ev:.1f}BB. '
        f'Variance reduction: std {std_once:.1f} -> {std_twice:.1f}BB (saves {variance_saved_bb:.1f}BB std). '
        f'BR risk once={br_risk_once:.1%}. Tilt={tilt_score:.2f}. '
        f'Reasons: {", ".join(reasons)}. Score={score} -> {rec}.'
    )

    tips = []

    tips.append(
        f'EV NOTE: Running twice does NOT change your EV ({ev:+.1f}BB either way). '
        f'It ONLY reduces variance. Running once and twice have identical expected value.'
    )

    if rec == 'accept_rit':
        tips.append(
            f'ACCEPT RIT: Variance reduced by ~{var_red:.0%}. '
            f'Bankroll risk drops from {br_risk_once:.1%} to {br_risk_twice:.1%} of bankroll. '
            f'Running twice saves ~{variance_saved_bb:.1f}BB standard deviation per trial.'
        )
    elif rec == 'decline_rit':
        tips.append(
            f'DECLINE RIT: Deep bankroll ({bankroll_bb:.0f}BB) and strong equity ({hero_equity:.0%}). '
            f'Variance reduction has minimal practical benefit. '
            f'Note: if opponent is tilted, declining may add psychological pressure.'
        )
    else:
        tips.append(
            f'INDIFFERENT: EV is identical. Choose based on comfort and table dynamics. '
            f'When truly indifferent, accepting RIT is good for table atmosphere.'
        )

    if is_tournament:
        tips.append(
            f'TOURNAMENT NOTE: ICM complicates RIT math. '
            f'In critical bubble/final-table spots, variance reduction can be MORE valuable than chips suggest. '
            f'When short-stacked: accept RIT almost always. When chip leader: can decline.'
        )

    if hero_equity >= 0.80 and not is_tournament:
        tips.append(
            f'HUGE FAVORITE ({hero_equity:.0%}): Declining RIT is reasonable here. '
            f'You win often enough that variance matters less. '
            f'Also: opponent may be trying to reduce your equity advantage by running twice.'
        )

    return RunItTwiceAdvice(
        pot_bb=round(pot_bb, 1),
        hero_equity=round(hero_equity, 4),
        bankroll_bb=round(bankroll_bb, 1),
        tilt_score=round(tilt_score, 3),
        is_tournament=is_tournament,
        is_hero_offering=is_hero_offering,
        ev_either_way=ev,
        std_run_once=std_once,
        std_run_twice=std_twice,
        variance_reduction_pct=round(var_red, 4),
        bankroll_risk_pct_once=br_risk_once,
        bankroll_risk_pct_twice=br_risk_twice,
        recommendation=rec,
        confidence=conf,
        reasoning_code=reason_code,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rit_one_liner(r: RunItTwiceAdvice) -> str:
    return (
        f'[RIT pot={r.pot_bb:.0f}BB|eq={r.hero_equity:.0%}] '
        f'{r.recommendation.upper()} ({r.confidence}) | '
        f'ev={r.ev_either_way:+.1f}BB std_once={r.std_run_once:.1f}->twice={r.std_run_twice:.1f}BB | '
        f'br_risk_once={r.bankroll_risk_pct_once:.1%}'
    )
