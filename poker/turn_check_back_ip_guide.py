"""
Turn Check-Back IP Guide (turn_check_back_ip_guide.py)

When in position after c-betting the flop and getting called, should you
bet the turn (double barrel) or check back? This guide focuses on the
CHECK-BACK decision specifically -- distinct from barrel decision modules.

THEORY:
  WHY CHECK BACK THE TURN IP:
  1. RANGE PROTECTION: If you always bet turn with strong hands, villain knows
     to fold when you check → your check range becomes capped and unprotected.
  2. POT CONTROL: Protect your medium-strength hand (top pair weak kicker)
     from getting check-raised by villain's strong hands.
  3. FREE CARD: Some draws benefit from seeing river without investing.
  4. TRAP: Strong hands occasionally check back to induce river bluffs.

  HAND CATEGORIES FOR IP TURN CHECK-BACK:
  - MUST CHECK: Air with no equity (give up; check-fold to river bet)
  - SHOULD CHECK (pot control): Middle pair, weak top pair with kicker concerns
  - MIXING RANGE: Top pair good kicker -- check ~25-35% of the time
  - MUST BET: Strong value (sets, 2-pair, nut draws) -- bet for value/protection

  BOARD TEXTURE EFFECTS ON CHECK-BACK:
  - Dry board: check back less (villain has fewer draws; capping is OK)
  - Wet board: check back more (need range protection; villain hits more)
  - Paired board: check back traps more (villain less likely to have trips)
  - Monotone: check back more with made hands (too many draws; protect turn)

  VILLAIN TENDENCIES:
  - vs Fish (passive): Bet more for value; fish won't check-raise light
  - vs LAG: Check back more strong hands; LAG check-raises too often
  - vs Nit: Bet more freely; nit rarely CR; check-back only for pot control
  - vs Reg: Balance properly; check-back ~30% with top pair range

  SPR EFFECTS:
  - Low SPR (<3): Bet/commit; no need to check back
  - Medium SPR (3-7): Standard check-back frequencies
  - High SPR (>7): Check back more; protect against large check-raises

DISTINCT FROM:
  turn_barrel_decision.py:  When to barrel the turn (yes/no decision)
  check_back_ip.py:         IP flop check-back (not turn)
  delayed_cbet.py:          Checking flop then betting turn (not turn-specific)
  THIS MODULE:              TURN SPECIFIC IP CHECK-BACK; range protection;
                            category-based frequencies; villain-adjusted rates.
"""

from dataclasses import dataclass, field
from typing import List


CHECK_BACK_FREQ_BY_TEXTURE: dict = {
    'dry':      {'air': 1.00, 'weak_pair': 0.75, 'top_pair_wk': 0.45,
                 'top_pair_gk': 0.20, 'strong_value': 0.10, 'nut_draw': 0.15},
    'semi_wet': {'air': 1.00, 'weak_pair': 0.80, 'top_pair_wk': 0.55,
                 'top_pair_gk': 0.30, 'strong_value': 0.12, 'nut_draw': 0.25},
    'wet':      {'air': 1.00, 'weak_pair': 0.88, 'top_pair_wk': 0.65,
                 'top_pair_gk': 0.38, 'strong_value': 0.18, 'nut_draw': 0.35},
    'monotone': {'air': 1.00, 'weak_pair': 0.90, 'top_pair_wk': 0.72,
                 'top_pair_gk': 0.42, 'strong_value': 0.22, 'nut_draw': 0.40},
    'paired':   {'air': 1.00, 'weak_pair': 0.70, 'top_pair_wk': 0.40,
                 'top_pair_gk': 0.28, 'strong_value': 0.20, 'nut_draw': 0.15},
}

VILLAIN_CHECK_BACK_MODIFIER: dict = {
    'fish':   {'air': 0.00, 'weak_pair': -0.10, 'top_pair_wk': -0.12,
               'top_pair_gk': -0.08, 'strong_value': -0.05, 'nut_draw': -0.10},
    'nit':    {'air': 0.00, 'weak_pair': -0.05, 'top_pair_wk': -0.10,
               'top_pair_gk': -0.08, 'strong_value': -0.05, 'nut_draw': -0.05},
    'lag':    {'air': 0.00, 'weak_pair': +0.05, 'top_pair_wk': +0.12,
               'top_pair_gk': +0.15, 'strong_value': +0.10, 'nut_draw': +0.08},
    'rec':    {'air': 0.00, 'weak_pair': -0.05, 'top_pair_wk': -0.05,
               'top_pair_gk': -0.03, 'strong_value': 0.00, 'nut_draw': 0.00},
    'reg':    {'air': 0.00, 'weak_pair': 0.00, 'top_pair_wk': 0.00,
               'top_pair_gk': 0.00, 'strong_value': 0.00, 'nut_draw': 0.00},
}

SPR_CHECK_BACK_MODIFIER: dict = {
    'low':     -0.12,
    'medium':   0.00,
    'high':    +0.10,
}


def _spr_zone(spr: float) -> str:
    if spr < 3:
        return 'low'
    elif spr < 8:
        return 'medium'
    return 'high'


