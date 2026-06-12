"""
Cold Call Frequency Guide (cold_call_frequency_guide.py)

Calibrates preflop cold-call (flat) frequency by position, villain type,
squeeze risk, and stack depth. Determines when to flat vs 3-bet vs fold.

THEORY:
  COLD-CALL vs 3-BET vs FOLD:
  Cold-calling has highest EV when:
  1. Hero is IP with implied-odds hand (small pairs, suited connectors)
  2. Multiway pot improves hand equity (sets, flushes)
  3. Hand lacks 3-bet value but beats villain's calling range
  4. Pot control is preferred (medium-strength holdings)

  BASELINE COLD-CALL FREQ (vs single raiser, no squeeze threat):
  BTN vs CO: 15-18% (best position; wide flat range acceptable)
  CO  vs MP: 10-13%
  HJ  vs MP: 7-9%
  SB:         2-4%  (OOP; mostly 3-bet or fold)

  FLAT vs 3-BET DECISION:
  Prefer 3-bet: hand SDV >= 0.75 (strong value, deny equity)
  Mixed flat/3-bet: SDV 0.55-0.75 (mid-strength; position-dependent)
  Prefer flat: SDV 0.30-0.55 (implied odds, playability)
  Fold: SDV < 0.30 (insufficient equity vs range)

  SQUEEZE RISK:
  Each squeeze-threat player behind reduces flat freq significantly.
  With 2+ squeezers: only flat nutted holdings or fold/3-bet.

DISTINCT FROM:
  cold_call.py:                   General cold-call EV analysis
  cold_call_defense_optimizer.py: Defending against cold-callers
  THIS MODULE:                    HOW OFTEN to cold-call (freq calibration);
                                  flat vs 3-bet decision; squeeze awareness.
"""

from dataclasses import dataclass, field
from typing import List

BASELINE_COLD_CALL_FREQ: dict = {
    'btn': 0.17,
    'co':  0.12,
    'hj':  0.08,
    'mp':  0.07,
    'utg': 0.04,
    'sb':  0.03,
}

VILLAIN_OPEN_COLD_CALL_MODIFIER: dict = {
    'fish':            +0.05,
    'calling_station': +0.03,
    'nit':             -0.04,
    'lag':             -0.02,
    'rec':             +0.02,
    'reg':              0.00,
}

SQUEEZE_RISK_PER_PLAYER: float = -0.04

STACK_DEPTH_COLD_CALL: dict = {
    'deep':    +0.04,
    'medium':   0.00,
    'shallow': -0.03,
    'short':   -0.06,
}

THREE_BET_PREFERENCE_THRESHOLD: float = 0.75
FLAT_PREFERENCE_THRESHOLD: float = 0.30


def _stack_depth_cat(stack_bb: float) -> str:
    if stack_bb > 80:
        return 'deep'
    if stack_bb > 40:
        return 'medium'
    if stack_bb > 20:
        return 'shallow'
    return 'short'


def _optimal_cold_call_freq(
    position: str,
    villain_type: str,
    squeezers_behind: int,
    stack_bb: float,
) -> float:
    base = BASELINE_COLD_CALL_FREQ.get(position, 0.07)
    vil_mod = VILLAIN_OPEN_COLD_CALL_MODIFIER.get(villain_type, 0.00)
    squeeze_adj = squeezers_behind * SQUEEZE_RISK_PER_PLAYER
    depth_cat = _stack_depth_cat(stack_bb)
    depth_adj = STACK_DEPTH_COLD_CALL.get(depth_cat, 0.00)
    freq = base + vil_mod + squeeze_adj + depth_adj
    return round(min(0.30, max(0.01, freq)), 3)


def _flat_or_3bet(hand_sdv: float) -> str:
    if hand_sdv >= THREE_BET_PREFERENCE_THRESHOLD:
        return '3BET_PREFERRED'
    if hand_sdv >= 0.55:
        return 'FLAT_OR_3BET_MIXED'
    if hand_sdv >= FLAT_PREFERENCE_THRESHOLD:
        return 'FLAT_PREFERRED'
    return 'FOLD_PREFERRED'


def _cold_call_status(actual: float, optimal: float) -> str:
    diff = actual - optimal
    if diff > 0.06:
        return 'OVER_FLATTING_SIGNIFICANTLY'
    if diff > 0.03:
        return 'OVER_FLATTING_SLIGHTLY'
    if diff < -0.06:
        return 'UNDER_FLATTING_SIGNIFICANTLY'
    if diff < -0.03:
        return 'UNDER_FLATTING_SLIGHTLY'
    return 'COLD_CALL_FREQ_OK'


