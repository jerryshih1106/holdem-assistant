"""
Cold Call Squeeze Protection Advisor (cold_call_squeeze_protection.py)

When cold calling a raise, players still to act behind may SQUEEZE (3-bet over the
open+cold-call), forcing you to fold your investment as dead money.

THEORY:
  SQUEEZE RISK = probability any player behind 3-bets over open + cold call.

  Cold caller signals a medium hand (not strong enough to 3-bet), giving players
  behind an incentive to squeeze for dead money and isolation.

  SQUEEZE PROBABILITY per player (combined via complement):
  - LAG:   ~20%  (high frequency squeezer)
  - REG:   ~11%  (balanced; squeezes value + some bluffs)
  - REC:    ~7%  (squeezes mainly strong hands)
  - NIT:    ~3%  (only premiums)
  - FISH:   ~8%  (unpredictable)

  Combined squeeze_pct = 1 - product(1 - per_player_prob)

  EV OF COLD CALL WITH SQUEEZE RISK:
  ev = (1 - squeeze_pct) * postflop_ev - squeeze_pct * cold_call_bb

  DEFENSE OPTIONS:
  1. 3-BET ISOLATE: Removes squeeze risk; takes dead money; builds pot with initiative
  2. FOLD: Avoid dead money when squeeze risk + hand are too weak
  3. COLD CALL ANYWAY: When EV positive and hand plays well postflop

DISTINCT FROM:
  squeeze_play_advisor.py:    Hero is the squeezer
  preflop_3bet_defense.py:    Defending vs 3-bet
  cold_call.py:               General cold call decisions
  THIS MODULE:                SQUEEZE RISK to the cold caller; EV accounting for
                              dead money risk; 3-bet vs cold call vs fold analysis.
"""

from dataclasses import dataclass, field
from typing import List


SQUEEZE_PROB_PER_PLAYER: dict = {
    'lag':   0.20,
    'reg':   0.11,
    'rec':   0.07,
    'nit':   0.03,
    'fish':  0.08,
}

POSTFLOP_EV_FACTOR: dict = {
    'premium':      0.30,
    'strong':       0.20,
    'speculative':  0.15,
    'marginal':     0.05,
    'weak':        -0.05,
}


def _combined_squeeze_pct(player_types_behind: list) -> float:
    """Combined probability at least one player behind squeezes."""
    no_squeeze = 1.0
    for pt in player_types_behind:
        prob = SQUEEZE_PROB_PER_PLAYER.get(pt, 0.07)
        no_squeeze *= (1.0 - prob)
    return round(1.0 - no_squeeze, 3)


def _cold_call_ev(
    cold_call_bb: float,
    pot_bb_if_reaches_flop: float,
    hand_strength: str,
    squeeze_pct: float,
) -> float:
    postflop_factor = POSTFLOP_EV_FACTOR.get(hand_strength, 0.10)
    postflop_ev = postflop_factor * pot_bb_if_reaches_flop
    return round((1.0 - squeeze_pct) * postflop_ev - squeeze_pct * cold_call_bb, 2)


def _squeeze_risk_level(squeeze_pct: float) -> str:
    if squeeze_pct >= 0.35:
        return 'high'
    elif squeeze_pct >= 0.18:
        return 'medium'
    elif squeeze_pct >= 0.08:
        return 'low'
    return 'minimal'


def _recommended_action(
    squeeze_pct: float,
    ev: float,
    hand_strength: str,
    can_3bet: bool,
) -> str:
    if hand_strength == 'premium' and can_3bet:
        return '3BET_ISOLATE'
    if squeeze_pct >= 0.30 and hand_strength in ('marginal', 'weak'):
        return 'FOLD_SQUEEZE_RISK'
    if squeeze_pct >= 0.25 and hand_strength == 'speculative' and can_3bet:
        return '3BET_OR_FOLD'
    if ev > 0:
        return 'COLD_CALL'
    if can_3bet and hand_strength in ('strong', 'premium'):
        return '3BET_VALUE'
    return 'FOLD'