def _check_back_freq(
    hand_category: str,
    board_texture: str,
    villain_type: str,
    spr: float,
) -> float:
    base_dict = CHECK_BACK_FREQ_BY_TEXTURE.get(board_texture, CHECK_BACK_FREQ_BY_TEXTURE['semi_wet'])
    base = base_dict.get(hand_category, 0.50)
    villain_adj = VILLAIN_CHECK_BACK_MODIFIER.get(villain_type, {}).get(hand_category, 0.0)
    spr_adj = SPR_CHECK_BACK_MODIFIER.get(_spr_zone(spr), 0.0)
    return round(max(0.0, min(1.0, base + villain_adj + spr_adj)), 3)


def _turn_action(check_freq: float, hand_category: str, spr: float) -> str:
    if spr < 2.0 and hand_category not in ('air',):
        return 'BET_COMMIT'
    if check_freq >= 0.85:
        return 'CHECK_BACK_ALWAYS'
    elif check_freq >= 0.55:
        return 'CHECK_BACK_PREFER'
    elif check_freq >= 0.25:
        return 'CHECK_BACK_MIX'
    else:
        return 'BET_PREFERRED'


def _check_back_reason(hand_category: str, board_texture: str, villain_type: str) -> str:
    if hand_category == 'air':
        return 'air: no equity, check-fold to river bet'
    if hand_category in ('weak_pair',):
        return 'pot control: weak hand cannot call check-raise'
    if villain_type == 'lag' and hand_category in ('top_pair_gk', 'strong_value'):
        return 'trap vs LAG: LAG check-raises often; induce bluff'
    if board_texture in ('wet', 'monotone'):
        return 'range protection: wet board needs balanced check range'
    return 'mix: protect check range while primarily betting for value'


@dataclass
class TurnCheckBackResult:
    hand_category: str
    board_texture: str
    villain_type: str
    spr: float

    check_back_freq: float
    recommended_action: str
    reason: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_turn_check_back(
    hand_category: str = 'top_pair_gk',
    board_texture: str = 'semi_wet',
    villain_type: str = 'reg',
    spr: float = 5.0,
    pot_bb: float = 20.0,
    turn_card_quality: str = 'blank',
) -> TurnCheckBackResult:
    """
    Determine the optimal check-back frequency on the turn when IP.

    Args:
        hand_category:   'air','weak_pair','top_pair_wk','top_pair_gk',
                         'strong_value','nut_draw'
        board_texture:   'dry','semi_wet','wet','monotone','paired'
        villain_type:    'fish','rec','nit','lag','reg'
        spr:             Stack-to-pot ratio
        pot_bb:          Current pot in BB
        turn_card_quality: 'blank','good_for_hero','bad_for_hero'

    Returns:
        TurnCheckBackResult
    """
    check_freq = _check_back_freq(hand_category, board_texture, villain_type, spr)

    if turn_card_quality == 'good_for_hero':
        check_freq = max(0.0, check_freq - 0.10)
    elif turn_card_quality == 'bad_for_hero':
        check_freq = min(1.0, check_freq + 0.10)

    action = _turn_action(check_freq, hand_category, spr)
    reason = _check_back_reason(hand_category, board_texture, villain_type)

    verdict = (
        f'[TCB {hand_category}|{board_texture}|{villain_type}] '
        f'{action} check_freq={check_freq:.0%} spr={spr:.1f}'
    )

    reasoning = (
        f'Turn IP check-back: {hand_category} on {board_texture} vs {villain_type}. '
        f'SPR={spr:.1f} ({_spr_zone(spr)}). '
        f'Check-back frequency={check_freq:.0%}. '
        f'Action: {action}. Reason: {reason}.'
    )

    tips = []

    tips.append(
        f'TURN CHECK-BACK: {hand_category} on {board_texture} -- check back {check_freq:.0%} of the time. '
        f'{"Always check -- give up." if check_freq >= 0.90 else "Prefer check-back for pot control/protection." if check_freq >= 0.50 else "Mix check-back to protect range; mostly bet." if check_freq >= 0.25 else "Bet preferred; check-back only occasionally to balance."}'
    )

    tips.append(
        f'REASON: {reason}. '
        f'{"Bet/commit -- SPR too low to check-back." if spr < 2.0 else "High SPR -- protect against check-raises." if spr >= 8.0 else "Standard SPR -- use base frequencies."}'
    )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Increase check-back with top pairs and strong value. '
            f'LAG check-raises light -- checking protects you AND induces river bluffs. '
            f'Trap more vs aggressive players.'
        )

    if board_texture in ('wet', 'monotone'):
        tips.append(
            f'{board_texture.upper()} BOARD: Range protection critical. '
            f'Must include strong hands in check range or villain can raise any bet. '
            f'Check-back {check_freq:.0%} even with top pair to balance.'
        )

    return TurnCheckBackResult(
        hand_category=hand_category,
        board_texture=board_texture,
        villain_type=villain_type,
        spr=spr,
        check_back_freq=check_freq,
        recommended_action=action,
        reason=reason,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tcb_one_liner(r: TurnCheckBackResult) -> str:
    return (
        f'[TCB {r.hand_category}|{r.board_texture}|{r.villain_type}] '
        f'{r.recommended_action} chk={r.check_back_freq:.0%} spr={r.spr:.1f}'
    )
