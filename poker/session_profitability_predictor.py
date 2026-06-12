"""
Session Profitability Predictor (session_profitability_predictor.py)

Before starting a session, predict expected profitability based on multiple
factors: game quality, hero's win rate, mental state, and session parameters.

This module helps decide:
  - Should I play this session at all?
  - How long should I play?
  - What's my stop-loss / take-profit target?
  - Is the expected value positive enough to justify my time?

PREDICTION MODEL:
  base_wr_adj = hero_win_rate * game_quality_multiplier
  mental_adj  = -tilt_risk * wr_penalty
  session_ev  = (base_wr_adj + mental_adj) * est_hands / 100
  session_std = sqrt(session_hands) * std_dev_bb100 / 10  (simplified)

GAME QUALITY MULTIPLIERS:
  Excellent (3+ fish):       1.8-2.0x
  Good (2 fish):             1.3-1.5x
  Average (1 fish):          1.0-1.2x
  Tough (0 fish, regs):      0.5-0.8x
  Terrible (all nits/regs):  0.2-0.5x

MENTAL STATE MODIFIERS:
  Fresh (0 tilt, well rested): 1.0x (no penalty)
  Slight tilt (0.2-0.3):       -0.5 BB/100 penalty
  Moderate tilt (0.4-0.6):     -1.5 BB/100 penalty
  High tilt (0.7-0.9):         -3.0 BB/100 penalty
  Severe tilt (1.0):           Session EV likely negative; skip

Usage:
    from poker.session_profitability_predictor import predict_session, SessionPrediction, spp_one_liner

    pred = predict_session(
        hero_win_rate_bb100=4.0,
        fish_count=2,
        reg_count=3,
        hero_tilt_risk=0.2,
        planned_hours=4.0,
        game_format='6max',
        hero_std_dev_bb100=80.0,
    )
    print(spp_one_liner(pred))
"""

import math
from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

_GAME_QUALITY_MULT = {
    'excellent':    1.80,   # 3+ fish at table
    'good':         1.35,
    'average':      1.00,
    'tough':        0.65,
    'terrible':     0.30,
}

_TILT_WR_PENALTY = {
    (0.0, 0.15): 0.0,
    (0.15, 0.35): 0.5,
    (0.35, 0.55): 1.5,
    (0.55, 0.75): 3.0,
    (0.75, 1.01): 5.0,
}

_HANDS_PER_HOUR = {
    '6max':       240,
    'full_ring':  200,
    'heads_up':   300,
    'mtt':        80,
    'sng':        100,
}


def _game_quality(fish_count: int, reg_count: int, n_players: int = 6) -> str:
    fish_pct = fish_count / max(n_players - 1, 1)
    if fish_count >= 3 or fish_pct >= 0.50:
        return 'excellent'
    if fish_count >= 2 or fish_pct >= 0.30:
        return 'good'
    if fish_count >= 1 or fish_pct >= 0.15:
        return 'average'
    if reg_count >= n_players - 2:
        return 'tough'
    return 'terrible'


def _tilt_penalty(tilt_risk: float) -> float:
    for (lo, hi), penalty in _TILT_WR_PENALTY.items():
        if lo <= tilt_risk < hi:
            return penalty
    return 5.0


def _session_std_dev(hands: int, std_dev_bb100: float) -> float:
    """Standard deviation of session result in BB."""
    return round(math.sqrt(hands) * std_dev_bb100 / 10.0, 1)


def _prob_positive_session(expected_ev: float, std_dev: float) -> float:
    """P(result > 0) using normal approximation."""
    if std_dev <= 0:
        return 1.0 if expected_ev > 0 else 0.0
    z = expected_ev / std_dev
    # Approximation: P(Z > -z) ~ sigmoid(1.7*z)
    p = 1 / (1 + math.exp(-1.7 * z))
    return round(max(0.0, min(1.0, p)), 3)


def _recommended_session_length(adj_wr: float, game_quality: str) -> float:
    """Recommended hours based on adjusted win rate."""
    if adj_wr <= 0:
        return 0.0    # skip this session
    if adj_wr < 2.0:
        return 2.0    # short session only
    if adj_wr < 4.0:
        return 4.0    # standard
    if game_quality in ('excellent', 'good'):
        return 6.0    # great game: play longer
    return 4.0


