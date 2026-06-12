"""
Variance Reducer (variance_reducer.py)

For bankroll-limited players, reducing variance is sometimes worth sacrificing
a small amount of EV. High variance can cause forced bad decisions (tilt, moving
down, quitting when running bad), all of which cost more than the EV sacrificed.

KEY CONCEPT:
  EV_adjusted = EV_standard - risk_premium
  risk_premium = f(variance, bankroll_bb, risk_aversion)

  A 1BB/100 EV edge is worth more in a low-variance line if:
  - Your bankroll is short (<40 BI)
  - The high-variance line risks a significant portion of your bankroll
  - You are currently on a downswing (tilt risk is elevated)

LINE COMPARISONS:
  High-variance line: jam/raise-all-in with strong equity
  Low-variance line: call/check-raise smaller

  Example:
    A) JAM: EV = +5BB, variance = ±80BB
    B) CALL: EV = +3BB, variance = ±15BB
    At 20 BI bankroll: Risk-adjusted EV(A) = 5 - risk_premium
    At 100 BI bankroll: Risk-adjusted EV(A) ≈ 5 (variance doesn't matter much)

WHEN TO REDUCE VARIANCE:
  - Short stack (<20 BI)
  - Downswing (lost 5+ BI recently)
  - High tilt risk
  - The higher-variance line is only marginally better EV (< 2BB edge)

WHEN TO TAKE HIGHER VARIANCE:
  - Deep bankroll (>60 BI)
  - Comfortable session, no tilt
  - Higher variance line has substantially better EV (>3BB edge)
  - Tournament or satellite where variance reduction may be wrong (ICM)

Usage:
    from poker.variance_reducer import advise_variance, VarianceAdvice, variance_one_liner

    advice = advise_variance(
        ev_high_var=5.0,
        std_dev_high_var=80.0,
        ev_low_var=3.0,
        std_dev_low_var=15.0,
        bankroll_bb=1500.0,
        current_stake_bb=100.0,
        tilt_score=0.3,
        recent_loss_bi=2.0,
        is_tournament=False,
    )
    print(variance_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List


def _risk_premium(
    variance: float,
    bankroll_bb: float,
    tilt_score: float,
    recent_loss_bi: float,
    buyins_at_stake: float,
) -> float:
    """
    Calculate risk premium (cost of variance) in BB.

    Higher when:
    - Variance is high relative to bankroll
    - Player is tilting
    - Player is on a downswing
    """
    if bankroll_bb <= 0:
        return variance

    # Base risk premium: variance / (bankroll)
    # Interpret: losing 1 std dev when bankroll = 20 BI = 0.5%/20=2.5% bankroll
    base_rp = (variance ** 2) / (2 * bankroll_bb)
    # Scale: bankroll in units of stakes
    base_rp = base_rp / 100.0  # normalize

    # Tilt multiplier (tilt makes losses hurt more + leads to bad decisions)
    tilt_mult = 1.0 + tilt_score * 1.5

    # Recent loss multiplier
    loss_mult = 1.0 + min(recent_loss_bi * 0.15, 0.60)

    # Short bankroll multiplier
    if buyins_at_stake < 15:
        short_mult = 2.0
    elif buyins_at_stake < 25:
        short_mult = 1.5
    elif buyins_at_stake < 40:
        short_mult = 1.2
    else:
        short_mult = 1.0

    rp = base_rp * tilt_mult * loss_mult * short_mult
    return round(max(0.0, rp), 3)


def _variance_ratio(
    ev_high: float,
    std_high: float,
    ev_low: float,
    std_low: float,
) -> float:
    """Sharpe-like ratio: EV / std_dev per line. Higher = better per unit risk."""
    if std_high <= 0:
        return float('inf')
    if std_low <= 0:
        return 0.0
    sharpe_high = ev_high / std_high
    sharpe_low = ev_low / std_low if std_low > 0 else 0.0
    return round(sharpe_high / max(sharpe_low, 0.001), 3)


@dataclass
class VarianceAdvice:
    """Variance-adjusted line selection advice."""
    ev_high_var: float
    std_dev_high_var: float
    ev_low_var: float
    std_dev_low_var: float
    bankroll_bb: float
    current_stake_bb: float
    tilt_score: float
    recent_loss_bi: float
    is_tournament: bool

    # Analysis
    buyins_at_stake: float
    risk_premium_high_var: float           # cost of taking high-var line
    risk_premium_low_var: float            # cost of taking low-var line
    risk_adjusted_ev_high_var: float       # EV - risk_premium
    risk_adjusted_ev_low_var: float
    ev_edge_high_var: float                # raw EV difference (high - low)
    var_adjusted_edge: float               # after risk premium
    sharpe_ratio_high_low: float           # risk-adjusted return ratio

    # Decision
    recommended_line: str                  # 'high_variance', 'low_variance', 'negligible'
    confidence: str                        # 'strong', 'moderate', 'marginal'
    action: str                            # 'choose_high_var', 'choose_low_var', 'coin_flip'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_variance(
    ev_high_var: float = 5.0,
    std_dev_high_var: float = 80.0,
    ev_low_var: float = 3.0,
    std_dev_low_var: float = 15.0,
    bankroll_bb: float = 1500.0,
    current_stake_bb: float = 100.0,
    tilt_score: float = 0.3,
    recent_loss_bi: float = 2.0,
    is_tournament: bool = False,
) -> VarianceAdvice:
    """
    Compare two poker lines (high-variance vs low-variance) on a risk-adjusted basis.

    Args:
        ev_high_var:         EV of the aggressive/high-variance line in BB
        std_dev_high_var:    Standard deviation of the high-variance line in BB
        ev_low_var:          EV of the passive/low-variance line in BB
        std_dev_low_var:     Standard deviation of the low-variance line in BB
        bankroll_bb:         Hero's total bankroll in BB at current stake
        current_stake_bb:    Big blind size in the game (stake level)
        tilt_score:          Hero's current tilt level (0=none, 1=severe)
        recent_loss_bi:      Buy-ins lost recently (this session or last few sessions)
        is_tournament:       If True, variance reduction is less important (ICM applies instead)

    Returns:
        VarianceAdvice
    """
    buyins = round(bankroll_bb / current_stake_bb, 1)

    rp_high = _risk_premium(std_dev_high_var, bankroll_bb, tilt_score, recent_loss_bi, buyins)
    rp_low = _risk_premium(std_dev_low_var, bankroll_bb, tilt_score, recent_loss_bi, buyins)

    adj_ev_high = round(ev_high_var - rp_high, 3)
    adj_ev_low = round(ev_low_var - rp_low, 3)

    ev_edge = round(ev_high_var - ev_low_var, 3)
    adj_edge = round(adj_ev_high - adj_ev_low, 3)

    sharpe_ratio = _variance_ratio(ev_high_var, std_dev_high_var, ev_low_var, std_dev_low_var)

    if is_tournament:
        # In tournaments, ICM typically weighs against high-variance plays
        # For simplicity, add an extra ICM penalty
        adj_ev_high = round(adj_ev_high - std_dev_high_var * 0.01, 3)
        adj_edge = round(adj_ev_high - adj_ev_low, 3)

    # Decision
    if adj_edge > 1.5:
        rec_line = 'high_variance'
        confidence = 'strong'
        action = 'choose_high_var'
    elif adj_edge > 0.5:
        rec_line = 'high_variance'
        confidence = 'moderate'
        action = 'choose_high_var'
    elif adj_edge > -0.5:
        rec_line = 'negligible'
        confidence = 'marginal'
        action = 'coin_flip'
    elif adj_edge > -1.5:
        rec_line = 'low_variance'
        confidence = 'moderate'
        action = 'choose_low_var'
    else:
        rec_line = 'low_variance'
        confidence = 'strong'
        action = 'choose_low_var'

    verdict = (
        f'High-var line: EV={ev_high_var:+.1f}BB, SD={std_dev_high_var:.0f}BB. '
        f'Low-var line: EV={ev_low_var:+.1f}BB, SD={std_dev_low_var:.0f}BB. '
        f'After risk premium: high={adj_ev_high:+.2f}BB low={adj_ev_low:+.2f}BB. '
        f'Bankroll={buyins:.0f}BI. '
        f'Recommendation: {rec_line.upper()} ({confidence} confidence).'
    )

    reasoning = (
        f'Bankroll: {bankroll_bb:.0f}BB ({buyins:.0f} BI). '
        f'Tilt: {tilt_score:.2f}. Recent losses: {recent_loss_bi:.1f} BI. '
        f'Risk premium: high_var={rp_high:.2f}BB low_var={rp_low:.2f}BB. '
        f'Adj EV: high={adj_ev_high:+.2f}BB low={adj_ev_low:+.2f}BB. '
        f'Raw EV edge: {ev_edge:+.2f}BB. Adj edge: {adj_edge:+.2f}BB. '
        f'Sharpe ratio (high/low): {sharpe_ratio:.2f}. '
        f'Action: {action}.'
    )

    tips = []
    if buyins < 20:
        tips.append(
            f'SHORT BANKROLL ({buyins:.0f} BI): Variance STRONGLY favors low-var line. '
            f'One bad downswing could force you to move down or go broke. '
            f'Risk premium is high — sacrifice some EV for survival.'
        )
    elif buyins > 60:
        tips.append(
            f'DEEP BANKROLL ({buyins:.0f} BI): Variance matters less. '
            f'Optimize for pure EV. Take high-var lines when they have edge. '
            f'Long-run, high EV always wins with sufficient bankroll.'
        )
    if tilt_score > 0.5:
        tips.append(
            f'TILT RISK ({tilt_score:.0%}): Under tilt, variance becomes dangerous. '
            f'Even marginally better EV in high-var line is NOT worth it. '
            f'Consider: would you make the correct decision if the high-var play went wrong?'
        )
    if abs(ev_edge) < 1.0:
        tips.append(
            f'CLOSE EV ({ev_edge:+.2f}BB edge): When lines are nearly equal EV, '
            f'always prefer the low-variance line — it reduces risk with no EV cost. '
            f'Low-var line: EV={ev_low_var:+.1f}BB with only {std_dev_low_var:.0f}BB SD.'
        )
    if is_tournament:
        tips.append(
            f'TOURNAMENT: ICM makes variance reduction MORE important, not less. '
            f'Losing chips has greater cost than chip EV suggests. '
            f'Prefer low-variance survival plays unless EV difference is very large (>3BB).'
        )
    if not tips:
        tips.append(
            f'Adj EV: high_var={adj_ev_high:+.2f}BB low_var={adj_ev_low:+.2f}BB. '
            f'Adj edge: {adj_edge:+.2f}BB. '
            f'Recommended: {rec_line.replace("_", " ")} ({confidence}).'
        )

    return VarianceAdvice(
        ev_high_var=round(ev_high_var, 2),
        std_dev_high_var=round(std_dev_high_var, 1),
        ev_low_var=round(ev_low_var, 2),
        std_dev_low_var=round(std_dev_low_var, 1),
        bankroll_bb=round(bankroll_bb, 1),
        current_stake_bb=round(current_stake_bb, 1),
        tilt_score=round(tilt_score, 3),
        recent_loss_bi=round(recent_loss_bi, 2),
        is_tournament=is_tournament,
        buyins_at_stake=buyins,
        risk_premium_high_var=rp_high,
        risk_premium_low_var=rp_low,
        risk_adjusted_ev_high_var=adj_ev_high,
        risk_adjusted_ev_low_var=adj_ev_low,
        ev_edge_high_var=ev_edge,
        var_adjusted_edge=adj_edge,
        sharpe_ratio_high_low=sharpe_ratio,
        recommended_line=rec_line,
        confidence=confidence,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def variance_one_liner(r: VarianceAdvice) -> str:
    return (
        f'[VAR {r.recommended_line.upper()}|{r.buyins_at_stake:.0f}BI] '
        f'{r.action.upper()} | '
        f'raw_edge={r.ev_edge_high_var:+.1f}BB adj_edge={r.var_adjusted_edge:+.1f}BB '
        f'rp_hi={r.risk_premium_high_var:.2f}BB | '
        f'conf={r.confidence}'
    )
