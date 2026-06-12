"""
Session Opening Strategy (session_opening_strategy.py)

The first 30-60 minutes of a poker session are different from mid-session.
You have no reads, no image, and opponents haven't categorized you yet.
This module guides the optimal "opening phase" strategy.

THEORY:
  WHY FIRST 30-60 MINUTES ARE DIFFERENT:
  1. NO READS: You don't know villain tendencies yet
  2. NO IMAGE: Opponents don't know your style -- can't exploit it
  3. VARIANCE CONTROL: First impression matters; avoid early bust-out risk
  4. OBSERVATION MODE: Collecting data is as valuable as winning chips

  PHASE 1 (Hands 1-20: OBSERVATION PHASE):
  - Play TAG (Tight-Aggressive) preflop
  - Watch: who limps, who 3-bets, who calls too wide, who is fish
  - Reduce bluff frequency (no reads = cannot assess fold equity)
  - Focus on value betting made hands
  - Primary goal: Gather reads while protecting bankroll

  PHASE 2 (Hands 21-60: CALIBRATION PHASE):
  - Start using reads gathered in Phase 1
  - Adjust to specific villains (loosen vs fish, tighten vs LAGs)
  - Begin mixing in exploitative plays
  - Secondary goal: Establish image while playing solid poker

  PHASE 3 (Hands 61+: EXPLOIT PHASE):
  - Full strategic repertoire available
  - Exploit identified weaknesses aggressively
  - Use table image built in Phases 1-2
  - Bluff frequency normalized; all strategies available

  SEAT SELECTION PRIORITY:
  Priority order for seat selection:
  1. Left of the fish (act after fish preflop and postflop)
  2. Left of the most aggressive player (act after them; can 3-bet)
  3. Right of tight players (steal their blinds freely)

  STACK MANAGEMENT ON SESSION OPEN:
  - Buy in for max (full stack maximizes implied odds)
  - Never short-buy at session open (except short-stack specialist strategy)
  - After winning a big pot: continue, advantage is now significant
  - After losing 50% in Phase 1: consider leaving (bad table, bad day)

  COMMON OPENING PHASE MISTAKES:
  1. Bluffing too early before reads (no fold equity estimate)
  2. Playing too many speculative hands (no implied odds data yet)
  3. Hero calling with marginal hands (no idea if villain is bluffing)
  4. Overplaying medium-strength hands (ranges still unknown)

DISTINCT FROM:
  session_tracker.py:     Session EV tracking
  session_coach.py:       General session coaching
  session_game_plan.py:   Session game plan
  THIS MODULE:            OPENING PHASE SPECIFIC; phase-based progression;
                          observation goals; seat selection; early-session preflop adjustments.
"""

from dataclasses import dataclass, field
from typing import List


PHASE_THRESHOLDS: dict = {
    'observation':   (0, 20),
    'calibration':   (21, 60),
    'exploitation':  (61, 999),
}

PHASE_OPEN_RANGE_ADJUST: dict = {
    'observation':  -0.06,
    'calibration':  -0.02,
    'exploitation':  0.00,
}

PHASE_BLUFF_ADJUST: dict = {
    'observation':  -0.15,
    'calibration':  -0.07,
    'exploitation':  0.00,
}

PHASE_STEAL_ADJUST: dict = {
    'observation':  -0.05,
    'calibration':  -0.02,
    'exploitation':  0.00,
}

PHASE_THIN_VALUE_ADJUST: dict = {
    'observation':  -0.10,
    'calibration':  -0.05,
    'exploitation':  0.00,
}

OBSERVATION_PRIORITIES: List[str] = [
    'identify_fish_players',
    'note_preflop_3bet_frequency',
    'track_cbet_patterns',
    'observe_fold_to_cbet',
    'identify_aggressive_players',
    'note_showdown_hand_strengths',
]


def _current_phase(hands_played: int) -> str:
    for phase, (lo, hi) in PHASE_THRESHOLDS.items():
        if lo <= hands_played <= hi:
            return phase
    return 'exploitation'


def _session_health(profit_bb: float, buy_in_bb: float) -> str:
    ratio = profit_bb / buy_in_bb if buy_in_bb > 0 else 0
    if ratio >= 0.50:
        return 'strong_session'
    elif ratio >= 0.10:
        return 'positive_session'
    elif ratio >= -0.25:
        return 'neutral_session'
    elif ratio >= -0.50:
        return 'losing_session'
    return 'bad_session'


def _seat_priority(
    fish_position: int,
    aggressor_position: int,
    hero_position: int,
    n_seats: int,
) -> str:
    left_of_fish = (fish_position + 1) % n_seats
    left_of_aggressor = (aggressor_position + 1) % n_seats
    if hero_position == left_of_fish:
        return 'OPTIMAL_LEFT_OF_FISH'
    if hero_position == left_of_aggressor:
        return 'GOOD_LEFT_OF_AGGRESSOR'
    if (fish_position - hero_position) % n_seats <= 2:
        return 'DECENT_NEAR_FISH'
    return 'SUBOPTIMAL_CONSIDER_CHANGE'