@dataclass
class SessionPrediction:
    # Inputs
    hero_win_rate_bb100: float
    fish_count: int
    reg_count: int
    hero_tilt_risk: float
    planned_hours: float
    game_format: str
    hero_std_dev_bb100: float
    n_players: int

    # Game assessment
    game_quality: str           # 'excellent', 'good', 'average', 'tough', 'terrible'
    quality_multiplier: float
    tilt_penalty_bb100: float
    adjusted_wr_bb100: float    # win rate after quality + tilt adjustments

    # Session estimates
    est_hands: int
    session_ev_bb: float        # expected BB profit/loss this session
    session_std_dev_bb: float   # standard deviation of result
    prob_positive_session: float

    # Recommendations
    session_recommendation: str  # 'play', 'skip', 'short_session', 'take_shot'
    recommended_hours: float
    stop_loss_bb: float          # when to quit if losing
    take_profit_bb: float        # when to quit if winning (optional)
    hourly_ev_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def predict_session(
    hero_win_rate_bb100: float = 4.0,
    fish_count: int = 1,
    reg_count: int = 3,
    hero_tilt_risk: float = 0.2,
    planned_hours: float = 4.0,
    game_format: str = '6max',
    hero_std_dev_bb100: float = 80.0,
    n_players: int = 6,
    n_tables: int = 1,
) -> SessionPrediction:
    """
    Predict session profitability before sitting down to play.

    Args:
        hero_win_rate_bb100:  Hero's estimated BB/100 at this format
        fish_count:           Number of recreational players at the table
        reg_count:            Number of solid regulars at the table
        hero_tilt_risk:       Hero's current tilt/mental fatigue (0=fresh, 1=severe)
        planned_hours:        Planned session length in hours
        game_format:          '6max', 'full_ring', 'heads_up', 'mtt', 'sng'
        hero_std_dev_bb100:   Hero's standard deviation in BB per 100 hands
        n_players:            Players at the table
        n_tables:             Number of tables being played simultaneously

    Returns:
        SessionPrediction
    """
    quality = _game_quality(fish_count, reg_count, n_players)
    quality_mult = _GAME_QUALITY_MULT[quality]
    tilt_pen = _tilt_penalty(hero_tilt_risk)

    adj_wr = round(hero_win_rate_bb100 * quality_mult - tilt_pen, 2)

    hph = _HANDS_PER_HOUR.get(game_format, 200) * n_tables
    est_hands = int(hph * planned_hours)

    session_ev = round(adj_wr / 100 * est_hands, 1)
    session_std = _session_std_dev(est_hands, hero_std_dev_bb100)
    prob_pos = _prob_positive_session(session_ev, session_std)

    rec_hours = _recommended_session_length(adj_wr, quality)

    # Session recommendation
    if adj_wr <= 0 or hero_tilt_risk >= 0.75:
        rec = 'skip'
    elif adj_wr >= 3.0 and quality in ('excellent', 'good') and hero_tilt_risk < 0.3:
        rec = 'play'
    elif adj_wr >= 1.5:
        rec = 'short_session'
    elif adj_wr > 0 and quality in ('excellent', 'good'):
        rec = 'take_shot'
    else:
        rec = 'skip'

    # Stop-loss: quit when down ~2 buy-ins (200 BB) or 3x expected hourly loss
    stop_loss = max(-200.0, min(-50.0, round(-abs(session_std * 1.5), 0)))

    # Take-profit: quit when up 3x expected EV
    take_profit = round(max(session_ev * 3, 150.0), 0) if session_ev > 0 else 0.0

    hourly_ev = round(adj_wr / 100 * hph, 2)

    reasoning = (
        f'Game: {quality} ({fish_count} fish, {reg_count} regs). '
        f'Quality mult: {quality_mult:.2f}x. Tilt penalty: -{tilt_pen:.1f}BB/100. '
        f'Adj WR: {adj_wr:+.2f}BB/100. '
        f'{est_hands} hands in {planned_hours:.0f}h. '
        f'Session EV: {session_ev:+.0f}BB. Prob positive: {prob_pos:.0%}.'
    )

    verdict = (
        f'SESSION PREDICTION: {rec.upper()}. '
        f'Adj WR: {adj_wr:+.2f}BB/100. '
        f'Expected {session_ev:+.0f}BB over {planned_hours:.0f}h ({prob_pos:.0%} prob positive). '
        f'Stop-loss: {stop_loss:.0f}BB. Hourly EV: {hourly_ev:+.2f}BB/hr.'
    )

    tips = []

    if rec == 'skip':
        if hero_tilt_risk >= 0.75:
            tips.append(
                f'SKIP (TILT RISK): Tilt risk={hero_tilt_risk:.0%} is too high. '
                f'Mental edge is gone. Expected WR drops to {adj_wr:+.2f}BB/100. '
                f'Rest, recover, and come back tomorrow.'
            )
        else:
            tips.append(
                f'SKIP (POOR GAME): Game quality is {quality}. '
                f'Adj WR={adj_wr:+.2f}BB/100 -- not worth your time. '
                f'Find a better table or wait for the fish to arrive.'
            )
    elif rec == 'play':
        tips.append(
            f'GREAT SESSION OPPORTUNITY: {quality.upper()} game + fresh mindset. '
            f'Adj WR={adj_wr:+.2f}BB/100. Play the full {rec_hours:.0f}h. '
            f'Set stop-loss at {stop_loss:.0f}BB. Extend session if game stays good.'
        )
    elif rec == 'short_session':
        tips.append(
            f'SHORT SESSION: Conditions are marginal. Play {rec_hours:.0f}h max. '
            f'Adj WR={adj_wr:+.2f}BB/100. Stop-loss: {stop_loss:.0f}BB. '
            f'Leave early if game deteriorates.'
        )

    if quality in ('excellent', 'good'):
        tips.append(
            f'FISH MANAGEMENT: {fish_count} fish at the table. '
            f'Do NOT leave while fish are present. '
            f'Seat to the left of the biggest fish. '
            f'Maximize hands vs fish: isolate, 3-bet wide, value bet thin.'
        )

    if hero_tilt_risk > 0.3 and rec != 'skip':
        tips.append(
            f'TILT CAUTION: Risk={hero_tilt_risk:.0%} is elevated. '
            f'Consider: break every 90min, strict stop-loss at {stop_loss:.0f}BB. '
            f'If you lose first 2 buy-ins in 30min: leave immediately.'
        )

    if not tips:
        tips.append(
            f'Adj WR={adj_wr:+.2f}BB/100. Session EV={session_ev:+.0f}BB ({prob_pos:.0%} win). '
            f'Hourly: {hourly_ev:+.2f}BB/hr. Stop-loss: {stop_loss:.0f}BB.'
        )

    return SessionPrediction(
        hero_win_rate_bb100=round(hero_win_rate_bb100, 2),
        fish_count=fish_count,
        reg_count=reg_count,
        hero_tilt_risk=round(hero_tilt_risk, 3),
        planned_hours=round(planned_hours, 1),
        game_format=game_format,
        hero_std_dev_bb100=round(hero_std_dev_bb100, 1),
        n_players=n_players,
        game_quality=quality,
        quality_multiplier=quality_mult,
        tilt_penalty_bb100=tilt_pen,
        adjusted_wr_bb100=adj_wr,
        est_hands=est_hands,
        session_ev_bb=session_ev,
        session_std_dev_bb=session_std,
        prob_positive_session=prob_pos,
        session_recommendation=rec,
        recommended_hours=rec_hours,
        stop_loss_bb=stop_loss,
        take_profit_bb=take_profit,
        hourly_ev_bb=hourly_ev,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def spp_one_liner(r: SessionPrediction) -> str:
    return (
        f'[SPP {r.game_quality.upper()}|{r.game_format}] '
        f'{r.session_recommendation.upper()} | '
        f'adj_wr={r.adjusted_wr_bb100:+.2f}BB/100 ev={r.session_ev_bb:+.0f}BB '
        f'({r.prob_positive_session:.0%}pos) | '
        f'stop={r.stop_loss_bb:.0f}BB hr={r.hourly_ev_bb:+.2f}BB/hr'
    )
