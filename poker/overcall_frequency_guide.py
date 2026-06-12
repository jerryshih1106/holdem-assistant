"""
Overcall Frequency Guide (overcall_frequency_guide.py)

Calibrates overcall (3rd+ player call preflop) frequency based on number of
players already in the pot, position, implied odds, and hand type.

THEORY:
  OVERCALL vs COLD CALL:
  Cold call: first player to call a raise (2 players in pot: raiser + caller)
  Overcall:  additional call when 1+ players already called (3+ way pot)

  WHY OVERCALL FREQUENCY SHOULD BE LOWER:
  (1) More opponents = more equity needed to win
  (2) Risk of squeeze from players behind
  (3) Domination risk increases in multiway pots

  OVERCALL HAND TYPES:
  INCREASE OVERCALL FREQ: Suited hands (implied odds multiway), small pairs (set mining)
  DECREASE OVERCALL FREQ: Dominated broadways (AJo, KQo often dominated multiway)
  FOLD OVERCALL:          Offsuit hands without multiway equity (KTo, QJo multiway)

  EACH EXTRA PLAYER: -4% to overcall frequency threshold
  POSITION BONUS: IP overcallers get +3% (realize equity better)

  IMPLIED ODDS MULTIPLIER:
  Multiway pots increase implied odds for strong made hands significantly.
  A set in 4-way pot yields ~3x more implied odds than heads-up.

DISTINCT FROM:
  cold_call_frequency_guide.py: First caller in pot (2-way after call)
  multiway_call.py:             General multiway calling logic
  THIS MODULE:                  OVERCALL frequency (3rd+ player); multiway
                                implied odds; squeeze avoidance strategy.
"""

from dataclasses import dataclass, field
from typing import List

BASELINE_OVERCALL_FREQ: dict = {
    'btn': 0.12,
    'co':  0.09,
    'hj':  0.07,
    'mp':  0.05,
    'utg': 0.03,
    'sb':  0.02,
    'bb':  0.14,
}

EXTRA_PLAYER_OVERCALL_REDUCTION: float = -0.03
POSITION_IP_OVERCALL_BONUS: float = +0.03
SQUEEZE_RISK_OVERCALL_PENALTY: float = -0.03

HAND_TYPE_OVERCALL_MODIFIER: dict = {
    'small_pair':        +0.06,
    'suited_connector':  +0.05,
    'suited_broadway':   +0.02,
    'offsuit_broadway':  -0.04,
    'suited_one_gap':    +0.04,
    'pocket_pair_med':   +0.03,
    'weak_suited':       +0.01,
    'offsuit_weak':      -0.07,
}

VILLAIN_OVERCALL_MODIFIER: dict = {
    'fish':            +0.04,
    'calling_station': +0.02,
    'nit':             -0.03,
    'lag':             -0.05,
    'reg':              0.00,
}

IP_POSITIONS = {'btn', 'co', 'hj'}


def _is_ip(position: str) -> bool:
    return position in IP_POSITIONS


def _optimal_overcall_freq(
    position: str,
    n_players_in: int,
    hand_type: str,
    squeezers_behind: int,
    villain_type: str,
) -> float:
    base = BASELINE_OVERCALL_FREQ.get(position, 0.06)
    extra = max(0, n_players_in - 1) * EXTRA_PLAYER_OVERCALL_REDUCTION
    ip_bonus = POSITION_IP_OVERCALL_BONUS if _is_ip(position) else 0.0
    sq_pen = squeezers_behind * SQUEEZE_RISK_OVERCALL_PENALTY
    hand_mod = HAND_TYPE_OVERCALL_MODIFIER.get(hand_type, 0.0)
    vil_mod = VILLAIN_OVERCALL_MODIFIER.get(villain_type, 0.0)
    freq = base + extra + ip_bonus + sq_pen + hand_mod + vil_mod
    return round(min(0.25, max(0.0, freq)), 3)


def _overcall_decision(hand_sdv: float, optimal_freq: float, position: str) -> str:
    if optimal_freq <= 0.01:
        return 'FOLD_OVERCALL'
    if hand_sdv >= 0.70:
        return '3BET_PREFERRED'
    if hand_sdv >= 0.55:
        return 'OVERCALL_STRONG' if _is_ip(position) else 'SQUEEZE_OR_FOLD'
    if hand_sdv >= 0.30:
        return 'OVERCALL_IMPLIED_ODDS'
    return 'FOLD_OVERCALL'