@dataclass
class SessionOpeningResult:
    hands_played: int
    phase: str

    open_range_adj: float
    bluff_freq_adj: float
    steal_freq_adj: float
    thin_value_adj: float

    session_health: str
    profit_bb: float

    observation_goals: List[str]
    seat_quality: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_session_opening(
    hands_played: int = 10,
    profit_bb: float = 0.0,
    buy_in_bb: float = 100.0,
    fish_position: int = 3,
    aggressor_position: int = 5,
    hero_position: int = 4,
    n_seats: int = 6,
) -> SessionOpeningResult:
    """
    Provide session opening phase strategy guidance.

    Args:
        hands_played:       Number of hands played this session
        profit_bb:          Session profit in BB (negative = loss)
        buy_in_bb:          Buy-in amount in BB
        fish_position:      Seat number of identified fish (0-based)
        aggressor_position: Seat number of most aggressive player
        hero_position:      Hero's seat number
        n_seats:            Total seats at table

    Returns:
        SessionOpeningResult
    """
    phase = _current_phase(hands_played)
    health = _session_health(profit_bb, buy_in_bb)
    seat_q = _seat_priority(fish_position, aggressor_position, hero_position, n_seats)

    open_adj  = PHASE_OPEN_RANGE_ADJUST[phase]
    bluff_adj = PHASE_BLUFF_ADJUST[phase]
    steal_adj = PHASE_STEAL_ADJUST[phase]
    thin_adj  = PHASE_THIN_VALUE_ADJUST[phase]

    phase_num = {'observation': 1, 'calibration': 2, 'exploitation': 3}[phase]

    verdict = (
        f'[SOS phase={phase_num}|hand={hands_played}|{health}] '
        f'bluff={bluff_adj:+.0%} open={open_adj:+.0%} '
        f'seat={seat_q}'
    )

    reasoning = (
        f'Session opening: Phase {phase_num} ({phase}), hand {hands_played}. '
        f'Health={health}, profit={profit_bb:+.0f}BB/{buy_in_bb:.0f}BB. '
        f'Adjustments: open={open_adj:+.0%} bluff={bluff_adj:+.0%} '
        f'steal={steal_adj:+.0%} thin_value={thin_adj:+.0%}. '
        f'Seat quality: {seat_q}.'
    )

    obs_goals = OBSERVATION_PRIORITIES[:4] if phase == 'observation' else OBSERVATION_PRIORITIES[:2]

    tips = []

    phase_descriptions = {
        'observation': 'OBSERVATION PHASE (hands 1-20): Gather reads; play tight; avoid bluffs.',
        'calibration': 'CALIBRATION PHASE (hands 21-60): Apply reads; adjust per villain; moderate exploits.',
        'exploitation': 'EXPLOITATION PHASE (61+): Full strategy; exploit identified weaknesses.',
    }
    tips.append(
        f'{phase_descriptions[phase]} '
        f'Adjustments: open={open_adj:+.0%} bluff={bluff_adj:+.0%} steal={steal_adj:+.0%}.'
    )

    tips.append(
        f'OBSERVATION GOALS: {"; ".join(obs_goals[:3])}. '
        f'{"Priority: identify fish -- highest EV target." if "identify_fish_players" in obs_goals else "Focus on range estimation for remaining players."}'
    )

    if health in ('losing_session', 'bad_session'):
        tips.append(
            f'SESSION HEALTH: {health.upper()}. Profit={profit_bb:+.0f}BB. '
            f'{"Consider leaving -- may be bad table." if health == "bad_session" else "Take a short break; regroup strategy."} '
            f'Do not tilt-call or hero-bluff to recover losses.'
        )
    elif health == 'strong_session':
        tips.append(
            f'STRONG SESSION: Profit={profit_bb:+.0f}BB. '
            f'Continue; consider buying more chips if at max buy-in table. '
            f'Opponents are losing -- loosen up slightly for maximum exploitation.'
        )

    tips.append(
        f'SEAT QUALITY: {seat_q}. '
        f'{"Ideal -- act after fish in most pots." if "OPTIMAL" in seat_q else "Consider requesting seat change to left of fish for maximum EV." if "SUBOPTIMAL" in seat_q else "Decent position -- OK to stay."}'
    )

    return SessionOpeningResult(
        hands_played=hands_played,
        phase=phase,
        open_range_adj=open_adj,
        bluff_freq_adj=bluff_adj,
        steal_freq_adj=steal_adj,
        thin_value_adj=thin_adj,
        session_health=health,
        profit_bb=profit_bb,
        observation_goals=obs_goals,
        seat_quality=seat_q,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sos_one_liner(r: SessionOpeningResult) -> str:
    phase_num = {'observation': 1, 'calibration': 2, 'exploitation': 3}[r.phase]
    return (
        f'[SOS phase={phase_num}|hand={r.hands_played}] '
        f'bluff={r.bluff_freq_adj:+.0%} open={r.open_range_adj:+.0%} '
        f'{r.session_health}'
    )
