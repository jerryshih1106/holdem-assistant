"""
River Probe Bet Advisor (river_probe_bet_advisor.py)

When the turn checks through (villain checks back IP, or both check),
the OOP player can PROBE BET on the river to exploit the capped range.

THEORY:
  TURN CHECK-BACK by IP villain means:
  1. Medium-strength showdown value (afraid of check-raise)
  2. Occasional slow-played monster (trap risk)
  3. Marginal hands controlling pot size

  OOP RIVER PROBE:
  - Exploits villain's capped check-back range
  - Value probe: hands that beat villain's medium range
  - Bluff probe: missed draws with good blockers
  - Check: strong showdown value (go to showdown)

  SIZING: 45-65% pot -- villain range is capped so large bets just fold everything

  PROBE EV:
  fold_pct x pot + call_pct x (equity x total_pot - probe_bet)

DISTINCT FROM:
  probe_advisor.py:           General probe bets
  turn_probe_bet_advisor.py:  Turn probe specifically
  river_advisor.py:           General river play
  THIS MODULE:                RIVER PROBE after check-back; villain-type
                              adjusted sizing; capped-range exploitation.
"""

from dataclasses import dataclass, field
from typing import List


VILLAIN_CHECKBACK_RANGE: dict = {
    'fish':   {'medium_value': 0.50, 'strong_value': 0.10, 'weak': 0.40},
    'rec':    {'medium_value': 0.45, 'strong_value': 0.10, 'weak': 0.45},
    'nit':    {'medium_value': 0.55, 'strong_value': 0.20, 'weak': 0.25},
    'lag':    {'medium_value': 0.35, 'strong_value': 0.08, 'weak': 0.57},
    'reg':    {'medium_value': 0.40, 'strong_value': 0.07, 'weak': 0.53},
}

VILLAIN_FOLD_TO_PROBE: dict = {
    'fish':   {0.40: 0.45, 0.55: 0.52, 0.75: 0.60},
    'rec':    {0.40: 0.40, 0.55: 0.50, 0.75: 0.58},
    'nit':    {0.40: 0.30, 0.55: 0.42, 0.75: 0.55},
    'lag':    {0.40: 0.32, 0.55: 0.40, 0.75: 0.50},
    'reg':    {0.40: 0.35, 0.55: 0.45, 0.75: 0.55},
}

SCARE_CARD_FOLD_BOOST: dict = {
    'blank':              0.00,
    'overcard':           0.05,
    'flush_completes':    0.08,
    'straight_completes': 0.10,
    'board_pairs':       -0.05,
}


def _optimal_probe_size(villain_type: str, hand_strength: str, river_card: str) -> float:
    """Return optimal probe size as fraction of pot."""
    if hand_strength in ('strong_value', 'nuts'):
        base = 0.65
    elif hand_strength in ('thin_value', 'top_pair'):
        base = 0.55
    elif hand_strength in ('bluff', 'air', 'missed_draw'):
        base = 0.55
    else:
        base = 0.45

    if river_card == 'flush_completes':
        base = min(0.75, base + 0.10)
    elif river_card == 'board_pairs':
        base = max(0.40, base - 0.10)

    if villain_type == 'lag':
        base = min(0.75, base + 0.05)
    elif villain_type == 'nit':
        base = max(0.40, base - 0.05)

    return round(base, 2)


def _probe_fold_pct(villain_type: str, probe_frac: float, river_card: str) -> float:
    """Estimate villain fold% to probe."""
    fold_table = VILLAIN_FOLD_TO_PROBE.get(villain_type, VILLAIN_FOLD_TO_PROBE['rec'])
    closest = min(fold_table.keys(), key=lambda s: abs(s - probe_frac))
    fold = fold_table[closest]
    boost = SCARE_CARD_FOLD_BOOST.get(river_card, 0.0)
    return round(min(0.90, max(0.10, fold + boost)), 3)


def _probe_ev(pot_bb: float, probe_bb: float, fold_pct: float, hero_equity: float) -> float:
    fold_ev = fold_pct * pot_bb
    call_pct = 1.0 - fold_pct
    call_ev = call_pct * (hero_equity * (pot_bb + 2.0 * probe_bb) - probe_bb)
    return round(fold_ev + call_ev, 2)


def _probe_recommendation(
    hand_strength: str,
    probe_ev: float,
    villain_type: str,
    hero_sdv: float,
    fold_pct: float,
) -> str:
    if hand_strength in ('nuts', 'strong_value'):
        return 'PROBE_VALUE'
    if hand_strength in ('thin_value', 'top_pair') and probe_ev > 0:
        return 'PROBE_THIN_VALUE'
    if hand_strength in ('bluff', 'air', 'missed_draw'):
        if fold_pct >= 0.45:
            return 'PROBE_BLUFF'
        return 'CHECK_SHOWDOWN'
    if hero_sdv >= 0.65:
        return 'CHECK_SHOWDOWN'
    if probe_ev > 0:
        return 'PROBE_VALUE'
    return 'CHECK_SHOWDOWN'


def _probe_score(probe_ev: float, fold_pct: float, hand_strength: str) -> int:
    score = 5
    if probe_ev > 3.0:
        score += 2
    elif probe_ev > 1.0:
        score += 1
    elif probe_ev < 0:
        score -= 2
    if fold_pct >= 0.55:
        score += 1
    elif fold_pct < 0.35:
        score -= 1
    if hand_strength in ('nuts', 'strong_value'):
        score += 1
    elif hand_strength == 'air':
        score -= 1
    return max(1, min(10, score))