@dataclass
class ColdCallSqueezeResult:
    hand_strength: str
    player_types_behind: list
    cold_call_bb: float

    squeeze_pct: float
    squeeze_risk_level: str
    cold_call_ev_bb: float

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_cold_call_squeeze(
    hand_strength: str = 'speculative',
    player_types_behind: list = None,
    cold_call_bb: float = 3.0,
    pot_bb_if_reaches_flop: float = 9.0,
    can_3bet: bool = True,
    position: str = 'btn',
) -> ColdCallSqueezeResult:
    """
    Analyze squeeze risk when considering a cold call.

    Args:
        hand_strength:              Hand category ('premium','strong','speculative',
                                    'marginal','weak')
        player_types_behind:        Player types still to act (e.g. ['lag','rec'])
        cold_call_bb:               Cold call size in BB
        pot_bb_if_reaches_flop:     Expected pot if action reaches the flop
        can_3bet:                   True if hero can 3-bet with this hand/stack
        position:                   Hero position ('btn','co','mp','ep')

    Returns:
        ColdCallSqueezeResult
    """
    if player_types_behind is None:
        player_types_behind = ['rec']

    squeeze_pct = _combined_squeeze_pct(player_types_behind)
    risk_level = _squeeze_risk_level(squeeze_pct)
    ev = _cold_call_ev(cold_call_bb, pot_bb_if_reaches_flop, hand_strength, squeeze_pct)
    action = _recommended_action(squeeze_pct, ev, hand_strength, can_3bet)

    n_behind = len(player_types_behind)
    types_str = '+'.join(player_types_behind)

    verdict = (
        f'[CCS {hand_strength}|{n_behind}behind({types_str})] '
        f'{action} squeeze={squeeze_pct:.0%} [{risk_level}] EV={ev:+.1f}BB'
    )

    reasoning = (
        f'Cold call squeeze: {hand_strength}, {n_behind} player(s) behind ({types_str}). '
        f'Combined squeeze risk: {squeeze_pct:.0%} [{risk_level}]. '
        f'Cold call EV: {ev:+.1f}BB. Action: {action}.'
    )

    tips = []

    tips.append(
        f'SQUEEZE RISK: {squeeze_pct:.0%} -- {risk_level.upper()} risk. '
        f'{n_behind} player(s) behind: {types_str}. '
        f'If squeezed, {cold_call_bb:.0f}BB investment lost as dead money.'
    )

    tips.append(
        f'COLD CALL EV: {ev:+.1f}BB including {squeeze_pct:.0%} squeeze discount. '
        f'{"Positive EV -- viable if no better option." if ev > 0 else "Negative EV -- squeeze risk makes cold call unprofitable."}'
    )

    if action in ('3BET_ISOLATE', '3BET_VALUE'):
        tips.append(
            f'3-BET TO ISOLATE: {hand_strength} + squeeze risk = 3-bet preferred. '
            f'3-bet removes squeeze threat, builds pot, takes initiative. '
            f'Players behind cannot squeeze after your 3-bet.'
        )
    elif action == 'FOLD_SQUEEZE_RISK':
        tips.append(
            f'FOLD: {squeeze_pct:.0%} squeeze risk with {hand_strength} = cold call -EV. '
            f'Losing {cold_call_bb:.0f}BB as dead money {squeeze_pct:.0%} of the time is too costly. '
            f'Wait for cleaner spot.'
        )
    elif action == '3BET_OR_FOLD':
        tips.append(
            f'3-BET OR FOLD: Too much squeeze risk to cold call {hand_strength}. '
            f'Either 3-bet to eliminate squeeze risk, or fold and protect stack.'
        )
    elif action == 'COLD_CALL':
        tips.append(
            f'COLD CALL: EV={ev:+.1f}BB positive despite {squeeze_pct:.0%} squeeze risk. '
            f'Hand plays well multiway; justify the risk. '
            f'If squeezed, fold without investing more chips.'
        )

    if squeeze_pct >= 0.20 and player_types_behind:
        dominant = max(player_types_behind,
                       key=lambda t: SQUEEZE_PROB_PER_PLAYER.get(t, 0.07))
        tips.append(
            f'HIGH SQUEEZE ALERT: {dominant.upper()} behind squeezes {SQUEEZE_PROB_PER_PLAYER.get(dominant, 0.07):.0%}. '
            f'3-bet to isolate or fold; do not cold call with marginal hands vs this player.'
        )

    return ColdCallSqueezeResult(
        hand_strength=hand_strength,
        player_types_behind=player_types_behind,
        cold_call_bb=cold_call_bb,
        squeeze_pct=squeeze_pct,
        squeeze_risk_level=risk_level,
        cold_call_ev_bb=ev,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ccs_one_liner(r: ColdCallSqueezeResult) -> str:
    return (
        f'[CCS {r.hand_strength}|{len(r.player_types_behind)}behind] '
        f'{r.recommended_action} squeeze={r.squeeze_pct:.0%} [{r.squeeze_risk_level}] '
        f'EV={r.cold_call_ev_bb:+.1f}BB'
    )
