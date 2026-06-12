"""
Bankroll Management Advisor (bankroll_advisor.py)

The #1 reason winning players go broke is playing stakes too high for their roll.
This module implements professional BRM: risk of ruin, buy-in thresholds,
move-up/move-down triggers, and stake recommendations.

Key concepts:
  Risk of Ruin (RoR) = exp(-2 * win_rate_bb100 * bankroll_bb / std_dev_bb100^2)
  For a 5% RoR ceiling: need bankroll so that exp(-2*W*B/σ²) ≤ 0.05

Standard buy-in minimums (6-max cash, conservative BRM):
  20 BI  = minimum (short-stacked bankroll management)
  25 BI  = standard (recommended for most players)
  30 BI  = conservative (recommended for beginners)
  50 BI  = ultra-conservative (high variance games, rebuilding)

Move-up trigger: 30 BI at next stake
Move-down trigger: below 15 BI at current stake

Typical 6-max standard deviation: ~80-100 BB/100 (varies with win rate)

Usage:
    from poker.bankroll_advisor import analyze_bankroll, BankrollAnalysis
    result = analyze_bankroll(
        bankroll_usd=500.0,
        stake_nl=25,
        win_rate_bb100=5.0,
        std_dev_bb100=90.0,
    )
    print(result.grade, result.recommended_stake)
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional


# Standard stake ladder (NL buy-in amounts in USD)
_STAKE_LADDER = [2, 5, 10, 25, 50, 100, 200, 500, 1000, 2000]

# Minimum buy-in for a 100BB buy-in at each stake (USD)
_BB_VALUE_USD = {
    2: 0.02, 5: 0.05, 10: 0.10, 25: 0.25,
    50: 0.50, 100: 1.00, 200: 2.00, 500: 5.00, 1000: 10.00, 2000: 20.00,
}

# Recommended minimum buy-ins by player type
_MIN_BUYINS = {
    'aggressive': 20,
    'standard':   25,
    'conservative': 30,
    'ultra': 50,
}

# Typical standard deviation at each stake (BB/100) — higher stakes = more complex
_STD_DEV_ESTIMATES = {
    2: 80, 5: 85, 10: 88, 25: 90,
    50: 92, 100: 95, 200: 98, 500: 100,
}


def _risk_of_ruin(win_rate_bb100: float, bankroll_bb: float, std_dev_bb100: float) -> float:
    """
    Kelly-based Risk of Ruin.
    RoR = exp(-2 * W * B / σ²)
    where W = win_rate in BB/100, B = bankroll in BB, σ = std dev in BB/100.
    Returns 1.0 (certain ruin) if win_rate <= 0.
    """
    if win_rate_bb100 <= 0:
        return 1.0
    exponent = -2.0 * win_rate_bb100 * bankroll_bb / (std_dev_bb100 ** 2)
    return min(1.0, max(0.0, math.exp(exponent)))


def _bankroll_for_ror(win_rate_bb100: float, std_dev_bb100: float, target_ror: float) -> float:
    """
    Bankroll (in BB) needed to achieve a target risk-of-ruin.
    B = -ln(RoR) * σ² / (2 * W)
    """
    if win_rate_bb100 <= 0 or target_ror <= 0:
        return float('inf')
    return -math.log(target_ror) * (std_dev_bb100 ** 2) / (2.0 * win_rate_bb100)


def _stake_buyins(bankroll_usd: float, stake_nl: int) -> float:
    """How many 100BB buy-ins can hero afford at this stake."""
    bb_usd = _BB_VALUE_USD.get(stake_nl, stake_nl / 100)
    buyin_usd = 100 * bb_usd
    return bankroll_usd / buyin_usd if buyin_usd > 0 else 0


def _recommended_stake(bankroll_usd: float, min_buyins: int = 25) -> int:
    """Find the highest stake where hero has min_buyins buy-ins."""
    for stake in reversed(_STAKE_LADDER):
        if _stake_buyins(bankroll_usd, stake) >= min_buyins:
            return stake
    return _STAKE_LADDER[0]


@dataclass
class BankrollAnalysis:
    """Full bankroll management analysis."""
    # Inputs
    bankroll_usd: float
    stake_nl: int
    win_rate_bb100: float
    std_dev_bb100: float

    # Current position
    bankroll_bb: float          # bankroll in big blinds at current stake
    current_buyins: float       # 100BB buy-ins at current stake
    risk_of_ruin: float         # probability of going broke (0-1)

    # Targets
    min_buyins_standard: int    # minimum BIs recommended (25)
    min_buyins_conservative: int  # conservative BIs (30)

    # Thresholds
    move_up_usd: float          # bankroll to safely move up one stake
    move_down_usd: float        # bankroll trigger to move down
    stake_at_5pct_ror: int      # highest stake where RoR ≤ 5%

    # Recommendations
    recommended_stake: int      # optimal stake (25 BI standard)
    grade: str                  # 'too_high', 'optimal', 'conservative', 'too_low'
    action: str                 # 'move_up', 'stay', 'move_down', 'move_down_immediately'

    # Monthly projections (rough)
    expected_bb_per_100: float
    hours_to_double: Optional[float]  # hours to double bankroll (None if losing)

    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_bankroll(
    bankroll_usd: float,
    stake_nl: int,
    win_rate_bb100: float = 5.0,
    std_dev_bb100: float = 90.0,
    game_type: str = 'cash_6max',
    style: str = 'standard',
) -> BankrollAnalysis:
    """
    Analyze bankroll management for a cash game player.

    Args:
        bankroll_usd:      Total poker bankroll in USD
        stake_nl:          Current stake level (e.g. 25 = NL25)
        win_rate_bb100:    Estimated win rate in BB/100 hands
        std_dev_bb100:     Standard deviation in BB/100 (default 90 for 6-max)
        game_type:         'cash_6max', 'cash_fr', 'mtt', 'sng'
        style:             'aggressive'(20BI), 'standard'(25BI), 'conservative'(30BI)

    Returns:
        BankrollAnalysis
    """
    bb_usd = _BB_VALUE_USD.get(stake_nl, stake_nl / 100.0)
    buyin_usd = 100 * bb_usd
    bankroll_bb = bankroll_usd / bb_usd

    current_buyins = bankroll_usd / buyin_usd

    # Use game-specific std dev if not overridden
    if std_dev_bb100 == 90.0:
        std_dev_bb100 = _STD_DEV_ESTIMATES.get(stake_nl, 90.0)

    # Risk of ruin at current stake/bankroll
    ror = _risk_of_ruin(win_rate_bb100, bankroll_bb, std_dev_bb100)

    # Buy-in minimums by style
    min_bi_standard = _MIN_BUYINS.get(style, 25)
    min_bi_conservative = _MIN_BUYINS['conservative']

    # Find highest safe stake (≤5% RoR)
    safe_stake = _STAKE_LADDER[0]
    for s in _STAKE_LADDER:
        bb_at_s = bankroll_usd / _BB_VALUE_USD.get(s, s / 100.0)
        std_s = _STD_DEV_ESTIMATES.get(s, 90.0)
        if _risk_of_ruin(win_rate_bb100, bb_at_s, std_s) <= 0.05:
            safe_stake = s

    recommended = _recommended_stake(bankroll_usd, min_bi_standard)

    # Move-up threshold: 30 BI at next stake
    stake_idx = _STAKE_LADDER.index(stake_nl) if stake_nl in _STAKE_LADDER else 0
    next_stake = _STAKE_LADDER[min(stake_idx + 1, len(_STAKE_LADDER) - 1)]
    next_bb_usd = _BB_VALUE_USD.get(next_stake, next_stake / 100.0)
    move_up_usd = 30 * 100 * next_bb_usd

    # Move-down trigger: below 15 BI at current stake
    move_down_usd = 15 * buyin_usd

    # Grade
    if current_buyins >= 35:
        grade = 'conservative'
    elif current_buyins >= min_bi_standard:
        grade = 'optimal'
    elif current_buyins >= 15:
        grade = 'too_high'
    else:
        grade = 'danger'

    # Action
    if current_buyins < 15:
        action = 'move_down_immediately'
    elif current_buyins < min_bi_standard:
        action = 'move_down'
    elif bankroll_usd >= move_up_usd and next_stake != stake_nl:
        action = 'move_up'
    else:
        action = 'stay'

    # Hours to double bankroll (rough estimate at 25 hands/hour, 6-max)
    if win_rate_bb100 > 0:
        bb_per_hour = win_rate_bb100 * 25 / 100  # 25 hands/hour
        hours_to_double = bankroll_bb / bb_per_hour
    else:
        hours_to_double = None

    # Tips
    tips = []
    if ror > 0.20:
        tips.append(
            f'Risk of ruin = {ror:.0%} — dangerously high. '
            f'Move down immediately to protect your bankroll.'
        )
    if current_buyins < 20:
        tips.append(
            f'Only {current_buyins:.1f} buy-ins at NL{stake_nl}. '
            f'Minimum is 20 BI. Move down to NL{recommended} (${recommended} max buy-in).'
        )
    if action == 'move_up' and recommended >= next_stake:
        tips.append(
            f'Bankroll ${bankroll_usd:.0f} supports NL{next_stake} (30 BI = ${move_up_usd:.0f}). '
            f'Consider moving up. Take a short shot (5 BI max) first.'
        )
    if win_rate_bb100 < 0:
        tips.append(
            'Win rate is negative — review leaks before moving up. '
            'A losing player at any stake needs coaching, not a different stake.'
        )
    if ror <= 0.05 and grade in ('optimal', 'conservative'):
        tips.append(
            f'Risk of ruin = {ror:.1%} — well within safe range. '
            f'Current stake NL{stake_nl} is appropriate.'
        )
    if std_dev_bb100 > 100:
        tips.append(
            'High standard deviation (>100 BB/100) suggests a high-variance play style. '
            'Consider adding more buy-ins (35+) or reducing bluffing frequency.'
        )
    if not tips:
        tips.append(
            f'BRM status: {current_buyins:.1f} BI at NL{stake_nl}. '
            f'RoR={ror:.1%}. Maintain {min_bi_standard} BI minimum.'
        )

    reasoning = (
        f'Bankroll ${bankroll_usd:.0f} at NL{stake_nl} = {current_buyins:.1f} buy-ins '
        f'({bankroll_bb:.0f}BB). '
        f'Win rate={win_rate_bb100:+.1f}BB/100 σ={std_dev_bb100:.0f}BB/100. '
        f'Risk of ruin={ror:.1%}. '
        f'Move-up at ${move_up_usd:.0f} (30 BI NL{next_stake}). '
        f'Move-down at ${move_down_usd:.0f} (15 BI NL{stake_nl}). '
        f'Grade: {grade.upper()}. Action: {action.upper()}.'
    )

    return BankrollAnalysis(
        bankroll_usd=bankroll_usd,
        stake_nl=stake_nl,
        win_rate_bb100=win_rate_bb100,
        std_dev_bb100=std_dev_bb100,
        bankroll_bb=round(bankroll_bb, 0),
        current_buyins=round(current_buyins, 2),
        risk_of_ruin=round(ror, 4),
        min_buyins_standard=min_bi_standard,
        min_buyins_conservative=min_bi_conservative,
        move_up_usd=round(move_up_usd, 2),
        move_down_usd=round(move_down_usd, 2),
        stake_at_5pct_ror=safe_stake,
        recommended_stake=recommended,
        grade=grade,
        action=action,
        expected_bb_per_100=win_rate_bb100,
        hours_to_double=round(hours_to_double, 1) if hours_to_double else None,
        reasoning=reasoning,
        tips=tips,
    )


def bankroll_one_liner(result: BankrollAnalysis) -> str:
    """Single-line overlay summary."""
    return (
        f'BRM NL{result.stake_nl}: {result.current_buyins:.1f}BI '
        f'RoR={result.risk_of_ruin:.0%} [{result.grade}] '
        f'-> {result.action.upper()}'
    )


def ror_table(win_rate_bb100: float, std_dev_bb100: float = 90.0) -> List[dict]:
    """
    Generate a risk-of-ruin table for different stake/bankroll combinations.
    Returns list of dicts with stake, buyins, bankroll_usd, ror.
    """
    rows = []
    for stake in _STAKE_LADDER:
        for buyins in (15, 20, 25, 30, 40, 50):
            bankroll_usd = buyins * 100 * _BB_VALUE_USD.get(stake, stake / 100.0)
            bankroll_bb = bankroll_usd / _BB_VALUE_USD.get(stake, stake / 100.0)
            ror = _risk_of_ruin(win_rate_bb100, bankroll_bb, std_dev_bb100)
            rows.append({
                'stake': stake,
                'buyins': buyins,
                'bankroll_usd': round(bankroll_usd, 2),
                'ror': round(ror, 4),
            })
    return rows
