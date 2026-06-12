"""
Blind vs Blind Strategy Guide (blind_vs_blind_strategy_guide.py)

Complete strategy guide for SB vs BB heads-up spots (folded around to SB).
This is the most common heads-up situation with unique position dynamics.

THEORY:
  WHY BLIND VS BLIND IS UNIQUE:
  1. SB is the only player who is IN POSITION preflop but OUT OF POSITION postflop
  2. Both players have invested money (SB=0.5BB, BB=1BB)
  3. Only two players remain -- ranges are much wider than vs full table
  4. Effective open raise from SB is vs just one opponent

  SB PREFLOP OPENING RANGE:
  - GTO SB open: ~45-55% of hands (much wider than any other position)
  - Limp vs raise: modern strategy leans toward RAISE (3BB standard)
  - Some strategies mix limp/raise but raising is simpler and exploitable less

  BB DEFENSE VS SB:
  - BB must defend wider than vs other positions (only 1BB to call 2.5-3BB)
  - GTO BB defense: ~55-65% of hands
  - BB 3-bet range: ~14-18% (wider than vs BTN because SB range is wider)
  - BB fold: ~35-45%

  POSTFLOP POSITION DYNAMICS (KEY INSIGHT):
  - SB acts FIRST postflop (same as BB in a normal HU hand if SB raised)
  - This means SB is OUT OF POSITION for all flop/turn/river decisions
  - BB has POSITION for the entire postflop -- acts last; more information
  - SB must compensate for OOP disadvantage with better preflop hand selection

  SB POSTFLOP STRATEGY (OOP):
  - Bet (donk) less frequently; check more with all hand types
  - Check strong hands sometimes (to trap and protect check range)
  - C-bet flop ~55-65% (lower than BTN c-bet vs BB which is ~70-80%)
  - On dangerous turns/rivers: check-fold more with marginal hands

  BB POSTFLOP STRATEGY (IP):
  - Check back flop ~30-35% to protect range (not always betting)
  - Bet turns when SB shows weakness (checks twice)
  - River value bet sizing: can go larger IP (1BB/100 position advantage)
  - Float more with position; SB often c-bets then gives up

  COMMON MISTAKES IN BVB SPOTS:
  1. SB limping too much preflop (giving BB free options)
  2. BB over-3betting (SB range wide; need value to 3-bet)
  3. SB c-betting too wide postflop (OOP; need condensed range)
  4. BB not floating enough with position (IP floating is profitable)
  5. SB not donk-betting river (can lead river as bluff with blockers)

DISTINCT FROM:
  blind_steal.py:         SB steal vs BB in general (not HU specific full guide)
  heads_up.py:            Full HU game strategy (not specifically BvB)
  bb_postflop.py:         BB postflop general (not BvB specific)
  THIS MODULE:            COMPLETE BvB GUIDE; SB opening range; BB defense range;
                          postflop dynamics by position; street-by-street adjustments.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple


SB_OPEN_RANGE_PCT: float = 0.52
BB_DEFENSE_PCT: float    = 0.60
BB_3BET_PCT: float       = 0.16
BB_FOLD_PCT: float       = 1.0 - BB_DEFENSE_PCT

SB_CBET_FREQ: Dict[str, float] = {
    'dry':       0.65,
    'semi_wet':  0.58,
    'wet':       0.48,
    'monotone':  0.42,
    'paired':    0.55,
}

BB_FLOAT_FREQ: Dict[str, float] = {
    'dry':       0.20,
    'semi_wet':  0.28,
    'wet':       0.38,
    'monotone':  0.35,
    'paired':    0.22,
}

BB_CHECKBACK_FREQ: Dict[str, float] = {
    'dry':       0.45,
    'semi_wet':  0.38,
    'wet':       0.30,
    'monotone':  0.28,
    'paired':    0.40,
}

SB_HAND_VALUE: Dict[str, float] = {
    'nuts':           0.95,
    'strong_value':   0.82,
    'top_pair_gk':    0.68,
    'top_pair_wk':    0.55,
    'middle_pair':    0.42,
    'air_with_draw':  0.38,
    'air':            0.15,
}

BB_POSITION_PREMIUM_BB100: float = 8.0


def _sb_action(
    hero_hand_pct: float,
    stack_bb: float,
) -> Tuple[str, float]:
    """Return (preflop_action, open_size_bb)."""
    if stack_bb <= 15:
        if hero_hand_pct >= 0.55:
            return 'PUSH_ALL_IN', stack_bb
        return 'FOLD', 0.0
    open_size = 3.0 if stack_bb > 25 else 2.5
    if hero_hand_pct >= 0.10:
        return 'OPEN_RAISE', open_size
    return 'FOLD', 0.0


def _bb_response(
    villain_size_bb: float,
    pot_bb: float,
    hero_hand_pct: float,
) -> str:
    if hero_hand_pct >= 0.82:
        return '3BET_VALUE'
    elif hero_hand_pct >= 0.70:
        return '3BET_LIGHT'
    elif hero_hand_pct >= 0.40:
        return 'CALL_DEFEND'
    elif hero_hand_pct >= 0.22:
        return 'CALL_SPECULATIVE'
    return 'FOLD'


def _sb_postflop_action(
    hero_hand_pct: float,
    board_texture: str,
    street: str,
    spr: float,
) -> str:
    cbet_threshold = SB_CBET_FREQ.get(board_texture, 0.55)
    hand_val = SB_HAND_VALUE.get(
        'top_pair_gk' if hero_hand_pct >= 0.60 else
        'middle_pair' if hero_hand_pct >= 0.40 else 'air',
        0.40
    )
    if spr <= 2.0:
        return 'BET_COMMIT'
    if hero_hand_pct >= 0.85:
        return 'BET_VALUE' if street == 'river' else 'BET_OR_CHECK_TRAP'
    if hero_hand_pct >= cbet_threshold:
        return 'BET_CBET'
    if hero_hand_pct >= 0.38:
        return 'CHECK_CALL'
    return 'CHECK_FOLD'


def _bb_postflop_action(
    hero_hand_pct: float,
    board_texture: str,
    villain_bet: bool,
    street: str,
) -> str:
    float_threshold = BB_FLOAT_FREQ.get(board_texture, 0.28)
    if villain_bet:
        if hero_hand_pct >= 0.80:
            return 'RAISE_VALUE'
        if hero_hand_pct >= 0.55:
            return 'CALL_STRONG'
        if hero_hand_pct >= float_threshold:
            return 'CALL_FLOAT'
        return 'FOLD'
    else:
        checkback_threshold = 1.0 - BB_CHECKBACK_FREQ.get(board_texture, 0.38)
        if hero_hand_pct >= 0.70:
            return 'BET_VALUE'
        if hero_hand_pct >= checkback_threshold:
            return 'BET_STAB'
        return 'CHECK_BACK'


@dataclass
class BvBStrategyResult:
    hero_role: str
    hero_hand_pct: float
    board_texture: str
    street: str
    stack_bb: float
    spr: float

    preflop_action: str
    postflop_action: str

    sb_cbet_freq: float
    bb_float_freq: float
    bb_position_premium: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_blind_vs_blind(
    hero_role: str = 'sb',
    hero_hand_pct: float = 0.60,
    board_texture: str = 'semi_wet',
    street: str = 'flop',
    stack_bb: float = 100.0,
    spr: float = 6.0,
    villain_bet: bool = False,
    villain_size_bb: float = 3.0,
    pot_bb: float = 6.0,
) -> BvBStrategyResult:
    """
    Provide complete SB vs BB strategy guidance.

    Args:
        hero_role:      'sb' or 'bb'
        hero_hand_pct:  Hero's hand percentile (0-1; 1=best)
        board_texture:  Board texture ('dry','semi_wet','wet','monotone','paired')
        street:         Current street ('preflop','flop','turn','river')
        stack_bb:       Effective stack in BB
        spr:            Stack-to-pot ratio (postflop)
        villain_bet:    Whether villain has bet (for postflop decisions)
        villain_size_bb: Villain's bet/raise size in BB
        pot_bb:         Current pot in BB

    Returns:
        BvBStrategyResult
    """
    role = hero_role.lower()

    if street == 'preflop':
        if role == 'sb':
            pf_action, _ = _sb_action(hero_hand_pct, stack_bb)
        else:
            pf_action = _bb_response(villain_size_bb, pot_bb, hero_hand_pct)
        post_action = 'N/A'
    else:
        pf_action = 'N/A'
        if role == 'sb':
            post_action = _sb_postflop_action(
                hero_hand_pct, board_texture, street, spr)
        else:
            post_action = _bb_postflop_action(
                hero_hand_pct, board_texture, villain_bet, street)

    sb_cbet  = SB_CBET_FREQ.get(board_texture, 0.55)
    bb_float = BB_FLOAT_FREQ.get(board_texture, 0.28)

    action_str = pf_action if street == 'preflop' else post_action
    verdict = (
        f'[BVB {role.upper()}|{street}|{board_texture}] '
        f'{action_str} hand={hero_hand_pct:.0%} '
        f'spr={spr:.1f} stack={stack_bb:.0f}BB'
    )

    reasoning = (
        f'Blind vs Blind ({role.upper()} side). '
        f'Hand={hero_hand_pct:.0%} on {board_texture} {street}. '
        f'SPR={spr:.1f}. '
        f'SB c-bet freq={sb_cbet:.0%}; BB float freq={bb_float:.0%}. '
        f'Action: {action_str}.'
    )

    tips = []

    tips.append(
        f'BVB POSITION DYNAMICS: SB opens {SB_OPEN_RANGE_PCT:.0%} of hands preflop but is OOP postflop. '
        f'BB defends {BB_DEFENSE_PCT:.0%} with position advantage worth +{BB_POSITION_PREMIUM_BB100:.1f}BB/100. '
        f'This is the most common HU spot -- study these ranges carefully.'
    )

    if role == 'sb':
        tips.append(
            f'AS SB (OOP): C-bet {sb_cbet:.0%} on {board_texture} boards. '
            f'Check-fold more than normal (OOP disadvantage). '
            f'Trap with strong hands sometimes to protect check range.'
        )
        if hero_hand_pct >= 0.80 and street in ('flop', 'turn'):
            tips.append(
                f'STRONG HAND (SB): Consider check-trap {hero_hand_pct:.0%} pct hand. '
                f'If you always bet strong hands, BB can over-fold to your bets. '
                f'Mix check/bet ~30/70 with value hands on {board_texture}.'
            )
        elif hero_hand_pct < 0.35 and street != 'preflop':
            tips.append(
                f'WEAK HAND (SB): {hero_hand_pct:.0%} pct hand -- lean toward CHECK-FOLD. '
                f'OOP bluffing is expensive; only bluff with strong blockers on river.'
            )
    else:
        tips.append(
            f'AS BB (IP): Float {bb_float:.0%} with position on {board_texture}. '
            f'Check back {BB_CHECKBACK_FREQ.get(board_texture, 0.38):.0%} to protect your range. '
            f'Stab turn/river when SB shows weakness (checks twice).'
        )
        if not villain_bet and street in ('flop', 'turn'):
            tips.append(
                f'SB CHECKED TO YOU (BB): Bet for value/stab {(1-BB_CHECKBACK_FREQ.get(board_texture,0.38)):.0%} of the time. '
                f'SB check range includes many weak hands -- exploit with stabs. '
                f'But protect range by checking back {BB_CHECKBACK_FREQ.get(board_texture, 0.38):.0%} including some strong hands.'
            )

    tips.append(
        f'COMMON MISTAKES: SB limping too much (loses position value); '
        f'BB over-3betting (SB range is wide -- need real value); '
        f'SB c-betting every hand OOP (range too wide postflop).'
    )

    return BvBStrategyResult(
        hero_role=role,
        hero_hand_pct=hero_hand_pct,
        board_texture=board_texture,
        street=street,
        stack_bb=stack_bb,
        spr=spr,
        preflop_action=pf_action,
        postflop_action=post_action,
        sb_cbet_freq=sb_cbet,
        bb_float_freq=bb_float,
        bb_position_premium=BB_POSITION_PREMIUM_BB100,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bvb_one_liner(r: BvBStrategyResult) -> str:
    action = r.preflop_action if r.preflop_action != 'N/A' else r.postflop_action
    return (
        f'[BVB {r.hero_role.upper()}|{r.street}|{r.board_texture}] '
        f'{action} hand={r.hero_hand_pct:.0%} '
        f'cbet={r.sb_cbet_freq:.0%} float={r.bb_float_freq:.0%}'
    )
