"""
Multiway Stack-Off Guide (multiway_stack_off_guide.py)

Determines when to stack off in multiway pots, adjusting SDV thresholds
based on number of opponents, board texture, and position.

THEORY:
  WHY MULTIWAY CHANGES STACK-OFF THRESHOLDS:
  In heads-up pots: top pair good kicker (~SDV 0.65) can stack off.
  In 3-way pots: need two pair+ (~SDV 0.72) because any of 2 opponents may have better.
  In 4-way pots: need strong two pair or better (~SDV 0.78).

  PROBABILITY OF BEING BEHIND:
  Each opponent has independent chance of holding a better hand.
  P(at least one opponent beats you) = 1 - (1-p_single)^n
  Where p_single = probability any one opponent has better hand

  MULTIWAY STACK-OFF SDV THRESHOLDS:
  2 players: 0.65 (top pair GK OK)
  3 players: 0.72 (two pair or better)
  4 players: 0.78 (strong two pair; set preferred)
  5 players: 0.82 (set or better strongly preferred)

  BOARD TEXTURE MODIFIERS:
  Wet board: raise threshold (more likely someone has a strong draw or made hand)
  Dry board: lower threshold (less likely to be behind)
  Monotone: raise threshold (flush draws everywhere)
  Paired: lower threshold (full houses rare; two pair more likely good)

  POSITION IMPACT:
  IP: lower threshold slightly (can see villain action before committing)
  OOP: raise threshold slightly (act before seeing villain response)

DISTINCT FROM:
  stack_off_advisor.py:    General stack-off advice for specific hands
  spr_commitment.py:       SPR-based commitment calculations
  multiway_advisor.py:     General multiway strategy
  THIS MODULE:             SDV THRESHOLDS for going all-in multiway;
                           n_players scaling; board/position adjustments.
"""

from dataclasses import dataclass, field
from typing import List

BASE_STACK_OFF_THRESHOLD_BY_PLAYERS: dict = {
    2: 0.63,
    3: 0.72,
    4: 0.78,
    5: 0.82,
    6: 0.85,
}

BOARD_STACK_OFF_MODIFIER: dict = {
    'dry':      -0.04,
    'semi_wet':  0.00,
    'wet':      +0.05,
    'monotone': +0.06,
    'paired':   -0.02,
}

POSITION_STACK_OFF_MODIFIER: dict = {
    'ip':  -0.02,
    'oop': +0.02,
}

VILLAIN_TYPE_STACK_OFF_MODIFIER: dict = {
    'fish':            -0.03,
    'calling_station': -0.04,
    'nit':             +0.04,
    'lag':             -0.02,
    'reg':              0.00,
}

SPR_COMMIT_THRESHOLD: float = 2.0


def _stack_off_threshold(
    n_players: int,
    board_texture: str,
    position: str,
    villain_type: str,
) -> float:
    base = BASE_STACK_OFF_THRESHOLD_BY_PLAYERS.get(min(n_players, 6), 0.85)
    board_adj = BOARD_STACK_OFF_MODIFIER.get(board_texture, 0.0)
    pos_adj = POSITION_STACK_OFF_MODIFIER.get(position, 0.0)
    vil_adj = VILLAIN_TYPE_STACK_OFF_MODIFIER.get(villain_type, 0.0)
    raw = base + board_adj + pos_adj + vil_adj
    return round(min(0.92, max(0.45, raw)), 3)


def _stack_off_decision(hand_sdv: float, threshold: float, spr: float) -> str:
    if spr <= SPR_COMMIT_THRESHOLD:
        if hand_sdv >= threshold - 0.08:
            return 'COMMIT_LOW_SPR'
        return 'FOLD_COMMITTED_BUT_BEHIND'
    if hand_sdv >= threshold + 0.08:
        return 'STACK_OFF_COMFORTABLY'
    if hand_sdv >= threshold:
        return 'STACK_OFF_MARGINALLY'
    if hand_sdv >= threshold - 0.05:
        return 'BORDERLINE_STACK_OFF'
    return 'FOLD_BELOW_THRESHOLD'


def _p_ahead_estimate(hand_sdv: float, n_players: int) -> float:
    p_beat_one = hand_sdv ** 1.5
    return round(p_beat_one ** (n_players - 1), 3)


