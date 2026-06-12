"""
Fold Frequency Calibrator (fold_frequency_calibrator.py)

Calibrates hero's fold frequency to various bet types and sizes.
Over-folding lets villains bluff profitably; under-folding lets them
value bet too wide. This module identifies which direction hero deviates
and quantifies the EV cost.

GTO FOLD FREQUENCY:
  For any bet size b into pot P:
    alpha = b / (P + b)      [villain's break-even fold rate]
    MDF   = 1 - alpha        [hero's minimum defense frequency]

  If hero folds MORE than alpha -> villain profits by bluffing any two cards
  If hero folds LESS than alpha -> villain profits by only betting value

  EXAMPLE:
    Villain bets 50% pot: alpha = 0.33, MDF = 0.67
    If hero folds 60% -> villain can bluff any two cards profitably
    If hero folds 20% -> villain should never bluff; only bet top pair+

FOLD CALIBRATION BY SPOT:
  Common spots to calibrate:
  1. Fold to flop c-bet:     GTO varies 35-55% by position/texture
  2. Fold to turn barrel:    GTO ~40-55%
  3. Fold to river bet:      Varies by size; PSB=33% fold, 50%pot=40% fold
  4. Fold to 3-bet:          GTO ~50-60% (position-dependent)
  5. Fold to check-raise:    GTO ~45-55%

DISTINCT FROM:
  calldown_advisor.py:       Per-hand calldown decision
  session_leak_prioritizer.py: Session-level leak analysis
  THIS MODULE:               Real-time fold frequency calibration;
                             how much to fold vs specific bet sizes;
                             which hand categories to continue vs fold

Usage:
    from poker.fold_frequency_calibrator import calibrate_fold_frequency, FoldCalibration, ffc_one_liner

    result = calibrate_fold_frequency(
        spot_type='fold_to_cbet',
        bet_size_pct=0.50,
        street='flop',
        hero_fold_pct=0.65,
        board_texture='dry',
        hero_position='oop',
        villain_vpip=0.30,
        villain_af=2.5,
        pot_bb=20.0,
    )
    print(ffc_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# GTO fold rates by spot type and street (base values before size adjustment)
GTO_FOLD_BASE = {
    'fold_to_cbet':      {'flop': 0.50, 'turn': 0.48, 'river': 0.45},
    'fold_to_3bet':      {'preflop': 0.55},
    'fold_to_check_raise': {'flop': 0.45, 'turn': 0.50, 'river': 0.48},
    'fold_to_barrel':    {'turn': 0.48, 'river': 0.42},
    'fold_to_river_bet': {'river': 0.42},
    'fold_to_donk':      {'flop': 0.40, 'turn': 0.42, 'river': 0.45},
    'fold_to_probe':     {'turn': 0.45, 'river': 0.48},
}

# EV cost per 10% over-fold (BB/100)
EV_COST_PER_10PCT_OVERFOLD = {
    'fold_to_cbet':      1.5,
    'fold_to_3bet':      2.0,
    'fold_to_check_raise': 1.2,
    'fold_to_barrel':    1.3,
    'fold_to_river_bet': 1.6,
    'fold_to_donk':      1.0,
    'fold_to_probe':     0.8,
}

# What hands to continue vs over-folding
CONTINUE_HANDS = {
    'fold_to_cbet': {
        'dry':     ['top_pair', 'overpair', 'flush_draw', 'two_pair+', 'middle_pair+IP'],
        'wet':     ['top_pair', 'overpair', 'two_pair+', 'flush_draw', 'oesd', 'combo_draw'],
        'default': ['top_pair', 'overpair', 'draw', 'two_pair+'],
    },
    'fold_to_river_bet': {
        'default': ['top_pair_good_kicker', 'overpair', 'two_pair+', 'hands_with_blocker'],
    },
    'fold_to_3bet': {
        'default': ['JJ+', 'AK', 'AQ_IP', 'suited_connectors_IP'],
    },
}


def _alpha(bet_size_pct: float) -> float:
    """Villain's break-even fold rate = alpha = bet/(pot+bet)."""
    return round(bet_size_pct / (1.0 + bet_size_pct), 4)


def _gto_fold_rate(spot_type: str, street: str, bet_size_pct: float) -> float:
    """GTO fold rate for this spot, adjusted for bet size."""
    base_map = GTO_FOLD_BASE.get(spot_type, {})
    base = base_map.get(street, 0.50)
    # Adjust base by bet size: larger bet → more folding is correct
    size_adj = (bet_size_pct - 0.50) * 0.15   # 10% per 1.0 pot difference
    return round(min(0.75, max(0.20, base + size_adj)), 4)


