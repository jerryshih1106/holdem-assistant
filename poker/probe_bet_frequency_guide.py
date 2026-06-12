"""
Probe Bet Frequency Guide (probe_bet_frequency_guide.py)

Calibrates probe bet frequency when OOP after IP villain checks back the flop.
A probe bet reclaims initiative on the turn after IP showed weakness.

THEORY:
  PROBE BET DEFINITION:
  Hero is OOP (e.g., BB). Villain is IP (e.g., BTN preflop raiser).
  Hero checks the flop. BTN checks back (signals weakness or pot control).
  Hero bets the TURN = probe bet. This captures:
  (1) Fold equity vs air/marginal IP hands (~50% of check-back range)
  (2) Protection for medium-strength hands vs IP free cards
  (3) Range advantage shift: IP check-back uncaps hero's range

  WHY IP CHECKS BACK:
  - Air / missed flop (~40-50% of check range)
  - Pot-controlling medium pair (~20-25%)
  - Slow-playing monster (~5-8%; probe risk)
  - Missed draw / overcards (~20-30%)

  BASELINE PROBE FREQUENCY:
  After IP checks back: OOP should probe ~50-60% of turns.
  Dry board + brick turn: probe ~70% (IP missed; take free pot)
  Wet board + scare turn: probe ~35% (IP may have connected)

  PROBE SIZING:
  Thin value/bluffs: 45-55% pot (efficient; folds out air)
  Strong value: 60-75% pot (extract value from IP pairs/draws)

DISTINCT FROM:
  probe_advisor.py:           When a specific probe is a good idea
  turn_probe_bet_advisor.py:  Turn probe analysis for a specific hand
  river_probe_bet_advisor.py: River probe after flop+turn check-back
  THIS MODULE:                FREQUENCY calibration of probe betting;
                              board/turn card adjustments; sizing guide.
"""

from dataclasses import dataclass, field
from typing import List

BASELINE_PROBE_FREQ_BY_STREET: dict = {
    'turn':  0.55,
    'river': 0.45,
}

BOARD_TEXTURE_PROBE_ADJ: dict = {
    'dry':      +0.10,
    'semi_wet':  0.00,
    'wet':      -0.08,
    'monotone': -0.05,
    'paired':   +0.05,
}

TURN_CARD_PROBE_ADJ: dict = {
    'brick':          +0.12,
    'low':            +0.06,
    'medium':          0.00,
    'high':           -0.06,
    'flush_complete': -0.12,
    'scare_card':     -0.08,
}

VILLAIN_IP_PROBE_MODIFIER: dict = {
    'fish':            -0.08,
    'calling_station': -0.05,
    'nit':             +0.10,
    'lag':             -0.06,
    'rec':             -0.02,
    'reg':              0.00,
}

PROBE_SIZING_BY_TEXTURE: dict = {
    'dry':      0.50,
    'semi_wet': 0.55,
    'wet':      0.65,
    'monotone': 0.60,
    'paired':   0.50,
}


def _optimal_probe_freq(
    street: str,
    board_texture: str,
    turn_card: str,
    villain_type: str,
) -> float:
    base = BASELINE_PROBE_FREQ_BY_STREET.get(street, 0.50)
    board_adj = BOARD_TEXTURE_PROBE_ADJ.get(board_texture, 0.00)
    turn_adj = TURN_CARD_PROBE_ADJ.get(turn_card, 0.00) if street == 'turn' else 0.0
    vil_adj = VILLAIN_IP_PROBE_MODIFIER.get(villain_type, 0.00)
    freq = base + board_adj + turn_adj + vil_adj
    return round(min(0.82, max(0.15, freq)), 3)


def _probe_decision(freq: float, hand_sdv: float, has_draw: bool) -> str:
    if hand_sdv >= 0.70:
        return 'PROBE_VALUE_BET'
    if hand_sdv >= 0.45:
        return 'PROBE_THIN_VALUE' if freq >= 0.55 else 'CHECK_BACK_POT_CONTROL'
    if has_draw:
        return 'PROBE_SEMI_BLUFF'
    if freq >= 0.55 and hand_sdv < 0.25:
        return 'PROBE_BLUFF'
    return 'CHECK_BACK_GIVE_UP'


def _probe_status(actual: float, optimal: float) -> str:
    diff = actual - optimal
    if diff > 0.15:
        return 'OVER_PROBING_SIGNIFICANTLY'
    if diff > 0.08:
        return 'OVER_PROBING_SLIGHTLY'
    if diff < -0.15:
        return 'UNDER_PROBING_SIGNIFICANTLY'
    if diff < -0.08:
        return 'UNDER_PROBING_SLIGHTLY'
    return 'PROBE_FREQUENCY_OK'


