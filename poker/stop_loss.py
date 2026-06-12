"""
Session Stop-Loss Advisor (stop_loss.py)

One of the most costly mistakes in poker: continuing to play after reaching a
mental/financial threshold where decision quality degrades (tilt) or the risk-of-
ruin consequences outweigh expected value.

This module computes real-time stop-loss thresholds based on:
  1. Bankroll position (how many buy-ins lost this session)
  2. Tilt indicators (losses, time played, bad beats)
  3. Table quality (are there still fish to exploit?)
  4. Win rate expectations (is this session likely -EV to continue?)

Key thresholds:
  2-buy-in stop-loss rule: Most professionals use a 2 BI/session loss limit
  Session time limit: Cognitive degradation after 3-4 hours
  Downswing rule: After 5+ buy-ins in a session → automatic stop

Session States:
  'continue'      : Session conditions are favorable
  'take_break'    : Short 15-minute break recommended
  'move_down'     : Consider moving to a lower stake
  'stop_session'  : Session stop-loss triggered
  'emergency_stop': Immediate stop (severe bankroll / tilt conditions)

Usage:
    from poker.stop_loss import analyze_stop_loss, StopLossResult
    result = analyze_stop_loss(
        session_buy_ins_lost=1.5,
        total_bankroll_bis=25.0,
        hands_played=300,
        tilt_score=0.35,
        hours_played=2.5,
        table_quality='good',
    )
    print(result.session_state, result.recommendation)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StopLossResult:
    """Real-time session management recommendation."""
    # Session status
    session_state: str          # 'continue', 'take_break', 'move_down', 'stop_session', 'emergency_stop'
    urgency: str                # 'none', 'low', 'medium', 'high', 'critical'

    # Metrics
    buy_ins_lost: float
    total_bankroll_bis: float
    bankroll_pct_lost: float    # what % of bankroll was lost this session
    hands_played: int
    hours_played: float
    tilt_score: float           # 0=no tilt, 1=full tilt

    # Thresholds
    stop_loss_threshold_bis: float   # trigger stop at this many BIs lost
    break_threshold_bis: float       # take a break at this level
    hands_per_hour: float
    cognitive_limit_hours: float     # hours until decision quality drops

    # Time analysis
    hands_remaining_estimate: int    # estimated hands before cognitive limit
    session_ev_per_100: float        # estimated session EV given current state

    # Recommendation
    recommendation: str
    action_items: List[str] = field(default_factory=list)


def _stop_loss_by_bankroll(total_bankroll_bis: float) -> float:
    """
    Dynamic stop-loss threshold based on bankroll size.
    Larger roll = can risk more per session without catastrophic ruin.
    """
    if total_bankroll_bis >= 50:
        return 3.0   # 50+ BI: can take 3 BI shots
    elif total_bankroll_bis >= 30:
        return 2.5   # 30-50 BI: 2.5 BI stop-loss
    elif total_bankroll_bis >= 20:
        return 2.0   # 20-30 BI: strict 2 BI rule
    else:
        return 1.5   # <20 BI: danger zone, 1.5 BI limit


def _tilt_ev_reduction(tilt_score: float) -> float:
    """
    Estimated EV reduction per 100 hands due to tilt.
    At tilt_score=1.0, playing at -10 BB/100 relative to normal.
    """
    return tilt_score * -15.0   # 0% tilt = 0 reduction, 100% tilt = -15 BB/100


def _cognitive_hours_limit(hands_played: int, hours_played: float) -> float:
    """
    Estimate hours remaining before decision quality meaningfully degrades.
    Most players degrade after 3-4 hours. Shorter sessions recommended.
    """
    base_limit = 3.5   # hours before meaningful degradation
    # If already past 2h and playing fast (>100 hands/hour), shorten limit
    hands_per_hour = hands_played / hours_played if hours_played > 0 else 50
    if hands_per_hour > 120:
        base_limit = 3.0   # fast-paced play is more mentally taxing
    return base_limit


def analyze_stop_loss(
    session_buy_ins_lost: float,
    total_bankroll_bis: float,
    hands_played: int = 0,
    tilt_score: float = 0.0,
    hours_played: float = 0.0,
    table_quality: str = 'average',  # 'excellent', 'good', 'average', 'bad'
    personal_winrate_bb100: float = 5.0,
    std_dev_bb100: float = 90.0,
    stake_nl: int = 25,
) -> StopLossResult:
    """
    Analyze whether to continue, take a break, or stop the session.

    Args:
        session_buy_ins_lost:    Buy-ins lost this session (positive = loss)
        total_bankroll_bis:      Total bankroll in buy-ins at current stake
        hands_played:            Hands played this session
        tilt_score:              0 = focused, 1 = on full tilt
        hours_played:            Hours into the session
        table_quality:           'excellent', 'good', 'average', 'bad'
        personal_winrate_bb100:  Player's estimated win rate
        std_dev_bb100:           Standard deviation of win rate
        stake_nl:                Current stake (e.g. 25 = NL25)

    Returns:
        StopLossResult
    """
    stop_thresh = _stop_loss_by_bankroll(total_bankroll_bis)
    break_thresh = stop_thresh * 0.65  # break at 65% of stop-loss

    bankroll_pct_lost = (session_buy_ins_lost / total_bankroll_bis
                         if total_bankroll_bis > 0 else 0.0)

    hands_per_hour = (hands_played / hours_played if hours_played > 0 else 50)
    cog_limit = _cognitive_hours_limit(hands_played, hours_played)
    time_remaining = max(0.0, cog_limit - hours_played)
    hands_remaining = int(time_remaining * hands_per_hour)

    tilt_ev_adj = _tilt_ev_reduction(tilt_score)
    table_ev_adj = {
        'excellent': +3.0, 'good': +1.0, 'average': 0.0, 'bad': -3.0,
    }.get(table_quality, 0.0)
    session_ev = personal_winrate_bb100 + tilt_ev_adj + table_ev_adj

    # ── Stop-loss logic ────────────────────────────────────────────────────
    # Priority: emergency > stop > break > move_down > continue
    if (session_buy_ins_lost >= stop_thresh + 1.5 or
            (tilt_score >= 0.80 and session_buy_ins_lost >= 1.0) or
            total_bankroll_bis <= 10):
        state = 'emergency_stop'
        urgency = 'critical'
    elif (session_buy_ins_lost >= stop_thresh or
            bankroll_pct_lost >= 0.12 or
            (tilt_score >= 0.65 and session_buy_ins_lost >= break_thresh)):
        state = 'stop_session'
        urgency = 'high'
    elif (session_buy_ins_lost >= break_thresh or
            tilt_score >= 0.50 or
            hours_played >= cog_limit):
        state = 'take_break'
        urgency = 'medium'
    elif (session_ev < 0 or
            (table_quality == 'bad' and session_buy_ins_lost > 0.5)):
        state = 'move_down'
        urgency = 'low'
    else:
        state = 'continue'
        urgency = 'none'

    # ── Recommendation text ────────────────────────────────────────────────
    state_texts = {
        'continue':      f'Continue playing. EV={session_ev:+.1f}BB/100 at {table_quality} table.',
        'take_break':    f'Take a 15-minute break. You are {session_buy_ins_lost:.1f}BI down or {hours_played:.1f}h into session.',
        'move_down':     f'Move down one stake or find a better table. Current EV={session_ev:+.1f}BB/100 is suboptimal.',
        'stop_session':  f'STOP SESSION. You have lost {session_buy_ins_lost:.1f}BI (threshold={stop_thresh:.1f}BI).',
        'emergency_stop': f'EMERGENCY STOP. Severe tilt (score={tilt_score:.0%}) or bankroll in danger ({total_bankroll_bis:.1f}BI remaining).',
    }
    recommendation = state_texts.get(state, 'Continue.')

    # ── Action items ─────────────────────────────────────────────────────────
    action_items = []
    if tilt_score >= 0.40:
        action_items.append(
            f'Tilt detected ({tilt_score:.0%}): step away briefly. '
            f'Do not make big decisions while tilted.'
        )
    if hours_played >= 2.5:
        action_items.append(
            f'Session time: {hours_played:.1f}h. Decision quality may be degrading. '
            f'Take a 10-minute break or end session.'
        )
    if session_buy_ins_lost >= break_thresh:
        action_items.append(
            f'Down {session_buy_ins_lost:.1f} BI. Stop-loss at {stop_thresh:.1f} BI. '
            f'Protect remaining {total_bankroll_bis - session_buy_ins_lost:.1f} BI bankroll.'
        )
    if table_quality == 'bad':
        action_items.append(
            'Table quality is bad (no fish, all regs). Find a better table or stop.'
        )
    if session_ev < 2.0 and state == 'continue':
        action_items.append(
            f'Estimated session EV={session_ev:+.1f}BB/100 is below your normal rate. '
            f'Investigate: is tilt, table selection, or run-bad the cause?'
        )
    if total_bankroll_bis < 20:
        action_items.append(
            f'Bankroll is below 20 BI ({total_bankroll_bis:.1f} BI). '
            f'Consider moving down a stake to NL{stake_nl//2}.'
        )
    if not action_items:
        action_items.append(
            f'Session in good shape. {hands_remaining} more hands before cognitive limit. '
            f'Continue playing {"aggressively" if table_quality in ("excellent","good") else "carefully"}.'
        )

    return StopLossResult(
        session_state=state,
        urgency=urgency,
        buy_ins_lost=round(session_buy_ins_lost, 2),
        total_bankroll_bis=round(total_bankroll_bis, 1),
        bankroll_pct_lost=round(bankroll_pct_lost, 3),
        hands_played=hands_played,
        hours_played=round(hours_played, 1),
        tilt_score=round(tilt_score, 2),
        stop_loss_threshold_bis=round(stop_thresh, 1),
        break_threshold_bis=round(break_thresh, 1),
        hands_per_hour=round(hands_per_hour, 0),
        cognitive_limit_hours=round(cog_limit, 1),
        hands_remaining_estimate=hands_remaining,
        session_ev_per_100=round(session_ev, 1),
        recommendation=recommendation,
        action_items=action_items,
    )


def stop_loss_one_liner(result: StopLossResult) -> str:
    """Single-line overlay summary."""
    urgency_icons = {
        'none': '', 'low': '[!]', 'medium': '[!!]', 'high': '[!!!]', 'critical': '[STOP]',
    }
    icon = urgency_icons.get(result.urgency, '')
    return (
        f'{icon} {result.session_state.upper().replace("_", " ")} | '
        f'-{result.buy_ins_lost:.1f}BI/{result.stop_loss_threshold_bis:.1f} | '
        f'EV={result.session_ev_per_100:+.0f} | '
        f'tilt={result.tilt_score:.0%}'
    )