def _deviation_direction(hero_fold: float, gto_fold: float) -> str:
    dev = hero_fold - gto_fold
    if abs(dev) <= 0.04:
        return 'calibrated'
    elif dev > 0:
        return 'over_folding'
    else:
        return 'under_folding'


def _ev_cost(spot_type: str, hero_fold: float, gto_fold: float, pot_bb: float) -> float:
    """EV cost of fold frequency deviation."""
    dev = abs(hero_fold - gto_fold)
    if dev < 0.04:
        return 0.0
    rate = EV_COST_PER_10PCT_OVERFOLD.get(spot_type, 1.2)
    cost = (dev * 100 / 10) * rate
    # Scale slightly by pot size
    pot_scale = (pot_bb / 20.0) ** 0.4
    return round(cost * pot_scale, 2)


def _position_adjustment(hero_position: str, spot_type: str) -> float:
    """Position adjustment to GTO fold rate."""
    if hero_position in ('oop', 'sb', 'bb'):
        return 0.03   # OOP should fold slightly more
    elif hero_position in ('ip', 'btn', 'co'):
        return -0.03  # IP can fold less (position EV)
    return 0.0


def _texture_adjustment(board_texture: str, spot_type: str) -> float:
    """Texture adjustment."""
    if board_texture in ('wet', 'monotone'):
        return -0.05  # Wet board: c-bets are stronger; should fold less on draws
    elif board_texture == 'dry':
        return 0.03   # Dry board: c-bets are sometimes wider; can fold more air
    return 0.0


def _continue_hands(spot_type: str, board_texture: str, hero_position: str) -> List[str]:
    """Hands that should continue (not fold) vs this spot type."""
    hands_map = CONTINUE_HANDS.get(spot_type, {})
    texture_key = board_texture if board_texture in hands_map else 'default'
    hands = hands_map.get(texture_key, hands_map.get('default', ['top_pair', 'better']))

    # Add IP-specific hands
    if hero_position in ('ip', 'btn', 'co'):
        hands = list(hands) + ['middle_pair_IP', 'flush_draw_IP']

    return hands


