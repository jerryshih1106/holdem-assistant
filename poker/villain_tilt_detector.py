"""
Villain Tilt Detector (villain_tilt_detector.py)

When a villain goes "on tilt," their play changes in predictable ways:
  - VPIP increases (playing more hands after a bad beat)
  - Bet sizing increases (trying to win back losses quickly)
  - 3-bet frequency spikes
  - Call-down frequency spikes (station mode)
  - Check-fold frequency drops (they won't give up)

DETECTING TILT:
  The module compares villain's CURRENT session stats to their
  long-term BASELINE stats. Significant deviations signal tilt.

TILT TYPES:
  1. Aggression tilt:   Bet/raise every spot, over-represent every hand
  2. Station tilt:      Call everything, won't fold to pressure
  3. Maniac tilt:       All-in at any opportunity
  4. Steam tilt:        Wide opens, loose calls, erratic sizing
  5. Passive tilt:      Shell-shocked, check-fold mode (rare but exists)
  6. No tilt:           Playing normally

EXPLOITATION BY TILT TYPE:
  Aggression tilt → Check strong hands, let them barrel into you
  Station tilt    → Value bet relentlessly, stop bluffing
  Maniac tilt     → Tighten starting hands, trap with premiums
  Steam tilt      → Call-down more with marginal hands (they over-bluff)
  Passive tilt    → Bluff more, they won't fight back
  No tilt         → Normal GTO-adjusted strategy

TILT INDICATORS AND WEIGHTS:
  VPIP spike (+15%+):           High indicator (playing way more hands)
  Avg bet size spike (1.5x+):   High indicator (betting too large)
  3bet spike (+8%+):            Medium indicator
  Showdown rate spike (+15%+):  Medium indicator (station behavior)
  Consecutive losses (3+):      Medium indicator (from session tracker)
  Recent big pot loss:          High indicator (tilted after losing bigpot)

TILT SCORE: 0 (not tilting) to 1.0 (severely tilting)
  0.0 - 0.30: no tilt or mild (normal play)
  0.30 - 0.60: moderate tilt (adjust play)
  0.60 - 0.80: significant tilt (heavy exploitation)
  0.80 - 1.00: severe tilt (max exploitation)

Usage:
    from poker.villain_tilt_detector import detect_villain_tilt
    from poker.villain_tilt_detector import VillainTiltResult, tilt_one_liner

    result = detect_villain_tilt(
        current_vpip=0.48,
        baseline_vpip=0.28,
        current_avg_bet_size=0.85,
        baseline_avg_bet_size=0.55,
        current_3bet=0.14,
        baseline_3bet=0.06,
        current_wtsd=0.38,
        baseline_wtsd=0.22,
        consecutive_losses=3,
        big_pot_loss_bb=80.0,
        total_session_hands=45,
    )
    print(tilt_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# ── Tilt detection weights ────────────────────────────────────────────────────

_INDICATOR_WEIGHTS = {
    'vpip_spike':          0.30,
    'bet_size_spike':      0.25,
    'threbet_spike':       0.15,
    'wtsd_spike':          0.15,
    'consecutive_losses':  0.10,
    'big_pot_loss':        0.05,
}


def _vpip_spike_score(current: float, baseline: float) -> float:
    """VPIP spike: +15% = 1.0 score."""
    delta = current - baseline
    return min(max(delta / 0.15, 0.0), 1.0)


def _bet_size_spike_score(current: float, baseline: float) -> float:
    """Bet size spike: 1.5x = 1.0 score."""
    if baseline <= 0:
        return 0.0
    ratio = current / baseline
    return min(max((ratio - 1.0) / 0.50, 0.0), 1.0)


def _threbet_spike_score(current: float, baseline: float) -> float:
    """3bet spike: +8% = 1.0 score."""
    delta = current - baseline
    return min(max(delta / 0.08, 0.0), 1.0)


def _wtsd_spike_score(current: float, baseline: float) -> float:
    """WTSD spike: +15% = 1.0 score."""
    delta = current - baseline
    return min(max(delta / 0.15, 0.0), 1.0)


def _consecutive_loss_score(losses: int) -> float:
    """Consecutive losses: 5+ = 1.0 score."""
    return min(max(losses / 5.0, 0.0), 1.0)


def _big_pot_loss_score(loss_bb: float) -> float:
    """Big pot loss: 100BB+ = 1.0 score."""
    return min(max(loss_bb / 100.0, 0.0), 1.0)


def _tilt_score(
    vpip_score, bet_score, threbet_score, wtsd_score,
    loss_score, bigpot_score,
) -> float:
    scores = {
        'vpip_spike':          vpip_score,
        'bet_size_spike':      bet_score,
        'threbet_spike':       threbet_score,
        'wtsd_spike':          wtsd_score,
        'consecutive_losses':  loss_score,
        'big_pot_loss':        bigpot_score,
    }
    weighted = sum(scores[k] * _INDICATOR_WEIGHTS[k] for k in scores)
    return round(min(weighted, 1.0), 3)


def _tilt_level(score: float) -> str:
    if score >= 0.80: return 'severe'
    if score >= 0.60: return 'significant'
    if score >= 0.30: return 'moderate'
    return 'none'


def _classify_tilt_type(
    vpip_delta: float, bet_ratio: float, threbet_delta: float,
    wtsd_delta: float, consecutive_losses: int,
) -> str:
    """Classify the TYPE of tilt based on which indicators spike."""
    # Station tilt: high VPIP + high WTSD, not aggressive
    if wtsd_delta >= 0.12 and vpip_delta >= 0.08 and threbet_delta < 0.05:
        return 'station_tilt'
    # Aggression tilt: high 3bet + high bet size, not necessarily more hands
    if threbet_delta >= 0.08 and bet_ratio >= 1.4:
        return 'aggression_tilt'
    # Maniac tilt: very high VPIP + very high bet + high 3bet
    if vpip_delta >= 0.20 and bet_ratio >= 1.6 and threbet_delta >= 0.06:
        return 'maniac_tilt'
    # Steam tilt: moderate spike everywhere
    if vpip_delta >= 0.10 and bet_ratio >= 1.2 and (threbet_delta >= 0.04 or wtsd_delta >= 0.08):
        return 'steam_tilt'
    # Passive tilt: VPIP DOWN, WTSD DOWN (shell-shocked)
    if vpip_delta <= -0.10 and wtsd_delta <= -0.08:
        return 'passive_tilt'
    return 'no_tilt'


def _exploitation_strategy(tilt_type: str, tilt_level: str) -> str:
    if tilt_type == 'station_tilt':
        return (
            'STATION TILT: Value bet relentlessly. '
            'Bet 3 streets with top pair+. '
            'STOP bluffing — they call everything. '
            'Size up: 75-100%pot instead of 50%pot. '
            'Thin value: bet even with one pair on safe boards.'
        )
    if tilt_type == 'aggression_tilt':
        return (
            'AGGRESSION TILT: Let them hang themselves. '
            'Check strong hands to trigger their aggression. '
            'Call-down wider than normal — they bluff too often. '
            'Do NOT 3-bet light; they will call/jam back. '
            'Trap with premium hands — check-raise when they barrel.'
        )
    if tilt_type == 'maniac_tilt':
        return (
            'MANIAC TILT: Tighten starting hands but widen calling. '
            'Premium hands only in marginal spots. '
            'Call-down with top pair+ — maniacs have weak ranges. '
            'Do NOT bluff a maniac. '
            'Consider isolating: open large to play them HU.'
        )
    if tilt_type == 'steam_tilt':
        return (
            'STEAM TILT: Play value-heavy, call-down wider. '
            'Villain is playing too many hands too fast. '
            'Value bet top pair 3 streets. '
            'Exploit wide pre-flop opens: 3-bet light IP. '
            'Watch for tells: bet-sizing tells, speed of action.'
        )
    if tilt_type == 'passive_tilt':
        return (
            'PASSIVE TILT (shell-shocked): Bluff more. '
            'Villain is in survival mode — they fold easily. '
            'Frequent small bets extract folds. '
            'Stop trying to value bet: they check-fold everything. '
            'C-bet every board — their flop fold rate is very high now.'
        )
    return 'No tilt detected. Play normal GTO-adjusted strategy.'


def _reliability_note(total_hands: int) -> str:
    if total_hands < 20:
        return f'LOW SAMPLE ({total_hands} hands): tilt detection unreliable. Wait for 30+ hands.'
    if total_hands < 50:
        return f'SMALL SAMPLE ({total_hands} hands): moderate reliability. Use with caution.'
    return f'SUFFICIENT SAMPLE ({total_hands} hands): tilt detection is reliable.'


@dataclass
class VillainTiltResult:
    """Villain tilt analysis result."""
    current_vpip: float
    baseline_vpip: float
    current_avg_bet_size: float
    baseline_avg_bet_size: float
    current_3bet: float
    baseline_3bet: float
    current_wtsd: float
    baseline_wtsd: float
    consecutive_losses: int
    big_pot_loss_bb: float
    total_session_hands: int

    # Analysis
    vpip_delta: float
    bet_size_ratio: float           # current / baseline
    tilt_score: float               # 0-1
    tilt_level: str                 # 'none', 'moderate', 'significant', 'severe'
    tilt_type: str                  # 'no_tilt', 'station_tilt', 'aggression_tilt', etc.

    # Exploitation
    exploitation_strategy: str
    reliability_note: str

    # Indicator breakdown
    indicator_scores: dict

    reasoning: str
    tips: List[str] = field(default_factory=list)


def detect_villain_tilt(
    current_vpip: float = 0.48,
    baseline_vpip: float = 0.28,
    current_avg_bet_size: float = 0.85,
    baseline_avg_bet_size: float = 0.55,
    current_3bet: float = 0.14,
    baseline_3bet: float = 0.06,
    current_wtsd: float = 0.38,
    baseline_wtsd: float = 0.22,
    consecutive_losses: int = 3,
    big_pot_loss_bb: float = 80.0,
    total_session_hands: int = 45,
) -> VillainTiltResult:
    """
    Detect if a villain is tilting and how to exploit them.

    Args:
        current_vpip:           Villain's VPIP in current session
        baseline_vpip:          Villain's normal long-term VPIP
        current_avg_bet_size:   Current average bet size (as fraction of pot)
        baseline_avg_bet_size:  Baseline average bet size
        current_3bet:           Current 3-bet frequency
        baseline_3bet:          Baseline 3-bet frequency
        current_wtsd:           Current WTSD rate
        baseline_wtsd:          Baseline WTSD rate
        consecutive_losses:     How many pots lost in a row
        big_pot_loss_bb:        Size of biggest recent pot loss in BB
        total_session_hands:    Total hands observed this session

    Returns:
        VillainTiltResult
    """
    vpip_delta = round(current_vpip - baseline_vpip, 3)
    bet_ratio = round(current_avg_bet_size / max(baseline_avg_bet_size, 0.01), 2)
    threbet_delta = round(current_3bet - baseline_3bet, 3)
    wtsd_delta = round(current_wtsd - baseline_wtsd, 3)

    # Individual indicator scores
    vs = _vpip_spike_score(current_vpip, baseline_vpip)
    bs = _bet_size_spike_score(current_avg_bet_size, baseline_avg_bet_size)
    ts = _threbet_spike_score(current_3bet, baseline_3bet)
    ws = _wtsd_spike_score(current_wtsd, baseline_wtsd)
    ls = _consecutive_loss_score(consecutive_losses)
    ps = _big_pot_loss_score(big_pot_loss_bb)

    indicator_scores = {
        'vpip_spike':          round(vs, 2),
        'bet_size_spike':      round(bs, 2),
        'threbet_spike':       round(ts, 2),
        'wtsd_spike':          round(ws, 2),
        'consecutive_losses':  round(ls, 2),
        'big_pot_loss':        round(ps, 2),
    }

    score = _tilt_score(vs, bs, ts, ws, ls, ps)
    level = _tilt_level(score)
    ttype = _classify_tilt_type(vpip_delta, bet_ratio, threbet_delta, wtsd_delta, consecutive_losses)
    exploit = _exploitation_strategy(ttype, level)
    reliability = _reliability_note(total_session_hands)

    reasoning = (
        f'Tilt analysis: VPIP {baseline_vpip:.0%}→{current_vpip:.0%} ({vpip_delta:+.0%}), '
        f'BetSize {baseline_avg_bet_size:.0%}→{current_avg_bet_size:.0%} (ratio={bet_ratio:.1f}x), '
        f'3bet {baseline_3bet:.0%}→{current_3bet:.0%} ({threbet_delta:+.0%}), '
        f'WTSD {baseline_wtsd:.0%}→{current_wtsd:.0%} ({wtsd_delta:+.0%}), '
        f'losses={consecutive_losses}, bigpot={big_pot_loss_bb:.0f}BB. '
        f'Score={score:.2f} level={level} type={ttype}.'
    )

    # Tips
    tips = []
    if level == 'none':
        tips.append(
            f'NO TILT DETECTED: Villain (score={score:.2f}) appears to be playing normally. '
            f'VPIP {baseline_vpip:.0%}→{current_vpip:.0%}, BetSize {bet_ratio:.1f}x. '
            f'Continue standard GTO-adjusted strategy.'
        )
    elif level in ('significant', 'severe'):
        tips.append(
            f'{level.upper()} TILT DETECTED (score={score:.2f}): '
            f'Villain is clearly {ttype.replace("_", " ")}. '
            f'VPIP spike: +{vpip_delta:.0%}. Bet size: {bet_ratio:.1f}x normal. '
            f'IMMEDIATE EXPLOITATION: {exploit[:100]}...'
        )
    elif level == 'moderate':
        tips.append(
            f'MODERATE TILT (score={score:.2f}): '
            f'Villain shows early tilt signs. '
            f'Adjust: {exploit[:80]}...'
        )
    if total_session_hands < 30:
        tips.append(
            f'SMALL SAMPLE WARNING: Only {total_session_hands} hands observed. '
            f'Tilt detection needs 30+ hands to be reliable. '
            f'Use cautiously — what looks like tilt may be natural variance.'
        )
    if ttype == 'station_tilt':
        tips.append(
            'STATION TILT EXPLOITATION: '
            'Value bet EVERY street with top pair+. '
            'Bet size: 75-100%pot (they call anyway). '
            'Do NOT bluff: total waste of chips. '
            'Even thin value like bottom pair may be good on the right board.'
        )
    if ttype == 'aggression_tilt':
        tips.append(
            'AGGRESSION TILT EXPLOITATION: '
            'Your checks become very powerful. '
            'Let them barrel 3 streets into your sets and two pairs. '
            'Increase check-raise frequency on strong hands. '
            'Widen call-down range vs their large bets.'
        )

    return VillainTiltResult(
        current_vpip=round(current_vpip, 3),
        baseline_vpip=round(baseline_vpip, 3),
        current_avg_bet_size=round(current_avg_bet_size, 3),
        baseline_avg_bet_size=round(baseline_avg_bet_size, 3),
        current_3bet=round(current_3bet, 3),
        baseline_3bet=round(baseline_3bet, 3),
        current_wtsd=round(current_wtsd, 3),
        baseline_wtsd=round(baseline_wtsd, 3),
        consecutive_losses=consecutive_losses,
        big_pot_loss_bb=round(big_pot_loss_bb, 1),
        total_session_hands=total_session_hands,
        vpip_delta=vpip_delta,
        bet_size_ratio=bet_ratio,
        tilt_score=score,
        tilt_level=level,
        tilt_type=ttype,
        exploitation_strategy=exploit,
        reliability_note=reliability,
        indicator_scores=indicator_scores,
        reasoning=reasoning,
        tips=tips,
    )


def tilt_one_liner(r: VillainTiltResult) -> str:
    return (
        f'[TILT] score={r.tilt_score:.2f} level={r.tilt_level} type={r.tilt_type} | '
        f'vpip +{r.vpip_delta:.0%} bet_ratio={r.bet_size_ratio:.1f}x '
        f'3b +{r.current_3bet - r.baseline_3bet:.0%} | '
        f'{r.total_session_hands}hands'
    )