@dataclass
class OvercallFrequencyResult:
    position: str
    n_players_in: int
    hand_type: str
    hand_sdv: float
    squeezers_behind: int
    villain_type: str

    optimal_overcall_freq: float
    overcall_decision: str
    multiway_implied_multiplier: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_overcall_frequency(
    position: str = 'btn',
    n_players_in: int = 1,
    hand_type: str = 'suited_connector',
    hand_sdv: float = 0.40,
    squeezers_behind: int = 0,
    villain_type: str = 'reg',
) -> OvercallFrequencyResult:
    """
    Calibrate overcall frequency (3rd+ player calling preflop).

    Args:
        position:          Hero's position ('btn','co','hj','mp','utg','sb','bb')
        n_players_in:      Number of players already in pot (callers, not counting raiser)
        hand_type:         Hand category ('small_pair','suited_connector','offsuit_broadway',etc.)
        hand_sdv:          Hand showdown value (0-1)
        squeezers_behind:  Players behind who might squeeze
        villain_type:      Original raiser type

    Returns:
        OvercallFrequencyResult
    """
    optimal = _optimal_overcall_freq(position, n_players_in, hand_type, squeezers_behind, villain_type)
    decision = _overcall_decision(hand_sdv, optimal, position)
    mw_mult = round(1.0 + n_players_in * 0.35, 2)

    verdict = (
        f'[OC {position}|{n_players_in}in|{hand_type}] '
        f'freq={optimal:.0%} dec={decision} mw_mult={mw_mult}'
    )

    reasoning = (
        f'Overcall freq from {position}: '
        f'base={BASELINE_OVERCALL_FREQ.get(position, 0.06):.0%} '
        f'extra_players={max(0, n_players_in-1)}x{EXTRA_PLAYER_OVERCALL_REDUCTION:.0%}={max(0, n_players_in-1)*EXTRA_PLAYER_OVERCALL_REDUCTION:.0%} '
        f'ip={POSITION_IP_OVERCALL_BONUS if _is_ip(position) else 0:+.0%} '
        f'squeeze={squeezers_behind}x{SQUEEZE_RISK_OVERCALL_PENALTY:.0%}={squeezers_behind*SQUEEZE_RISK_OVERCALL_PENALTY:.0%} '
        f'hand_mod={HAND_TYPE_OVERCALL_MODIFIER.get(hand_type, 0):+.0%} '
        f'vil_mod={VILLAIN_OVERCALL_MODIFIER.get(villain_type, 0):+.0%}. '
        f'Optimal={optimal:.0%}. Decision={decision}. MW_implied={mw_mult}x.'
    )

    tips = []

    tips.append(
        f'Overcall freq from {position} ({n_players_in} player(s) in pot): {optimal:.0%}. '
        f'Hand={hand_type} ({decision}). '
        f'Multiway implied odds multiplier: {mw_mult}x vs heads-up. '
        f'{"IP: realize equity better in multiway pots" if _is_ip(position) else "OOP: fold more; harder to profit multiway without position"}.'
    )

    if decision == 'FOLD_OVERCALL':
        tips.append(
            f'FOLD overcall: {hand_type} does not have sufficient multiway equity. '
            f'Offsuit hands and weak hands lose value in {n_players_in+1}-way pots. '
            f'{"Focus on 3-betting or folding -- not flatting" if hand_sdv >= 0.55 else "Hand too weak for overcall EV"}.'
        )
    elif decision == 'OVERCALL_IMPLIED_ODDS':
        tips.append(
            f'OVERCALL for implied odds: {hand_type} gains {mw_mult}x implied odds multiway. '
            f'Required: stack/call ratio sufficient; SPR allows set-mining or flush odds. '
            f'Squeeze risk: {squeezers_behind} behind -- {"be careful of squeezes" if squeezers_behind > 0 else "no squeeze threat"}.'
        )
    elif decision == '3BET_PREFERRED':
        tips.append(
            f'3-BET PREFERRED over overcall: hand SDV={hand_sdv:.0%} too strong to flat. '
            f'3-betting denies equity to players behind and takes initiative. '
            f'Overcalling strong hands multiway is often -EV vs squeeze risk.'
        )

    if n_players_in >= 2:
        tips.append(
            f'{n_players_in} players already in: multiway pot likely. '
            f'Focus on implied odds hands (small pairs, suited connectors). '
            f'Dominated broadways (KQo, AJo) drop dramatically in value.'
        )

    return OvercallFrequencyResult(
        position=position,
        n_players_in=n_players_in,
        hand_type=hand_type,
        hand_sdv=hand_sdv,
        squeezers_behind=squeezers_behind,
        villain_type=villain_type,
        optimal_overcall_freq=optimal,
        overcall_decision=decision,
        multiway_implied_multiplier=mw_mult,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ocf_one_liner(r: OvercallFrequencyResult) -> str:
    return (
        f'[OC {r.position}|{r.n_players_in}in|{r.hand_type}] '
        f'freq={r.optimal_overcall_freq:.0%} {r.overcall_decision}'
    )