@dataclass
class ProbeBetFrequencyResult:
    street: str
    board_texture: str
    turn_card: str
    villain_type: str
    hand_sdv: float
    has_draw: bool
    actual_probe_freq: float

    optimal_probe_freq: float
    probe_decision: str
    probe_status: str
    recommended_sizing: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_probe_bet_frequency(
    street: str = 'turn',
    board_texture: str = 'semi_wet',
    turn_card: str = 'medium',
    villain_type: str = 'reg',
    hand_sdv: float = 0.45,
    has_draw: bool = False,
    actual_probe_freq: float = 0.50,
) -> ProbeBetFrequencyResult:
    """
    Calibrate OOP probe bet frequency after IP checks back.

    Args:
        street:           Street being probed ('turn' or 'river')
        board_texture:    Flop texture ('dry','semi_wet','wet','monotone','paired')
        turn_card:        Turn card type ('brick','low','medium','high','flush_complete','scare_card')
        villain_type:     IP villain type ('fish','nit','lag','reg', etc.)
        hand_sdv:         Hero's hand showdown value (0-1)
        has_draw:         True if hero holds a draw (flush/straight)
        actual_probe_freq: Hero's current probe frequency for calibration

    Returns:
        ProbeBetFrequencyResult
    """
    optimal = _optimal_probe_freq(street, board_texture, turn_card, villain_type)
    decision = _probe_decision(optimal, hand_sdv, has_draw)
    status = _probe_status(actual_probe_freq, optimal)
    sizing = PROBE_SIZING_BY_TEXTURE.get(board_texture, 0.55)

    verdict = (
        f'[PROBE {street}|{board_texture}|{villain_type}] '
        f'optimal={optimal:.0%} actual={actual_probe_freq:.0%} rec={decision}'
    )

    reasoning = (
        f'Probe freq on {street} ({board_texture} board, turn={turn_card}, vs IP {villain_type}): '
        f'base={BASELINE_PROBE_FREQ_BY_STREET.get(street, 0.50):.0%} '
        f'board_adj={BOARD_TEXTURE_PROBE_ADJ.get(board_texture, 0):+.0%} '
        f'turn_adj={TURN_CARD_PROBE_ADJ.get(turn_card, 0) if street == "turn" else 0:+.0%} '
        f'vil_adj={VILLAIN_IP_PROBE_MODIFIER.get(villain_type, 0):+.0%}. '
        f'hand_sdv={hand_sdv:.0%} has_draw={has_draw}. '
        f'Rec={decision} sizing={sizing:.0%}pot. Status={status}.'
    )

    tips = []

    tips.append(
        f'Probe bet OOP on {street} after IP check-back: {optimal:.0%} of range. '
        f'Board={board_texture} turn={turn_card}: IP check-back shows '
        f'{"weakness (missed/air) -- probe freely" if board_texture in ("dry", "paired") else "weakness but some traps exist -- probe value+draws"}. '
        f'Sizing: {sizing:.0%} pot.'
    )

    if 'OVER_PROB' in status:
        tips.append(
            f'OVER-PROBING: {actual_probe_freq:.0%} vs optimal {optimal:.0%}. '
            f'vs {villain_type}: reduce air probes on {board_texture}/{turn_card} boards. '
            f'Check back pure bluffs; probe only value hands and strong draws.'
        )
    elif 'UNDER_PROB' in status:
        tips.append(
            f'UNDER-PROBING: {actual_probe_freq:.0%} vs optimal {optimal:.0%}. '
            f'IP checked back on {board_texture}/{turn_card} -- range is weak. '
            f'Add to probe range: thin value (middle pair+), backdoor draws, air bluffs.'
        )
    else:
        tips.append(
            f'Probe frequency calibrated ({actual_probe_freq:.0%} ~ optimal {optimal:.0%}). '
            f'Continue: value probes, semi-bluffs with draws, balanced air probes. '
            f'vs {villain_type}: {"probe freely -- nit rarely traps" if villain_type == "nit" else "check trapping range -- fish may slowplay" if villain_type in ("fish", "calling_station") else "standard balanced probe range"}.'
        )

    if has_draw:
        tips.append(
            f'Draw in hand -- PROBE_SEMI_BLUFF on {street}. '
            f'Sizing {sizing:.0%} pot: fold equity now + outs if called. '
            f'If called: evaluate river equity; consider check-jam or bet-fold.'
        )

    return ProbeBetFrequencyResult(
        street=street,
        board_texture=board_texture,
        turn_card=turn_card,
        villain_type=villain_type,
        hand_sdv=hand_sdv,
        has_draw=has_draw,
        actual_probe_freq=actual_probe_freq,
        optimal_probe_freq=optimal,
        probe_decision=decision,
        probe_status=status,
        recommended_sizing=sizing,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pbfg_one_liner(r: ProbeBetFrequencyResult) -> str:
    return (
        f'[PROBE {r.street}|{r.board_texture}|{r.villain_type}] '
        f'optimal={r.optimal_probe_freq:.0%} rec={r.probe_decision}'
    )