@dataclass
class FoldCalibration:
    # Inputs
    spot_type: str
    bet_size_pct: float
    street: str
    hero_fold_pct: float
    board_texture: str
    hero_position: str
    villain_vpip: float
    villain_af: float
    pot_bb: float

    # Analysis
    alpha: float                  # villain's break-even fold rate
    mdf: float                    # minimum defense frequency
    gto_fold_rate: float          # adjusted GTO fold rate for this spot
    deviation: float              # hero_fold - gto_fold (positive = over-folding)
    direction: str                # 'over_folding' / 'under_folding' / 'calibrated'
    ev_cost_bb_100: float         # EV cost of deviation
    continue_hands: List[str]     # hands that should continue

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calibrate_fold_frequency(
    spot_type: str = 'fold_to_cbet',
    bet_size_pct: float = 0.50,
    street: str = 'flop',
    hero_fold_pct: float = 0.65,
    board_texture: str = 'dry',
    hero_position: str = 'oop',
    villain_vpip: float = 0.30,
    villain_af: float = 2.5,
    pot_bb: float = 20.0,
) -> FoldCalibration:
    """
    Calibrate hero's fold frequency to a specific bet type.

    Args:
        spot_type:      'fold_to_cbet' / 'fold_to_3bet' / 'fold_to_barrel' /
                        'fold_to_river_bet' / 'fold_to_check_raise' / 'fold_to_donk'
        bet_size_pct:   Villain's bet as fraction of pot (0.33, 0.50, 0.75, 1.00)
        street:         'preflop' / 'flop' / 'turn' / 'river'
        hero_fold_pct:  Hero's observed fold frequency (0-1)
        board_texture:  'dry' / 'semi_wet' / 'wet' / 'paired' / 'monotone'
        hero_position:  'ip' / 'oop' / 'btn' / 'bb' etc.
        villain_vpip/af: HUD stats
        pot_bb:         Current pot

    Returns:
        FoldCalibration
    """
    a = _alpha(bet_size_pct)
    mdf = round(1.0 - a, 4)

    pos_adj = _position_adjustment(hero_position, spot_type)
    tex_adj = _texture_adjustment(board_texture, spot_type)
    gto = _gto_fold_rate(spot_type, street, bet_size_pct)
    gto_adj = round(min(0.75, max(0.20, gto + pos_adj + tex_adj)), 4)

    deviation = round(hero_fold_pct - gto_adj, 4)
    direction = _deviation_direction(hero_fold_pct, gto_adj)
    ev_cost = _ev_cost(spot_type, hero_fold_pct, gto_adj, pot_bb)
    cont_hands = _continue_hands(spot_type, board_texture, hero_position)

    reasoning = (
        f'Fold calibration: {spot_type} on {street}. '
        f'Bet={bet_size_pct:.0%}pot. Alpha={a:.0%} MDF={mdf:.0%}. '
        f'GTO fold={gto_adj:.0%} (base={gto:.0%} pos_adj={pos_adj:+.0%} tex_adj={tex_adj:+.0%}). '
        f'Hero fold={hero_fold_pct:.0%}. Deviation={deviation:+.0%} ({direction}). '
        f'EV cost={ev_cost:.1f} BB/100.'
    )

    verdict = (
        f'[FFC {spot_type}|{street}|{direction.upper()}] '
        f'hero={hero_fold_pct:.0%} gto={gto_adj:.0%} dev={deviation:+.0%} | '
        f'ev_cost={ev_cost:.1f}BB/100 mdf={mdf:.0%}'
    )

    tips = []

    if direction == 'over_folding':
        tips.append(
            f'OVER-FOLDING by {deviation:.0%}: Continue more hands. '
            f'Villain profits by bluffing any two cards when you fold {hero_fold_pct:.0%}. '
            f'GTO fold = {gto_adj:.0%}. Hands to continue: {", ".join(cont_hands[:5])}.'
        )
        tips.append(
            f'ALPHA REMINDER: Bet={bet_size_pct:.0%}pot requires villain to fold {a:.0%} for bluff to break even. '
            f'MDF = {mdf:.0%}. You must defend AT LEAST {mdf:.0%} of range. '
            f'Currently defending only {1-hero_fold_pct:.0%} -- villain is printing money bluffing.'
        )
    elif direction == 'under_folding':
        tips.append(
            f'UNDER-FOLDING by {abs(deviation):.0%}: Fold more marginal hands. '
            f'Villain profits by value betting too wide when you call {1-hero_fold_pct:.0%} of range. '
            f'GTO fold = {gto_adj:.0%}. Reduce calls with: bottom pair, weak kicker hands, no equity.'
        )
    else:
        tips.append(
            f'CALIBRATED: Fold frequency {hero_fold_pct:.0%} is near GTO {gto_adj:.0%}. '
            f'Villain cannot profitably deviate. Maintain this defense frequency.'
        )

    tips.append(
        f'SPOT CONTEXT: {spot_type.replace("_", " ")} on {board_texture} {street}. '
        f'Position: {hero_position.upper()}. '
        f'EV cost of deviation: {ev_cost:.1f} BB/100. '
        f'Continue: {", ".join(cont_hands[:4])}.'
    )

    if villain_af >= 3.0:
        tips.append(
            f'HIGH AF VILLAIN (AF={villain_af:.1f}): Villain bets frequently -- lots of bluffs. '
            f'DEFEND MORE. Tighten your fold frequency toward the lower end of GTO range. '
            f'Consider folding {max(0.30, gto_adj - 0.08):.0%} instead of {gto_adj:.0%}.'
        )
    elif villain_af <= 1.5:
        tips.append(
            f'PASSIVE VILLAIN (AF={villain_af:.1f}): Villain rarely bluffs. '
            f'FOLD MORE vs this player. Tighten toward upper end of GTO fold range. '
            f'Consider folding {min(0.70, gto_adj + 0.08):.0%} instead of {gto_adj:.0%}.'
        )

    return FoldCalibration(
        spot_type=spot_type,
        bet_size_pct=bet_size_pct,
        street=street,
        hero_fold_pct=hero_fold_pct,
        board_texture=board_texture,
        hero_position=hero_position,
        villain_vpip=villain_vpip,
        villain_af=villain_af,
        pot_bb=pot_bb,
        alpha=a,
        mdf=mdf,
        gto_fold_rate=gto_adj,
        deviation=deviation,
        direction=direction,
        ev_cost_bb_100=ev_cost,
        continue_hands=cont_hands,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ffc_one_liner(r: FoldCalibration) -> str:
    return (
        f'[FFC {r.spot_type}|{r.street}|{r.direction.upper()}] '
        f'hero={r.hero_fold_pct:.0%} gto={r.gto_fold_rate:.0%} dev={r.deviation:+.0%} | '
        f'ev_cost={r.ev_cost_bb_100:.1f}BB/100 mdf={r.mdf:.0%}'
    )
