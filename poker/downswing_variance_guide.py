"""
Downswing Variance Guide (downswing_variance_guide.py)

Poker variance is high; even winning players experience large downswings.
This module quantifies expected downswings by win rate, helps players
understand if they're running bad vs playing bad, and sizes the bankroll
needed to survive variance with a given probability.

THEORY:
  POKER VARIANCE BASICS:
  Variance is measured as standard deviation (SD) in BB/100 hands.
  Typical 6-max cash: SD = 80-90 BB/100; full ring: 65-75 BB/100.
  A player winning at 5 BB/100 with SD=85 is still in a normal 2-sigma
  downswing if they've lost 100BB over 200 hands (expected short-term).

  EXPECTED DOWNSWING FORMULA:
  The expected maximum downswing D over N hands approximates:
  D ≈ SD * sqrt(N/100) - WR * N/100
  where WR = win rate in BB/100, SD = std deviation in BB/100, N = hands.

  SAMPLE SIZE FOR STATISTICAL SIGNIFICANCE:
  To show positive win rate at 95% confidence:
  N_min = (1.96 * SD / WR)^2 * 100
  At WR=5 BB/100, SD=85: need ~111,000 hands to confirm positive WR.

  BANKROLL REQUIREMENTS:
  To withstand downswings with 95% probability:
  Required BR (buy-ins) = (D_max + 2*SD*sqrt(0.05)) / buy_in_BB
  Rule of thumb: 20-30 buy-ins for cash, 50-100 for tournaments.

  RUNNING BAD VS PLAYING BAD:
  If loss rate > 2 * expected_downswing_rate -> likely playing badly too.
  At N < 10,000 hands: nearly impossible to distinguish from pure variance.

DISTINCT FROM:
  bankroll_advisor.py:   General bankroll advice
  bankroll_manager.py:   Bankroll management rules
  session_opening_strategy.py: Session-level health
  THIS MODULE:           VARIANCE EDUCATION specifically; expected downswing
                         magnitudes; sample size math; run-good/bad assessment.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional


GAME_STD_DEV: dict = {
    '6max_cash':        85.0,
    'fullring_cash':    70.0,
    'zoom_6max':        90.0,
    'hu_cash':          120.0,
    'plo_6max':         150.0,
    'mtt':              200.0,
}

WIN_RATE_BENCHMARKS: dict = {
    'micro_stakes':  8.0,
    'small_stakes':  5.0,
    'mid_stakes':    3.0,
    'high_stakes':   2.0,
    'break_even':    0.0,
}

BANKROLL_RECS_BUYIN: dict = {
    '6max_cash':     20,
    'fullring_cash': 20,
    'zoom_6max':     25,
    'hu_cash':       30,
    'plo_6max':      40,
    'mtt':           100,
}

CONFIDENCE_Z: dict = {
    0.90: 1.645,
    0.95: 1.960,
    0.99: 2.576,
}


def _expected_downswing(win_rate_bb100: float, std_dev_bb100: float, n_hands: int) -> float:
    if win_rate_bb100 <= 0:
        n_units = n_hands / 100.0
        return round(std_dev_bb100 * math.sqrt(n_units), 1)
    # Expected max drawdown for Brownian motion with drift:
    # E[max DD] = (SD^2 / (2*WR)) * (1 - exp(-2*WR*N / SD^2))
    asymptotic = (std_dev_bb100 ** 2) / (2.0 * win_rate_bb100)
    exponent = -2.0 * win_rate_bb100 * n_hands / (100.0 * std_dev_bb100 ** 2)
    scale = 1.0 - math.exp(exponent)
    return round(asymptotic * scale, 1)


def _sample_size_needed(win_rate_bb100: float, std_dev_bb100: float, confidence: float = 0.95) -> int:
    if win_rate_bb100 <= 0:
        return 999999
    z = CONFIDENCE_Z.get(confidence, 1.96)
    n_units = (z * std_dev_bb100 / win_rate_bb100) ** 2
    return int(math.ceil(n_units * 100))


def _bankroll_required_bb(win_rate_bb100: float, std_dev_bb100: float, ruin_prob: float = 0.05) -> float:
    if win_rate_bb100 <= 0:
        return 9999.0
    b = math.exp(-2 * win_rate_bb100 * (1.0 / std_dev_bb100) ** 2 * 100)
    if ruin_prob <= 0 or b <= 0:
        return 9999.0
    br = math.log(ruin_prob) / math.log(b) * 100
    return round(max(0, br), 1)


def _assess_run(
    observed_bb_loss: float,
    n_hands: int,
    win_rate_bb100: float,
    std_dev_bb100: float,
) -> str:
    if n_hands < 5000:
        return 'SAMPLE_TOO_SMALL_INCONCLUSIVE'
    n_units = n_hands / 100.0
    expected_profit = win_rate_bb100 * n_units
    # deviation = actual - expected; negative means underperforming
    deviation = -observed_bb_loss - expected_profit
    sigma = std_dev_bb100 * math.sqrt(n_units)
    if sigma == 0:
        return 'INCONCLUSIVE'
    z = deviation / sigma
    if z <= -2.5:
        return 'LIKELY_PLAYING_BADLY_TOO'
    if z <= -1.5:
        return 'RUNNING_BAD_SIGNIFICANTLY'
    if z <= -0.5:
        return 'RUNNING_SLIGHTLY_BAD'
    if z <= 0.5:
        return 'RUNNING_NORMAL'
    return 'RUNNING_GOOD'


@dataclass
class DownswingVarianceResult:
    game_type: str
    win_rate_bb100: float
    n_hands: int
    observed_bb_loss: float

    std_dev: float
    expected_downswing_50k: float
    expected_downswing_100k: float
    sample_size_needed: int
    bankroll_req_bb: float
    run_assessment: str
    bankroll_rec_buyins: int

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_downswing_variance(
    game_type: str = '6max_cash',
    win_rate_bb100: float = 5.0,
    n_hands: int = 10000,
    observed_bb_loss: float = 0.0,
    buy_in_bb: float = 100.0,
) -> DownswingVarianceResult:
    """
    Quantify expected downswings and assess current run.

    Args:
        game_type:       Game type key ('6max_cash','fullring_cash','zoom_6max',...)
        win_rate_bb100:  Expected win rate in BB/100
        n_hands:         Total hands played in sample
        observed_bb_loss: BB lost in sample (positive = losing)
        buy_in_bb:       Standard buy-in in BB (usually 100)

    Returns:
        DownswingVarianceResult
    """
    sd = GAME_STD_DEV.get(game_type, 85.0)
    ds50k = _expected_downswing(win_rate_bb100, sd, 50000)
    ds100k = _expected_downswing(win_rate_bb100, sd, 100000)
    sample_n = _sample_size_needed(win_rate_bb100, sd)
    br_bb = _bankroll_required_bb(win_rate_bb100, sd)
    br_buyins = BANKROLL_RECS_BUYIN.get(game_type, 25)
    run = _assess_run(observed_bb_loss, n_hands, win_rate_bb100, sd)

    verdict = (
        f'[VAR {game_type}|WR={win_rate_bb100:.1f}BB/100] '
        f'ds50k={ds50k:.0f}BB ds100k={ds100k:.0f}BB '
        f'need={sample_n}hands run={run}'
    )

    reasoning = (
        f'Variance analysis: {game_type}, WR={win_rate_bb100:.1f}BB/100, SD={sd:.0f}BB/100. '
        f'Expected downswing over 50k hands={ds50k:.0f}BB; 100k={ds100k:.0f}BB. '
        f'Sample to confirm WR at 95% confidence={sample_n:,} hands (have {n_hands:,}). '
        f'Bankroll required={br_bb:.0f}BB ({br_bb/buy_in_bb:.0f} buy-ins). '
        f'Current run assessment: {run}.'
    )

    tips = []

    tips.append(
        f'EXPECTED DOWNSWING: WR={win_rate_bb100:.1f}BB/100, SD={sd:.0f}BB/100. '
        f'Over 50k hands: expect up to {ds50k:.0f}BB ({ds50k/buy_in_bb:.1f} buy-ins) downswing. '
        f'Over 100k hands: {ds100k:.0f}BB ({ds100k/buy_in_bb:.1f} buy-ins). '
        f'This is NORMAL variance -- not evidence of playing badly.'
    )

    tips.append(
        f'SAMPLE SIZE: Need {sample_n:,} hands to confirm WR at 95% confidence. '
        f'You have {n_hands:,} hands ({100*n_hands/sample_n:.0f}% of needed sample). '
        f'{"Sufficient sample -- results statistically meaningful." if n_hands >= sample_n else "Insufficient sample -- results dominated by variance; do not adjust strategy based on results alone."}'
    )

    tips.append(
        f'RUN ASSESSMENT ({n_hands:,} hands): {run}. '
        f'{"Too few hands to distinguish variance from skill." if "TOO_SMALL" in run else "Your losses are within normal variance bounds -- stay the course." if run in ("RUNNING_SLIGHTLY_BAD","RUNNING_NORMAL","RUNNING_GOOD") else "Significantly running bad -- review game spots but understand variance is primary cause." if "SIGNIFICANTLY" in run else "Results suggest possible leaks beyond variance -- detailed review recommended."}'
    )

    tips.append(
        f'BANKROLL: Recommend {br_buyins} buy-ins ({br_buyins * buy_in_bb:.0f}BB) for {game_type}. '
        f'Minimum to survive variance with 95% probability = {br_bb:.0f}BB ({br_bb/buy_in_bb:.0f} buy-ins).'
    )

    return DownswingVarianceResult(
        game_type=game_type,
        win_rate_bb100=win_rate_bb100,
        n_hands=n_hands,
        observed_bb_loss=observed_bb_loss,
        std_dev=sd,
        expected_downswing_50k=ds50k,
        expected_downswing_100k=ds100k,
        sample_size_needed=sample_n,
        bankroll_req_bb=br_bb,
        run_assessment=run,
        bankroll_rec_buyins=br_buyins,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def var_one_liner(r: DownswingVarianceResult) -> str:
    return (
        f'[VAR {r.game_type}|WR={r.win_rate_bb100:.1f}BB/100] '
        f'ds50k={r.expected_downswing_50k:.0f}BB run={r.run_assessment}'
    )
