"""
Tilt Management Guide (tilt_management_guide.py)

Tilt = playing sub-optimally due to emotional state after bad beats,
losing streaks, or fatigue. Quantifies tilt severity and prescribes
corrective actions (breaks, stop-losses, table exits).

THEORY:
  WHAT IS TILT?
  Tilt causes deviations from optimal play: playing too many hands (VPIP+),
  over-bluffing (aggression+), calling too wide (WTS+), or chasing losses
  (loss-aversion bias). Even mild tilt is costly: +5% VPIP can cost 3+ BB/100.

  TILT TRIGGERS AND SEVERITY:
  - Bad beat (lost when 80%+ favorite): high severity, ~30 hands affected
  - Cooler (set over set, AA vs KK): moderate-high, ~20 hands
  - Losing streak (multiple losses): high severity, ~40 hands
  - Long session (4+ hours): creeping fatigue tilt
  - Aggressive villain (constant 3-bets, banter): mild-moderate

  TILT SCORING:
  tilt_score = sum(trigger_severity * recency_decay) + bb_loss_factor
  recency_decay = 1.0 if hands_since < 5; decay by 0.05/hand thereafter
  bb_loss_factor = min(0.50, bb_lost / (2 * buy_in_bb))

  TILT LEVELS:
  none (0-20%): Play normally
  mild (20-45%): Take 5-minute break; reduce tables; tighten range slightly
  moderate (45-70%): STOP playing; 30+ minute break
  severe (70%+): Quit session; no play today

  STOP-LOSS RULES:
  Hard stop-loss: 2 buy-ins in a session -> stop regardless of tilt level
  Tilt stop-loss: ANY moderate/severe tilt -> stop immediately
  Time stop-loss: 5+ hours -> mandatory 30-minute break

  RECOVERY STRATEGIES:
  - Physical: walk, stretch, hydrate (brain needs glucose + oxygen)
  - Mental: accept variance, review hand for study (not in session)
  - Behavioral: tighten VPIP -5%, eliminate bluffs, value bet only

DISTINCT FROM:
  villain_tilt_detector.py:  Detecting OPPONENT tilt (exploit)
  stop_loss.py:              Stop-loss rule implementation
  session_opening_strategy.py: Session health tracking
  THIS MODULE:               HERO TILT specifically; self-assessment;
                             scoring; break recommendations; recovery.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


TILT_TRIGGER_SEVERITY: dict = {
    'bad_beat':              0.90,
    'losing_streak':         0.80,
    'cooler':                0.70,
    'missed_big_draw':       0.55,
    'opponent_trash_talk':   0.50,
    'aggressive_villain':    0.40,
    'long_session':          0.35,
    'multi_table_fatigue':   0.30,
    'distraction':           0.25,
}

TRIGGER_HANDS_AFFECTED: dict = {
    'bad_beat':              30,
    'losing_streak':         40,
    'cooler':                20,
    'missed_big_draw':       15,
    'opponent_trash_talk':   20,
    'aggressive_villain':    10,
    'long_session':          999,
    'multi_table_fatigue':   999,
    'distraction':           10,
}

TILT_LEVEL_THRESHOLDS: dict = {
    'none':     (0.00, 0.20),
    'mild':     (0.20, 0.45),
    'moderate': (0.45, 0.70),
    'severe':   (0.70, 1.00),
}

TILT_BEHAVIOR_CHANGES: dict = {
    'none':     {'vpip_adj': 0.00, 'aggr_adj': 0.00, 'call_adj': 0.00, 'bluff_adj': 0.00},
    'mild':     {'vpip_adj': 0.05, 'aggr_adj': 0.05, 'call_adj': 0.08, 'bluff_adj': 0.08},
    'moderate': {'vpip_adj': 0.12, 'aggr_adj': 0.15, 'call_adj': 0.18, 'bluff_adj': 0.18},
    'severe':   {'vpip_adj': 0.25, 'aggr_adj': 0.30, 'call_adj': 0.30, 'bluff_adj': 0.35},
}

TILT_STOP_ACTION: dict = {
    'none':     'PLAY_NORMALLY',
    'mild':     'TAKE_5MIN_BREAK',
    'moderate': 'STOP_30MIN_BREAK',
    'severe':   'QUIT_SESSION',
}

TILT_CORRECTIONS: dict = {
    'none':     [],
    'mild':     ['Tighten VPIP by 5%', 'Eliminate marginal bluffs', 'Reduce to 1 table if multi-tabling'],
    'moderate': ['Stop immediately', 'Do not play for 30+ min', 'Physical break: walk/stretch/hydrate'],
    'severe':   ['End session now', 'No poker today', 'Review session tomorrow (not now)', 'Meditation or sleep'],
}

HARD_STOP_LOSS_BUY_INS: float = 2.0


def _recency_weight(hands_since_trigger: int, hands_affected: int) -> float:
    if hands_since_trigger <= 5:
        return 1.0
    decay = max(0.0, 1.0 - 0.04 * (hands_since_trigger - 5))
    return round(min(1.0, decay * (hands_affected / max(hands_affected, hands_since_trigger))), 3)


def _tilt_score(
    triggers: List[str],
    hands_since_trigger: int,
    bb_loss: float,
    buy_in_bb: float,
    session_hours: float,
) -> float:
    trigger_score = 0.0
    for t in triggers:
        sev = TILT_TRIGGER_SEVERITY.get(t, 0.30)
        affected = TRIGGER_HANDS_AFFECTED.get(t, 15)
        weight = _recency_weight(hands_since_trigger, affected)
        trigger_score += sev * weight

    trigger_score = min(0.80, trigger_score)

    loss_factor = min(0.40, bb_loss / (2.0 * buy_in_bb)) if buy_in_bb > 0 else 0.0
    time_factor = min(0.20, max(0.0, (session_hours - 3.0) * 0.05))

    total = round(min(1.0, trigger_score + loss_factor + time_factor), 3)
    return total


def _tilt_level(score: float) -> str:
    for level, (lo, hi) in TILT_LEVEL_THRESHOLDS.items():
        if lo <= score < hi:
            return level
    return 'severe'


def _hard_stop_triggered(bb_loss: float, buy_in_bb: float) -> bool:
    if buy_in_bb <= 0:
        return False
    return (bb_loss / buy_in_bb) >= HARD_STOP_LOSS_BUY_INS


@dataclass
class TiltManagementResult:
    triggers: List[str]
    hands_since_trigger: int
    bb_loss: float
    buy_in_bb: float
    session_hours: float

    tilt_score: float
    tilt_level: str
    stop_action: str
    hard_stop: bool
    behavior_changes: Dict[str, float]
    corrections: List[str]

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_tilt_management(
    triggers: Optional[List[str]] = None,
    hands_since_trigger: int = 0,
    bb_loss: float = 0.0,
    buy_in_bb: float = 100.0,
    session_hours: float = 2.0,
) -> TiltManagementResult:
    """
    Assess hero tilt level and recommend corrective actions.

    Args:
        triggers:             Active tilt triggers ('bad_beat','cooler','losing_streak',...)
        hands_since_trigger:  Hands played since last trigger event
        bb_loss:              BB lost this session (positive = losing)
        buy_in_bb:            Standard buy-in in BB (100 for 100BB standard)
        session_hours:        Hours played in this session

    Returns:
        TiltManagementResult
    """
    if triggers is None:
        triggers = []

    score = _tilt_score(triggers, hands_since_trigger, bb_loss, buy_in_bb, session_hours)
    level = _tilt_level(score)
    stop_action = TILT_STOP_ACTION[level]
    hard_stop = _hard_stop_triggered(bb_loss, buy_in_bb)
    behavior = TILT_BEHAVIOR_CHANGES[level]
    corrections = TILT_CORRECTIONS[level]

    if hard_stop and level in ('none', 'mild'):
        stop_action = 'HARD_STOP_LOSS_TRIGGERED'
        level = 'moderate'

    verdict = (
        f'[TILT score={score:.2f}|{level}] '
        f'action={stop_action} '
        f'{"HARD_STOP " if hard_stop else ""}'
        f'VPIP+{behavior["vpip_adj"]:.0%} AGGR+{behavior["aggr_adj"]:.0%}'
    )

    reasoning = (
        f'Tilt assessment: triggers={triggers}, hands_since={hands_since_trigger}. '
        f'BB loss={bb_loss:.0f}BB (buy-in={buy_in_bb:.0f}BB). '
        f'Session={session_hours:.1f}h. '
        f'Tilt score={score:.2f} -> level={level}. '
        f'Action: {stop_action}. '
        f'Hard stop-loss={hard_stop}. '
        f'Behavior impact: VPIP+{behavior["vpip_adj"]:.0%}, '
        f'AGGR+{behavior["aggr_adj"]:.0%}, CALL+{behavior["call_adj"]:.0%}.'
    )

    tips = []

    tips.append(
        f'TILT LEVEL: {level.upper()} (score={score:.2f}). '
        f'Action: {stop_action}. '
        f'{"No significant tilt detected -- play normally." if level == "none" else "Mild tilt -- minor leaks; take short break." if level == "mild" else "Moderate tilt -- stop playing; take real break." if level == "moderate" else "Severe tilt -- quit session entirely; protect bankroll."}'
    )

    tips.append(
        f'BEHAVIOR IMPACT: Tilt inflates VPIP+{behavior["vpip_adj"]:.0%}, '
        f'aggression+{behavior["aggr_adj"]:.0%}, calling+{behavior["call_adj"]:.0%}. '
        f'{"At this level, these leaks cost ~{:.0f} BB/100 extra." .format(behavior["vpip_adj"] * 60 + behavior["call_adj"] * 40) if level != "none" else "Behavior within normal range."}'
    )

    if triggers:
        tips.append(
            f'ACTIVE TRIGGERS: {", ".join(triggers)}. '
            f'Hands since trigger={hands_since_trigger}. '
            f'{"Trigger still very fresh -- tilt risk high." if hands_since_trigger < 10 else "Trigger fading -- continue monitoring." if hands_since_trigger < 30 else "Trigger mostly dissipated -- reassess in 10 hands."}'
        )

    if hard_stop:
        tips.append(
            f'HARD STOP-LOSS: Lost {bb_loss:.0f}BB >= {HARD_STOP_LOSS_BUY_INS:.0f} buy-ins ({buy_in_bb:.0f}BB). '
            f'Stop-loss triggered regardless of tilt level. '
            f'Leave the table now; results today cannot be recovered by continuing.'
        )

    if corrections:
        tips.append(
            f'CORRECTIONS: {" | ".join(corrections[:3])}.'
        )

    return TiltManagementResult(
        triggers=triggers,
        hands_since_trigger=hands_since_trigger,
        bb_loss=bb_loss,
        buy_in_bb=buy_in_bb,
        session_hours=session_hours,
        tilt_score=score,
        tilt_level=level,
        stop_action=stop_action,
        hard_stop=hard_stop,
        behavior_changes=behavior,
        corrections=corrections,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tilt_one_liner(r: TiltManagementResult) -> str:
    return (
        f'[TILT score={r.tilt_score:.2f}|{r.tilt_level}] '
        f'action={r.stop_action}'
    )