@dataclass
class RiverProbeResult:
    villain_type: str
    hand_strength: str
    river_card: str

    probe_size_frac: float
    probe_size_bb: float
    fold_pct: float
    probe_ev_bb: float

    probe_score: int
    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_river_probe(
    villain_type: str = 'rec',
    hand_strength: str = 'thin_value',
    river_card: str = 'blank',
    pot_bb: float = 20.0,
    hero_equity_if_called: float = 0.35,
    hero_sdv: float = 0.55,
    checked_street: str = 'turn',
) -> RiverProbeResult:
    """
    Analyze river probe bet when villain checked back the previous street.

    Args:
        villain_type:           Villain profile ('fish','rec','nit','lag','reg')
        hand_strength:          Hero hand ('nuts','strong_value','thin_value',
                                'top_pair','medium_value','bluff','air','missed_draw')
        river_card:             River card type ('blank','overcard','flush_completes',
                                'straight_completes','board_pairs')
        pot_bb:                 Pot in BB before probe
        hero_equity_if_called:  Showdown equity when probe is called
        hero_sdv:               Fraction of villain check-back range hero beats unimproved
        checked_street:         Which street villain checked back ('turn'/'flop')

    Returns:
        RiverProbeResult
    """
    probe_frac = _optimal_probe_size(villain_type, hand_strength, river_card)
    probe_bb = round(pot_bb * probe_frac, 1)
    fold_pct = _probe_fold_pct(villain_type, probe_frac, river_card)
    ev = _probe_ev(pot_bb, probe_bb, fold_pct, hero_equity_if_called)
    action = _probe_recommendation(hand_strength, ev, villain_type, hero_sdv, fold_pct)
    score = _probe_score(ev, fold_pct, hand_strength)

    villain_range = VILLAIN_CHECKBACK_RANGE.get(villain_type, VILLAIN_CHECKBACK_RANGE['rec'])
    trap_pct = villain_range.get('strong_value', 0.10)

    verdict = (
        f'[RPB {hand_strength}|{river_card}|{villain_type}] '
        f'{action} {probe_frac:.0%}pot={probe_bb:.1f}BB '
        f'score={score}/10 EV={ev:+.1f}BB fold={fold_pct:.0%}'
    )

    reasoning = (
        f'River probe vs {villain_type} (checked {checked_street}). '
        f'Villain check-back: {villain_range.get("medium_value",0):.0%} medium, '
        f'{trap_pct:.0%} strong (trap), {villain_range.get("weak",0):.0%} weak. '
        f'Probe {probe_frac:.0%}pot = {probe_bb:.1f}BB. '
        f'Fold pct: {fold_pct:.0%}. EV: {ev:+.1f}BB. Action: {action}.'
    )

    tips = []

    tips.append(
        f'PROBE SIZING: {probe_frac:.0%} pot ({probe_bb:.1f}BB). '
        f'Villain checked back = capped range. '
        f'Keep probe 45-65% pot; larger bets just fold all worse hands.'
    )

    if trap_pct >= 0.12:
        tips.append(
            f'TRAP RISK: {villain_type.upper()} checks back strong hands {trap_pct:.0%}. '
            f'If villain raises probe, they likely have the trap hand; fold bluffs immediately.'
        )

    if action == 'CHECK_SHOWDOWN':
        tips.append(
            f'CHECK SHOWDOWN: SDV={hero_sdv:.0%} with {hand_strength}. '
            f'Villain check-back range has much air/medium; go to showdown and win quietly.'
        )
    elif action in ('PROBE_VALUE', 'PROBE_THIN_VALUE'):
        tips.append(
            f'VALUE PROBE: {hand_strength} beats {villain_type} check-back range. '
            f'Bet {probe_frac:.0%} pot to extract value from medium-strength hands. '
            f'EV={ev:+.1f}BB over checking.'
        )
    elif action == 'PROBE_BLUFF':
        tips.append(
            f'PROBE BLUFF: Villain capped range folds {fold_pct:.0%}. '
            f'Use missed draws / hands with blockers to villain calling range. '
            f'EV={ev:+.1f}BB.'
        )

    if river_card == 'flush_completes':
        tips.append(
            f'FLUSH CARD: Probe represents the flush strongly. '
            f'Villain checked back many flushdraws on turn; this card folds his non-made hands. '
            f'Probe size increased; villain needs flush or strong made hand to call.'
        )
    elif river_card == 'board_pairs':
        tips.append(
            f'BOARD PAIRS: Villain may have checked back trips. '
            f'Probe size reduced; villain calling range widens on paired boards. '
            f'Bluff probes less profitable when board pairs.'
        )

    return RiverProbeResult(
        villain_type=villain_type,
        hand_strength=hand_strength,
        river_card=river_card,
        probe_size_frac=probe_frac,
        probe_size_bb=probe_bb,
        fold_pct=fold_pct,
        probe_ev_bb=ev,
        probe_score=score,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rpb_one_liner(r: RiverProbeResult) -> str:
    return (
        f'[RPB {r.hand_strength}|{r.river_card}|{r.villain_type}] '
        f'{r.recommended_action} {r.probe_size_frac:.0%}pot={r.probe_size_bb:.1f}BB '
        f'score={r.probe_score}/10 EV={r.probe_ev_bb:+.1f}BB'
    )