@dataclass
class MultiwayStackOffResult:
    n_players: int
    board_texture: str
    position: str
    villain_type: str
    hand_sdv: float
    spr: float

    stack_off_threshold: float
    stack_off_decision: str
    p_ahead_estimate: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_multiway_stack_off(
    n_players: int = 3,
    board_texture: str = 'semi_wet',
    position: str = 'ip',
    villain_type: str = 'reg',
    hand_sdv: float = 0.72,
    spr: float = 4.0,
) -> MultiwayStackOffResult:
    """
    Determine stack-off threshold in multiway pots.

    Args:
        n_players:     Total players in the pot (including hero)
        board_texture: Board texture ('dry','semi_wet','wet','monotone','paired')
        position:      Hero position ('ip' or 'oop')
        villain_type:  Primary villain type (most aggressive/dangerous)
        hand_sdv:      Hero's hand SDV (0-1)
        spr:           Current stack-to-pot ratio

    Returns:
        MultiwayStackOffResult
    """
    threshold = _stack_off_threshold(n_players, board_texture, position, villain_type)
    decision = _stack_off_decision(hand_sdv, threshold, spr)
    p_ahead = _p_ahead_estimate(hand_sdv, n_players)

    verdict = (
        f'[MSO {n_players}way|{board_texture}|{position}|SDV={hand_sdv:.0%}] '
        f'threshold={threshold:.0%} SPR={spr} dec={decision}'
    )

    reasoning = (
        f'Multiway stack-off {n_players} players: '
        f'base_threshold={BASE_STACK_OFF_THRESHOLD_BY_PLAYERS.get(min(n_players, 6), 0.85):.0%} '
        f'board_adj={BOARD_STACK_OFF_MODIFIER.get(board_texture, 0):+.0%} '
        f'pos_adj={POSITION_STACK_OFF_MODIFIER.get(position, 0):+.0%} '
        f'vil_adj={VILLAIN_TYPE_STACK_OFF_MODIFIER.get(villain_type, 0):+.0%}. '
        f'Threshold={threshold:.0%}. Hand SDV={hand_sdv:.0%}. P_ahead~{p_ahead:.0%}. '
        f'SPR={spr}. Decision={decision}.'
    )

    tips = []

    tips.append(
        f'Multiway stack-off ({n_players} players, {board_texture} board): '
        f'threshold SDV={threshold:.0%}. Your SDV={hand_sdv:.0%}. P(ahead)~{p_ahead:.0%}. '
        f'{"Stack off comfortably" if "COMFORTABLY" in decision else "Marginal stack-off; consider villain range" if "MARGINALLY" in decision else "Fold -- below threshold; too many opponents"}.'
    )

    tips.append(
        f'SPR={spr}: {"Low SPR -- pot odds push toward calling off; focus on blockers" if spr <= 2 else "Adequate SPR -- use position and range advantage to control commitment"}. '
        f'P(ahead all opponents)~{p_ahead:.0%} at SDV={hand_sdv:.0%} vs {n_players-1} opponent(s). '
        f'{"Add 5-6% SDV requirement per extra opponent beyond heads-up." if n_players > 2 else "Heads-up: standard SDV threshold applies."}'
    )

    if n_players >= 4:
        tips.append(
            f'{n_players}-WAY POT: Significantly raise stack-off requirements. '
            f'Even two pair can be behind in 4-way pots (opponents can have sets, straights). '
            f'Prefer sets, straights, flushes for committing stacks in {n_players}-way pots.'
        )

    if 'FOLD' in decision and decision != 'FOLD_COMMITTED_BUT_BEHIND':
        tips.append(
            f'SDV={hand_sdv:.0%} below threshold={threshold:.0%} in {n_players}-way pot. '
            f'Fold to stack-off pressure. '
            f'{"IP: can call one more street then fold if action continues" if position == "ip" else "OOP: fold to raise/bet; lack position to control pot size"}.'
        )
    elif 'COMMIT' in decision:
        tips.append(
            f'LOW SPR (={spr}): Committed to pot. '
            f'SDV={hand_sdv:.0%} >= threshold-0.08={threshold-0.08:.0%}: call it off. '
            f'Do not fold in low-SPR spots in {n_players}-way pot -- pot odds override threshold.'
        )

    return MultiwayStackOffResult(
        n_players=n_players,
        board_texture=board_texture,
        position=position,
        villain_type=villain_type,
        hand_sdv=hand_sdv,
        spr=spr,
        stack_off_threshold=threshold,
        stack_off_decision=decision,
        p_ahead_estimate=p_ahead,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def mso_one_liner(r: MultiwayStackOffResult) -> str:
    return (
        f'[MSO {r.n_players}way|{r.board_texture}|SDV={r.hand_sdv:.0%}] '
        f'threshold={r.stack_off_threshold:.0%} {r.stack_off_decision}'
    )
