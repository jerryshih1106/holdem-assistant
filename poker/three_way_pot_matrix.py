"""
Three-Way Pot Matrix (three_way_pot_matrix.py)

Provides a comprehensive decision matrix for 3-way pot scenarios.
When 3 players see the flop (e.g., EP opens, BTN calls, BB defends),
strategy changes dramatically vs heads-up:

KEY 3-WAY DYNAMICS:
  1. RANGE COMPRESSION: Must have stronger hands to bet/call in 3-way pots.
     A top pair that would be strong HU is often just a bluff-catcher 3-way.
  2. REDUCED BLUFFING: Need to be profitable vs TWO callers.
     GTO c-bet frequency drops to ~35-45% in 3-way vs ~55-65% HU.
  3. PLAYER ORDERING: PFR (EP opener) bets first; IP player acts last.
     This changes check-raise dynamics significantly.
  4. BLOCKERS MATTER MORE: Blockers to nut draws are more valuable 3-way.
  5. PROTECTION BETS: Must charge TWO opponents' equity.

ROLE CLASSIFICATION:
  pfr:      Pre-flop raiser (acts first postflop, OOP)
  caller:   Called the open (usually IP)
  squeezee: Cold-called or BB defend (often weakest range)

C-BET FREQUENCY ADJUSTMENTS (3-way vs HU):
  Dry boards: 45% → 33% (both opponents have equity; capped hands fold more)
  Wet boards: 55% → 38% (too many draws; half the field has a draw)
  Paired boards: 40% → 28% (trips/boats in range; more check-raises)
  Monotone: 35% → 22% (flush draw hits one of them; equity very distributed)

DISTINCT FROM:
  multiway.py:           General multiway strategy (4+ players)
  pot_odds_advisor.py:   Individual pot odds
  THIS MODULE:           Specific 3-way decision matrix with role-based advice

Usage:
    from poker.three_way_pot_matrix import analyze_three_way, ThreeWayAdvice, twm_one_liner

    result = analyze_three_way(
        hero_role='pfr',
        hero_hand_category='top_pair',
        board_texture='dry',
        street='flop',
        pot_bb=9.0,
        hero_stack_bb=95.0,
        villain1_vpip=0.30,
        villain1_af=2.0,
        villain2_vpip=0.25,
        villain2_af=1.8,
        hero_position='oop',
    )
    print(twm_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# 3-way c-bet frequencies by board texture
GTO_CBET_3WAY = {
    'dry':       0.33,
    'semi_wet':  0.38,
    'wet':       0.38,
    'paired':    0.28,
    'monotone':  0.22,
}

# HU c-bet frequencies for comparison
GTO_CBET_HU = {
    'dry':       0.65,
    'semi_wet':  0.55,
    'wet':       0.55,
    'paired':    0.40,
    'monotone':  0.35,
}

# Required equity to continue in 3-way pot vs bet (call vs c-bet 33% pot)
# call_cost = 0.33 * pot; total = pot + 2*0.33*pot = 1.66*pot; req = 0.33/1.66 = ~0.20
# But 3-way: villain behind may also call, so effective equity required is higher
REQUIRED_EQUITY_3WAY_VS_33PCT = 0.22
REQUIRED_EQUITY_3WAY_VS_50PCT = 0.27
REQUIRED_EQUITY_3WAY_VS_67PCT = 0.31


def _pfr_hand_strength(hand_category: str, board_texture: str) -> str:
    """
    Rate hand strength for the PFR in a 3-way pot.
    Must be stronger than HU since facing 2 opponents.
    """
    if hand_category in ('set', 'two_pair', 'flush', 'straight', 'full_house'):
        return 'premium'
    elif hand_category in ('overpair', 'top_pair'):
        if board_texture in ('dry', 'paired'):
            return 'strong'      # HU would be very strong; 3-way just strong
        else:
            return 'medium'      # wet board: draws all around; overpair = medium
    elif hand_category in ('middle_pair', 'draw', 'flush_draw', 'straight_draw'):
        return 'medium'
    elif hand_category in ('weak_pair', 'bottom_pair', 'overcards'):
        return 'weak'
    else:
        return 'air'


def _cbet_recommendation(
    hero_role: str,
    hand_strength: str,
    board_texture: str,
    hero_position: str,
    v1_af: float,
    v2_af: float,
) -> tuple:
    """
    (should_cbet: bool, cbet_size_pct: float, frequency: float)
    """
    freq = GTO_CBET_3WAY.get(board_texture, 0.33)
    avg_af = (v1_af + v2_af) / 2

    # Only PFR cbets; callers donk/probe/float
    if hero_role != 'pfr':
        return False, 0.0, 0.0

    # Adjust for hand strength
    if hand_strength == 'premium':
        should = True
        size = 0.50   # bet big to protect + build pot
        freq = min(0.90, freq * 1.8)
    elif hand_strength == 'strong':
        should = True
        size = 0.40   # medium sizing in 3-way
        freq = min(0.70, freq * 1.3)
    elif hand_strength == 'medium':
        should = True
        size = 0.33   # range bet small
        freq = freq
    elif hand_strength == 'weak':
        should = True if board_texture == 'dry' else False
        size = 0.33
        freq = max(0.10, freq * 0.5)   # drastically reduce weak hands
    else:  # air
        should = False
        size = 0.33
        freq = max(0.05, freq * 0.3)   # rare pure bluffs in 3-way

    # If opponents are aggressive (high AF), reduce cbet freq (more check-raises)
    if avg_af >= 3.0:
        freq = max(0.15, freq * 0.75)
        size = max(0.33, size)   # bet bigger if they will raise anyway

    # OOP penalty
    if hero_position == 'oop':
        freq = max(0.10, freq * 0.88)

    return should, round(size, 2), round(freq, 3)


def _continue_vs_cbet(
    hero_role: str,
    hand_strength: str,
    board_texture: str,
    hero_position: str,
) -> tuple:
    """
    (action: str, reasoning: str) when facing a c-bet in 3-way pot.
    hero_role is 'caller' or 'squeezee'.
    """
    if hand_strength == 'premium':
        action = 'raise' if hero_position == 'ip' else 'check_raise'
        reasoning = 'Premium hand in 3-way: raise or check-raise for value and to price out draws.'
    elif hand_strength == 'strong':
        if board_texture in ('dry', 'paired'):
            action = 'call'
            reasoning = 'Strong hand on dry board: call to keep all worse hands in; raise on wet board.'
        else:
            action = 'call' if hero_role == 'caller' else 'raise'
            reasoning = 'Strong hand on wet board: protect against draws; raise if squeezee/IP.'
    elif hand_strength == 'medium':
        if board_texture in ('dry',):
            action = 'call'
            reasoning = 'Medium hand on dry board: call pot odds; fold if facing 2 bets.'
        else:
            action = 'fold' if hero_role == 'squeezee' else 'call'
            reasoning = 'Medium hand on wet board: squeezee folds; caller calls once with pot odds.'
    elif hand_strength == 'weak':
        action = 'fold'
        reasoning = 'Weak hand in 3-way: fold; break-even equity is too high vs two opponents.'
    else:  # air
        action = 'fold'
        reasoning = 'Air in 3-way: always fold vs c-bet unless very high fold equity raise opportunity.'

    return action, reasoning


def _multiway_equity_discount(hand_strength: str) -> float:
    """How much equity to discount in 3-way vs HU."""
    return {
        'premium': 0.0,    # Sets/straights: same equity multi-way (mostly)
        'strong':  0.10,   # TPTK: ~10% discount vs 2 opponents
        'medium':  0.18,   # Draws: ~18% discount (need to beat BOTH)
        'weak':    0.25,   # Weak pairs: very discounted
        'air':     0.30,
    }.get(hand_strength, 0.15)


@dataclass
class ThreeWayAdvice:
    # Inputs
    hero_role: str
    hero_hand_category: str
    board_texture: str
    street: str
    pot_bb: float
    hero_stack_bb: float
    hero_position: str

    # Analysis
    hand_strength: str          # 'premium' / 'strong' / 'medium' / 'weak' / 'air'
    equity_discount: float      # How much equity is reduced vs HU

    # C-bet (when PFR)
    should_cbet: bool
    cbet_size_pct: float
    cbet_size_bb: float
    cbet_frequency: float       # GTO cbet frequency for this spot
    hu_cbet_frequency: float    # For comparison

    # Response (when facing c-bet)
    response_action: str        # when NOT the PFR
    response_reasoning: str

    # Overall recommendation
    action: str
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_three_way(
    hero_role: str = 'pfr',
    hero_hand_category: str = 'top_pair',
    board_texture: str = 'dry',
    street: str = 'flop',
    pot_bb: float = 9.0,
    hero_stack_bb: float = 95.0,
    villain1_vpip: float = 0.30,
    villain1_af: float = 2.0,
    villain2_vpip: float = 0.25,
    villain2_af: float = 1.8,
    hero_position: str = 'oop',
) -> ThreeWayAdvice:
    """
    Comprehensive 3-way pot decision matrix.

    Args:
        hero_role:          'pfr' / 'caller' / 'squeezee'
        hero_hand_category: Hand category (top_pair, draw, set, etc.)
        board_texture:      'dry' / 'semi_wet' / 'wet' / 'paired' / 'monotone'
        street:             'flop' / 'turn' / 'river'
        pot_bb:             Current pot in BBs
        hero_stack_bb:      Hero's effective stack
        villain1_vpip/af:   Villain 1 (usually the IP player) stats
        villain2_vpip/af:   Villain 2 (usually the other caller) stats
        hero_position:      'ip' / 'oop'

    Returns:
        ThreeWayAdvice
    """
    hand_strength = _pfr_hand_strength(hero_hand_category, board_texture)
    eq_discount = _multiway_equity_discount(hand_strength)

    should_cbet, cbet_size, cbet_freq = _cbet_recommendation(
        hero_role, hand_strength, board_texture, hero_position, villain1_af, villain2_af
    )
    cbet_bb = round(cbet_size * pot_bb, 1)
    hu_freq = GTO_CBET_HU.get(board_texture, 0.55)

    response_action, response_reasoning = _continue_vs_cbet(
        hero_role, hand_strength, board_texture, hero_position
    )

    # Primary action
    if hero_role == 'pfr':
        if should_cbet and cbet_freq >= 0.30:
            action = f'cbet_{cbet_size:.0%}_pot'
            action_exp = (
                f'C-bet {cbet_bb:.1f}BB ({cbet_size:.0%} pot) at freq={cbet_freq:.0%}. '
                f'3-way GTO: {cbet_freq:.0%} vs HU {hu_freq:.0%}. '
                f'Hand strength: {hand_strength}.'
            )
        else:
            action = 'check'
            action_exp = (
                f'Check: 3-way c-bet freq too low for {hand_strength} hand on {board_texture} board. '
                f'GTO freq={cbet_freq:.0%}. Check-call or check-raise with strong hands.'
            )
    else:
        action = response_action
        action_exp = response_reasoning

    reasoning = (
        f'3-way pot: hero={hero_role} hand={hero_hand_category} ({hand_strength}) '
        f'board={board_texture} street={street}. '
        f'Equity discount vs HU: -{eq_discount:.0%}. '
        f'C-bet: freq={cbet_freq:.0%} (HU={hu_freq:.0%}) size={cbet_size:.0%} pot. '
        f'V1: VPIP={villain1_vpip:.0%} AF={villain1_af:.1f}. '
        f'V2: VPIP={villain2_vpip:.0%} AF={villain2_af:.1f}. '
        f'Action={action}.'
    )

    verdict = (
        f'[TWM {hero_role.upper()}|{hand_strength}|{board_texture}] '
        f'{action.upper()} | '
        f'cbet_freq={cbet_freq:.0%} (HU={hu_freq:.0%}) size={cbet_size:.0%}pot={cbet_bb:.1f}BB | '
        f'eq_discount=-{eq_discount:.0%}'
    )

    tips = [action_exp]

    tips.append(
        f'3-WAY C-BET REDUCTION: GTO c-bet frequency on {board_texture} board is {cbet_freq:.0%} '
        f'(vs {hu_freq:.0%} HU). Reduce c-betting because BOTH opponents need to fold '
        f'for the c-bet to win the pot outright; equity is distributed across 2 villains.'
    )

    if hand_strength == 'strong':
        tips.append(
            f'STRONG HAND 3-WAY: {hero_hand_category} is "strong" in 3-way context -- '
            f'TPTK/overpair is no longer the nuts. Bet for value but be prepared to '
            f'fold to 2 streets of aggression from both villains simultaneously.'
        )

    avg_af = (villain1_af + villain2_af) / 2
    if avg_af >= 2.8:
        tips.append(
            f'AGGRESSIVE TABLE: Avg villain AF={avg_af:.1f}. In 3-way pots, '
            f'aggressive opponents will squeeze and check-raise more. '
            f'Bet/fold more; call-down is very dangerous with medium hands.'
        )

    if board_texture == 'wet':
        tips.append(
            f'WET BOARD 3-WAY: With 2 opponents, at least one likely has a draw. '
            f'Bet to PROTECT your made hands; do not give free cards. '
            f'Reduce pure bluffs (too many callers); bet your best hands and nut draws.'
        )

    return ThreeWayAdvice(
        hero_role=hero_role,
        hero_hand_category=hero_hand_category,
        board_texture=board_texture,
        street=street,
        pot_bb=pot_bb,
        hero_stack_bb=hero_stack_bb,
        hero_position=hero_position,
        hand_strength=hand_strength,
        equity_discount=eq_discount,
        should_cbet=should_cbet,
        cbet_size_pct=cbet_size,
        cbet_size_bb=cbet_bb,
        cbet_frequency=cbet_freq,
        hu_cbet_frequency=hu_freq,
        response_action=response_action,
        response_reasoning=response_reasoning,
        action=action,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def twm_one_liner(r: ThreeWayAdvice) -> str:
    return (
        f'[TWM {r.hero_role.upper()}|{r.hand_strength}|{r.board_texture}] '
        f'{r.action.upper()} | '
        f'cbet={r.cbet_frequency:.0%} vs HU={r.hu_cbet_frequency:.0%} | '
        f'eq_discount=-{r.equity_discount:.0%}'
    )
