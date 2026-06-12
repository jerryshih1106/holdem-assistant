"""
Preflop 3-Way Strategy (preflop_3way_strategy.py)

Strategy for 3-way pots: when there's an open, a cold-caller, and
you are considering entering the pot (or when you're already in a 3-way scenario).

3-WAY POT PREFLOP THEORY:
  In a 3-way pot, the following positions exist:
  - OPENER: opened the raise preflop
  - COLD_CALLER: called the open without 3-betting
  - SQUEEZER: 3-bets after open + call
  - IP_CLAIMER: claims position (BTN)

  COLD-CALLER STRATEGY:
    Cold-callers represent a capped range (no 4-bets in range).
    Key hands to cold-call: Sets (small pairs IP), suited connectors,
    broadway hands IP. AVOID: hands dominated by opener (KQ vs UTG opener).

  SQUEEZE STRATEGY:
    A squeeze works when:
    1. Dead money is significant (caller + opener dead money)
    2. Opener and caller are likely to fold
    3. Or hero has a strong hand to 3-bet value
    Squeeze size: open × 3 + callers × open (each caller adds 1 open)

  3-WAY FLOP ADJUSTMENTS:
    C-bet frequencies drop dramatically 3-way:
    - Dry: IP PFR 40% (vs 65% HU)
    - Wet: IP PFR 25% (vs 50% HU)
    Both players having wide ranges means more hands that connect.

  POSITION CLARIFICATION:
    In 3-way pot (BTN opens, CO cold-calls, BB defends):
    - BTN = IP vs all opponents
    - CO = middle position (IP vs BB, OOP vs BTN)
    - BB = OOP vs both
    BB should give up fast without strong holdings.

DISTINCT FROM:
  squeeze.py:          General squeeze analysis
  three_way_pot_matrix.py: Post-flop 3-way decision matrix
  squeeze_ev_optimizer.py: Squeeze EV calculation
  THIS MODULE:         PREFLOP 3-way strategy; cold-call decision vs
                       open+caller; squeeze sizing; 3-way range adjustments.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Cold-call eligible hands by position (when facing open + 1 caller)
COLD_CALL_IP_HANDS = {
    'premium': {'AA', 'KK', 'QQ', 'JJ'},       # 4-bet or just call
    'value_ip': {'TT', '99', '88', 'AKs', 'AKo', 'AQs', 'KQs'},
    'set_mine': {'77', '66', '55', '44', '33', '22'},
    'suited_conn': {'JTs', 'T9s', '98s', '87s', '76s', '65s'},
    'suited_broad': {'AJs', 'ATs', 'KJs', 'QJs'},
}

COLD_CALL_OOP_HANDS = {
    'premium': {'AA', 'KK'},           # must 3-bet (can't cold-call OOP with these)
    'value_oop': {'QQ', 'JJ', 'AKs', 'AKo'},  # 3-bet or fold; rarely cold-call
    'rarely_call': {'TT', 'AQs'},      # marginal cold-call OOP
}

# Squeeze hands given fold-to-3bet estimates
SQUEEZE_VALUE_HANDS = {'AA', 'KK', 'QQ', 'JJ', 'TT', 'AKs', 'AKo', 'AQs'}
SQUEEZE_BLUFF_HANDS = {'A5s', 'A4s', 'A3s', 'A2s', 'KQs', 'QJs', 'J9s'}

# Squeeze sizing multiplier
SQUEEZE_MULTIPLIER = 3.0   # open × 3 + each caller × open


def _squeeze_size(open_bb: float, n_callers: int) -> float:
    return round(open_bb * SQUEEZE_MULTIPLIER + n_callers * open_bb, 1)


def _cold_call_action(
    hero_hand: str,
    hero_position: str,
    opener_position: str,
    stack_bb: float,
    opener_vpip: float,
    n_callers_before: int,
) -> str:
    is_ip = hero_position in ('btn', 'co') and opener_position in ('utg', 'hj', 'mp')
    is_btn_vs_co = hero_position == 'btn' and opener_position == 'co'
    is_oop = hero_position in ('bb', 'sb')

    if hero_hand in ('AA', 'KK'):
        return '3bet_value'
    if hero_hand in ('QQ', 'JJ', 'AKs', 'AKo'):
        return '3bet_or_cold_call'
    if is_oop:
        if hero_hand in COLD_CALL_OOP_HANDS.get('rarely_call', set()):
            return 'cold_call_marginal_oop'
        return 'fold_oop'
    if is_ip or is_btn_vs_co:
        if any(hero_hand in v for v in COLD_CALL_IP_HANDS.values()):
            if hero_hand in COLD_CALL_IP_HANDS.get('set_mine', set()):
                rough_call = max(2.0, opener_vpip * 100 * 0.10)
                spr_est = (stack_bb - rough_call) / max(1.0, rough_call * 3)
                if spr_est >= 5.0:
                    return 'cold_call_set_mine'
                return 'fold_spr_too_low'
            return 'cold_call'
    return 'fold'


def _squeeze_ev(
    fold_prob_opener: float,
    fold_prob_caller: float,
    squeeze_size: float,
    dead_money: float,
    hero_eq: float,
    pot_if_called: float,
) -> float:
    """EV of squeeze."""
    p_all_fold = fold_prob_opener * fold_prob_caller
    ev_fold = p_all_fold * dead_money
    ev_called = (1 - p_all_fold) * (hero_eq * (pot_if_called + 2 * squeeze_size) - squeeze_size)
    return round(ev_fold + ev_called, 2)


def _3way_cbet_freq(
    board_texture: str,
    hero_position: str,
    hand_category: str,
) -> float:
    """GTO cbet frequency in 3-way pot."""
    base = {
        'dry':     0.38,
        'medium':  0.28,
        'wet':     0.22,
        'paired':  0.30,
        'monotone': 0.18,
    }.get(board_texture, 0.28)

    if hero_position in ('oop',):
        base *= 0.75   # OOP cbets much less

    if hand_category in ('set', 'nuts', 'flush', 'straight', 'full_house'):
        base = min(0.85, base + 0.25)   # always cbet strong value
    elif hand_category in ('air', 'gutshot'):
        base = max(0.05, base - 0.15)   # rarely bluff 3-way

    return round(min(1.0, max(0.0, base)), 2)


@dataclass
class ThreeWayPreflopAdvice:
    # Inputs
    hero_hand: str
    hero_position: str
    opener_position: str
    n_callers: int
    open_size_bb: float
    stack_bb: float
    opener_vpip: float

    # Analysis
    cold_call_action: str
    squeeze_size_bb: float
    squeeze_ev_est: float
    three_way_cbet_freq: float
    dead_money_bb: float
    is_good_squeeze_spot: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_3way_preflop(
    hero_hand: str = 'TT',
    hero_position: str = 'btn',
    opener_position: str = 'co',
    n_callers: int = 1,
    open_size_bb: float = 3.0,
    stack_bb: float = 100.0,
    opener_vpip: float = 0.28,
    caller_fold_to_3bet: float = 0.55,
    opener_fold_to_3bet: float = 0.50,
    board_texture: str = 'dry',
    hand_category_postflop: str = 'top_pair',
) -> ThreeWayPreflopAdvice:
    """
    Analyze preflop 3-way pot strategy.

    Args:
        hero_hand:            Hero's hand
        hero_position:        Hero's position ('btn'/'co'/'hj'/'bb'/'sb')
        opener_position:      Opener's position
        n_callers:            Number of callers before hero
        open_size_bb:         Open-raise size in BB
        stack_bb:             Effective stack in BB
        opener_vpip:          Opener's VPIP (0-1)
        caller_fold_to_3bet:  Caller's fold-to-3bet frequency
        opener_fold_to_3bet:  Opener's fold-to-3bet frequency
        board_texture:        Board texture for postflop cbet estimate
        hand_category_postflop: Expected hand category on flop (for cbet)

    Returns:
        ThreeWayPreflopAdvice
    """
    cc_action = _cold_call_action(
        hero_hand, hero_position, opener_position, stack_bb, opener_vpip, n_callers
    )
    dead_money = open_size_bb * (n_callers + 1)   # opener + callers already in
    sqz_size = _squeeze_size(open_size_bb, n_callers)
    hero_eq_vs_range = 0.55 if hero_hand in SQUEEZE_VALUE_HANDS else 0.42
    pot_if_called = dead_money + sqz_size
    sqz_ev = _squeeze_ev(
        opener_fold_to_3bet, caller_fold_to_3bet,
        sqz_size, dead_money, hero_eq_vs_range, pot_if_called,
    )
    cbet_freq = _3way_cbet_freq(board_texture, 'ip' if hero_position == 'btn' else 'oop', hand_category_postflop)
    is_good_squeeze = (
        dead_money >= 4.5 and
        (hero_hand in SQUEEZE_VALUE_HANDS or (opener_fold_to_3bet >= 0.50 and caller_fold_to_3bet >= 0.50))
    )

    verdict = (
        f'[3WAY {hero_hand}|{hero_position}] '
        f'{cc_action.upper()} | '
        f'sqz_ev={sqz_ev:+.1f}BB sqz_size={sqz_size:.0f}BB | '
        f'cbet_3way={cbet_freq:.0%}'
    )

    reasoning = (
        f'3-way preflop: {hero_hand} at {hero_position} vs {opener_position} open + {n_callers} caller(s). '
        f'Dead money: {dead_money:.1f}BB. '
        f'Cold-call action: {cc_action}. '
        f'Squeeze to {sqz_size:.0f}BB: EV={sqz_ev:+.1f}BB. '
        f'3-way {board_texture} flop cbet freq: {cbet_freq:.0%}.'
    )

    tips = []
    tips.append(
        f'COLD-CALL vs SQUEEZE: {hero_hand} at {hero_position}. '
        f'Action: {cc_action}. '
        f'{"Good squeeze spot!" if is_good_squeeze else "Squeeze marginal -- prefer cold-call."}'
    )

    tips.append(
        f'SQUEEZE MATH: Dead money={dead_money:.1f}BB, Squeeze to {sqz_size:.0f}BB. '
        f'EV={sqz_ev:+.1f}BB. '
        f'Opener fold-to-3b={opener_fold_to_3bet:.0%}, Caller fold-to-3b={caller_fold_to_3bet:.0%}. '
        f'{"SQUEEZE: EV positive." if sqz_ev > 0 else "NO SQUEEZE: EV negative."}'
    )

    tips.append(
        f'3-WAY FLOP: Cbet much less in 3-way pots. '
        f'{board_texture} board with {hand_category_postflop}: cbet {cbet_freq:.0%} '
        f'(vs HU: {min(1.0, cbet_freq*1.65):.0%}). '
        f'Two opponents connected = fold equity drops. Check often in 3-way.'
    )

    if 'oop' in cc_action:
        tips.append(
            f'OOP WARNING: Cold-calling OOP with {hero_hand} is dangerous. '
            f'You will face 2 opponents out of position. '
            f'Prefer 3-bet (not cold-call) OOP if continuing.'
        )
    elif 'set_mine' in cc_action:
        tips.append(
            f'SET MINING: {hero_hand} cold-call for implied odds. '
            f'Need SPR >= 5 and ~15:1 implied odds. '
            f'Stack={stack_bb:.0f}BB vs call={open_size_bb:.0f}BB: '
            f'{"SPR OK." if stack_bb/open_size_bb >= 15 else "SPR LOW -- consider folding."}'
        )

    return ThreeWayPreflopAdvice(
        hero_hand=hero_hand,
        hero_position=hero_position,
        opener_position=opener_position,
        n_callers=n_callers,
        open_size_bb=open_size_bb,
        stack_bb=stack_bb,
        opener_vpip=opener_vpip,
        cold_call_action=cc_action,
        squeeze_size_bb=sqz_size,
        squeeze_ev_est=sqz_ev,
        three_way_cbet_freq=cbet_freq,
        dead_money_bb=dead_money,
        is_good_squeeze_spot=is_good_squeeze,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def p3w_one_liner(r: ThreeWayPreflopAdvice) -> str:
    return (
        f'[P3W {r.hero_hand}|{r.hero_position}] '
        f'{r.cold_call_action.upper()} | '
        f'sqz_ev={r.squeeze_ev_est:+.1f}BB | '
        f'3way_cbet={r.three_way_cbet_freq:.0%}'
    )