@dataclass
class ColdCallFrequencyResult:
    position: str
    villain_type: str
    squeezers_behind: int
    stack_bb: float
    hand_sdv: float
    actual_cold_call_freq: float

    optimal_cold_call_freq: float
    depth_category: str
    flat_or_3bet_rec: str
    cold_call_status: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_cold_call_frequency(
    position: str = 'btn',
    villain_type: str = 'reg',
    squeezers_behind: int = 0,
    stack_bb: float = 100.0,
    hand_sdv: float = 0.50,
    actual_cold_call_freq: float = 0.15,
) -> ColdCallFrequencyResult:
    """
    Calibrate preflop cold-call (flat) frequency.

    Args:
        position:              Hero's position ('btn','co','hj','mp','utg','sb')
        villain_type:          Villain type ('fish','nit','lag','reg', etc.)
        squeezers_behind:      Number of players behind who might squeeze
        stack_bb:              Effective stack in BB
        hand_sdv:              Hero's hand showdown value (0-1); guides flat vs 3-bet
        actual_cold_call_freq: Hero's current cold-call freq for calibration

    Returns:
        ColdCallFrequencyResult
    """
    optimal = _optimal_cold_call_freq(position, villain_type, squeezers_behind, stack_bb)
    depth_cat = _stack_depth_cat(stack_bb)
    f_3b_rec = _flat_or_3bet(hand_sdv)
    status = _cold_call_status(actual_cold_call_freq, optimal)

    verdict = (
        f'[CCF {position}|{villain_type}|sdv={hand_sdv:.0%}] '
        f'optimal={optimal:.0%} actual={actual_cold_call_freq:.0%} rec={f_3b_rec}'
    )

    reasoning = (
        f'Cold-call freq from {position} vs {villain_type}: '
        f'base={BASELINE_COLD_CALL_FREQ.get(position, 0.07):.0%} '
        f'vil_adj={VILLAIN_OPEN_COLD_CALL_MODIFIER.get(villain_type, 0):+.0%} '
        f'squeeze={squeezers_behind}x={squeezers_behind * SQUEEZE_RISK_PER_PLAYER:+.0%} '
        f'depth({depth_cat}). '
        f'hand_sdv={hand_sdv:.0%} -> {f_3b_rec}. '
        f'Optimal flat freq={optimal:.0%}. Status={status}.'
    )

    tips = []

    tips.append(
        f'Cold-call freq from {position} vs {villain_type}: {optimal:.0%}. '
        f'Hand SDV={hand_sdv:.0%}: {f_3b_rec}. '
        f'{"Prefer 3-bet: deny equity + value." if f_3b_rec == "3BET_PREFERRED" else "Flat: implied odds, pot control." if f_3b_rec == "FLAT_PREFERRED" else "Mixed: 3-bet some, flat rest."}'
    )

    if squeezers_behind > 0:
        tips.append(
            f'SQUEEZE RISK: {squeezers_behind} player(s) behind may squeeze. '
            f'Tighten flat range to nutted hands (TT+, AQs+, suited connectors). '
            f'Marginal flats (pocket pairs <88, weak suited) become fold-or-3bet.'
        )

    if 'OVER_FLAT' in status:
        tips.append(
            f'OVER-FLATTING: {actual_cold_call_freq:.0%} vs optimal {optimal:.0%}. '
            f'Convert top flatting hands to 3-bets (JJ+/AQs+). '
            f'Drop bottom flatting range (offsuit 1-gappers, weak suited hands OOP).'
        )
    elif 'UNDER_FLAT' in status:
        tips.append(
            f'UNDER-FLATTING: {actual_cold_call_freq:.0%} vs optimal {optimal:.0%}. '
            f'Add to flat range: suited connectors (87s, 76s), small pairs (22-55), suited Ax. '
            f'These play better as flats (implied odds) than 3-bets.'
        )
    else:
        tips.append(
            f'Cold-call freq calibrated ({actual_cold_call_freq:.0%} ~ optimal {optimal:.0%}). '
            f'Stack={stack_bb:.0f}BB ({depth_cat}): '
            f'{"flat pairs/connectors for implied odds" if depth_cat == "deep" else "shallow -- prefer 3-bet or fold"}. '
            f'vs {villain_type}: {"fish/rec = wide flat range; postflop edge" if villain_type in ("fish", "rec") else "nit = tight flat; strong implied odds only"}.'
        )

    return ColdCallFrequencyResult(
        position=position,
        villain_type=villain_type,
        squeezers_behind=squeezers_behind,
        stack_bb=stack_bb,
        hand_sdv=hand_sdv,
        actual_cold_call_freq=actual_cold_call_freq,
        optimal_cold_call_freq=optimal,
        depth_category=depth_cat,
        flat_or_3bet_rec=f_3b_rec,
        cold_call_status=status,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ccf_one_liner(r: ColdCallFrequencyResult) -> str:
    return (
        f'[CCF {r.position}|{r.villain_type}] '
        f'optimal={r.optimal_cold_call_freq:.0%} rec={r.flat_or_3bet_rec}'
    )
