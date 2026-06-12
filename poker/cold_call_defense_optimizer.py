"""
Cold Call Defense Optimizer (cold_call_defense_optimizer.py)

Optimizes the decision to cold call, 3-bet, or fold when facing an open raise
without being in the blinds. Cold calling has specific requirements:

COLD CALL THEORY:
  Cold call = calling a raise without having previously invested money.
  Unlike BB defense (invested 1BB), cold calling from CO/HJ/BTN starts fresh.

  COLD CALL REQUIREMENTS (stricter than BB defense):
  1. POSITION: Must have position on the raiser (act after them postflop)
  2. EQUITY: Sufficient equity vs opener's range to realize value
  3. IMPLIED ODDS: Stack deep enough to win a large pot when you hit
  4. MULTIWAY POTENTIAL: Hands that play well in multiway pots (sets, draws)

  WHY COLD CALLING IS OFTEN WRONG:
  - No "dead money" benefit (unlike BB)
  - Squeezed: players behind you may 3-bet; you call off equity before seeing flop
  - Dominated preflop: AJ vs AQ = cooler; lose big when both hit top pair

  WHEN COLD CALLING IS OPTIMAL:
  1. Pairs (22-TT): set-mining; need 15:1 implied odds
     Profitable when SPR >= 5 and deep stacks
  2. Suited connectors: multiway value; play well vs weak ranges
  3. Position matters: only cold call from BTN/CO (never UTG/HJ as cold call)
  4. vs Wide opener: can cold call more hands (wider range = weaker hands)
  5. Multiway pot expected: others likely to call → better odds for speculative hands

  3-BET vs COLD CALL:
  3-bet when: (a) hand has value heads-up (QQ+, AK), (b) squeeze opportunity,
              (c) range balance requires it (GTO), (d) fold equity > 40%
  Cold call when: (a) speculative hands with implied odds, (b) want multiway pot,
                  (c) position secured, (d) hand doesn't benefit from isolation

  COLD CALL HAND SELECTION:
  BTN vs CO open:
    Cold call: 77-TT, suited connectors (76s+), A7s-A9s, KQs, KJs, QJs
    3-bet: JJ+, AK, AQs (value 3-bets)
    Fold: offsuit broadways (KJo, QTo), weak aces (A2o-A6o)
  HJ vs UTG open:
    Much tighter; cold call only 88-TT, KQs, strongest speculative hands
    Avoid cold calling weak hands; range of UTG open is very strong

DISTINCT FROM:
  cold_call.py:          Basic cold call logic
  call_threshold.py:     Whether to call a bet
  preflop_advisor.py:    General preflop action
  iso_raise.py:          Isolating limpers (you raise)
  THIS MODULE:           OPTIMIZATION framework for cold calling;
                         set mining profitability; squeeze risk;
                         3-bet vs call vs fold decision tree.

Usage:
    from poker.cold_call_defense_optimizer import optimize_cold_call, ColdCallOptimization, ccdo_one_liner

    result = optimize_cold_call(
        hero_hand='77',
        hero_position='btn',
        opener_position='co',
        opener_raise_size_bb=3.0,
        stack_bb=100.0,
        pot_bb=4.5,
        opener_vpip=0.28,
        players_behind=1,
        villain_fold_to_3bet=0.52,
    )
    print(ccdo_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Required SPR (stack/pot) for set mining profitability
SET_MINE_MIN_SPR = 5.0

# Cold call eligible positions (position vs opener)
IP_POSITIONS = {
    ('co', 'utg'), ('co', 'utg1'), ('co', 'hj'),
    ('btn', 'utg'), ('btn', 'utg1'), ('btn', 'hj'), ('btn', 'co'),
    ('hj', 'utg'), ('hj', 'utg1'),
    ('sb', 'utg'), ('sb', 'co'), ('sb', 'btn'),   # SB: oop postflop
}

# Hand type by category
PAIRS = {'22', '33', '44', '55', '66', '77', '88', '99', 'TT', 'JJ', 'QQ', 'KK', 'AA'}
SMALL_PAIRS = {'22', '33', '44', '55', '66'}
MEDIUM_PAIRS = {'77', '88', '99', 'TT'}
BIG_PAIRS = {'JJ', 'QQ', 'KK', 'AA'}
SUITED_CONNECTORS = {'87s', '76s', '65s', '54s', '98s', 'T9s', 'JTs', 'QJs', 'KQs', 'KJs', 'QTs'}
STRONG_ACES = {'AKs', 'AKo', 'AQs', 'AQo', 'AJs'}
WEAK_ACES = {'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s'}


def _hand_type(hand: str) -> str:
    if hand in BIG_PAIRS:
        return 'big_pair'
    if hand in MEDIUM_PAIRS:
        return 'medium_pair'
    if hand in SMALL_PAIRS:
        return 'small_pair'
    if hand in SUITED_CONNECTORS:
        return 'suited_connector'
    if hand in STRONG_ACES:
        return 'strong_ace'
    if hand in WEAK_ACES:
        return 'weak_ace'
    return 'other'


def _is_ip(hero_position: str, opener_position: str) -> bool:
    """True if hero will have position on opener postflop."""
    return (hero_position.lower(), opener_position.lower()) in IP_POSITIONS


def _set_mine_profitable(
    raise_size_bb: float,
    stack_bb: float,
    pot_before_call: float,
) -> bool:
    """True if set mining is profitable (15:1 implied odds rule)."""
    implied_odds_needed = raise_size_bb * 15
    pot_after_call = pot_before_call + raise_size_bb
    spr = stack_bb / pot_after_call
    return spr >= SET_MINE_MIN_SPR and stack_bb >= implied_odds_needed


def _squeeze_risk(players_behind: int, opener_vpip: float) -> float:
    """Risk of being squeezed (player behind 3-bets after you call)."""
    if players_behind == 0:
        return 0.0
    base_squeeze = 0.07 * players_behind
    if opener_vpip <= 0.22:
        base_squeeze *= 0.7   # tight opener squeezed less
    return round(min(0.40, base_squeeze), 3)


def _optimal_action(
    hand: str,
    hero_position: str,
    opener_position: str,
    stack_bb: float,
    raise_size_bb: float,
    pot_bb: float,
    opener_vpip: float,
    villain_fold_to_3bet: float,
    players_behind: int,
) -> str:
    hand_type = _hand_type(hand)
    ip = _is_ip(hero_position, opener_position)
    squeeze_risk = _squeeze_risk(players_behind, opener_vpip)
    set_mine = _set_mine_profitable(raise_size_bb, stack_bb, pot_bb)

    if hand_type == 'big_pair':
        return 'three_bet_value'   # always 3-bet JJ+/AK

    if hand_type == 'strong_ace':
        if villain_fold_to_3bet >= 0.50:
            return 'three_bet_value'
        return 'three_bet_or_call'

    if hand_type == 'medium_pair':
        if not ip:
            return 'fold'   # never cold call oop with medium pairs
        if set_mine:
            if squeeze_risk >= 0.20:
                return 'fold'   # too risky; might be squeezed
            return 'cold_call'
        return 'fold'

    if hand_type == 'small_pair':
        if not ip or not set_mine or squeeze_risk >= 0.15:
            return 'fold'
        return 'cold_call'

    if hand_type == 'suited_connector':
        if not ip:
            return 'fold'
        if squeeze_risk >= 0.20:
            return 'fold'
        if opener_vpip >= 0.35:
            return 'cold_call'   # wide opener; implied odds better
        return 'fold' if opener_vpip < 0.25 else 'cold_call'

    if hand_type == 'weak_ace':
        if not ip:
            return 'fold'
        if villain_fold_to_3bet >= 0.55:
            return 'three_bet_bluff'
        return 'fold'

    return 'fold'


@dataclass
class ColdCallOptimization:
    # Inputs
    hero_hand: str
    hero_position: str
    opener_position: str
    opener_raise_size_bb: float
    stack_bb: float
    pot_bb: float
    opener_vpip: float
    players_behind: int
    villain_fold_to_3bet: float

    # Analysis
    hand_type: str
    is_ip: bool
    set_mine_profitable: bool
    squeeze_risk: float
    optimal_action: str    # 'cold_call' / 'three_bet_value' / 'fold' / 'three_bet_bluff'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def optimize_cold_call(
    hero_hand: str = '77',
    hero_position: str = 'btn',
    opener_position: str = 'co',
    opener_raise_size_bb: float = 3.0,
    stack_bb: float = 100.0,
    pot_bb: float = 4.5,
    opener_vpip: float = 0.28,
    players_behind: int = 1,
    villain_fold_to_3bet: float = 0.52,
) -> ColdCallOptimization:
    """
    Optimize cold call vs 3-bet vs fold decision.

    Args:
        hero_hand:            Hero's hand
        hero_position:        Hero's position ('btn', 'co', 'hj', etc.)
        opener_position:      Raiser's position
        opener_raise_size_bb: Open raise size in BB
        stack_bb:             Effective stack
        pot_bb:               Current pot before hero acts
        opener_vpip:          Opener's VPIP
        players_behind:       Players left to act who might squeeze
        villain_fold_to_3bet: Villain fold-to-3bet rate

    Returns:
        ColdCallOptimization
    """
    htype = _hand_type(hero_hand)
    ip = _is_ip(hero_position, opener_position)
    set_mine = _set_mine_profitable(opener_raise_size_bb, stack_bb, pot_bb)
    sq_risk = _squeeze_risk(players_behind, opener_vpip)
    action = _optimal_action(
        hero_hand, hero_position, opener_position,
        stack_bb, opener_raise_size_bb, pot_bb,
        opener_vpip, villain_fold_to_3bet, players_behind
    )

    verdict = (
        f'[CCDO {hero_hand}|{hero_position}vs{opener_position}] '
        f'{action.upper()} | ip={ip} set_mine={set_mine} sq_risk={sq_risk:.0%}'
    )

    reasoning = (
        f'Cold call optimization: {hero_hand} ({htype}) at {hero_position} vs {opener_position} open. '
        f'IP: {ip}. Set mine profitable: {set_mine}. '
        f'Squeeze risk: {sq_risk:.0%}. Opener VPIP: {opener_vpip:.0%}. '
        f'Villain fold-to-3bet: {villain_fold_to_3bet:.0%}. '
        f'Optimal action: {action}.'
    )

    tips = []

    tips.append(
        f'COLD CALL CRITERIA: '
        f'(1) IP: {"YES" if ip else "NO - avoid cold call OOP"}. '
        f'(2) Set mine {opener_raise_size_bb:.1f}BB: {"YES" if set_mine else "NO - need 15x implied odds"}. '
        f'(3) Squeeze risk ({sq_risk:.0%}): {"LOW" if sq_risk < 0.15 else "MODERATE/HIGH - risky"}. '
        f'Optimal: {action.upper()}.'
    )

    if 'three_bet' in action:
        three_bet_size = opener_raise_size_bb * 3.0
        tips.append(
            f'3-BET SIZING: {three_bet_size:.1f}BB (3x the open of {opener_raise_size_bb:.1f}BB). '
            f'Villain fold-to-3bet={villain_fold_to_3bet:.0%}. '
            f'{"3-bet for value: build pot with premium hand." if action == "three_bet_value" else "3-bet as bluff: steal dead money with blocker."}'
        )

    if 'cold_call' in action:
        tips.append(
            f'COLD CALL PLAN: '
            f'Set mining with {hero_hand}: need to hit set (~11%) to win large pot. '
            f'Implied odds: stack={stack_bb:.0f}BB, call={opener_raise_size_bb:.1f}BB = {stack_bb/opener_raise_size_bb:.0f}:1. '
            f'Profitable when villain pays off set: effective SPR = {stack_bb/pot_bb:.1f}. '
            f'If you miss flop: check-fold unless you pick up strong draw.'
        )

    tips.append(
        f'SQUEEZE RISK: {players_behind} player(s) behind. '
        f'Probability of squeeze: {sq_risk:.0%}. '
        f'{"High squeeze risk: only cold call/3-bet; do not limp-call." if sq_risk >= 0.20 else "Low squeeze risk: cold call is safe."} '
        f'If squeezed: fold unless you have JJ+/AK.'
    )

    if not ip:
        tips.append(
            f'OOP PENALTY: {hero_position} vs {opener_position} = out of position postflop. '
            f'Cold calling OOP gives away significant equity. '
            f'OOP cold calls require very strong implied odds. '
            f'For most hands: fold or 3-bet (never cold call oop with speculative hands).'
        )

    return ColdCallOptimization(
        hero_hand=hero_hand,
        hero_position=hero_position,
        opener_position=opener_position,
        opener_raise_size_bb=opener_raise_size_bb,
        stack_bb=stack_bb,
        pot_bb=pot_bb,
        opener_vpip=opener_vpip,
        players_behind=players_behind,
        villain_fold_to_3bet=villain_fold_to_3bet,
        hand_type=htype,
        is_ip=ip,
        set_mine_profitable=set_mine,
        squeeze_risk=sq_risk,
        optimal_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ccdo_one_liner(r: ColdCallOptimization) -> str:
    return (
        f'[CCDO {r.hero_hand}|{r.hero_position}vs{r.opener_position}] '
        f'{r.optimal_action.upper()} | '
        f'ip={r.is_ip} sq_risk={r.squeeze_risk:.0%}'
    )
