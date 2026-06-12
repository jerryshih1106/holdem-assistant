"""
Leverage Pressure Guide (leverage_pressure_guide.py)

Leverage = remaining_stack / pot. When SPR is high, each bet on an early
street implies a large future bet (the threat), multiplying fold equity.
When SPR is low, there is no future threat -- hands must be resolved now.

THEORY:
  LEVERAGE DEFINITION:
  Leverage = effective_stack / current_pot (after any bet)
  - High SPR/leverage (>6): hero can threaten large river bets from small flop bets
  - Medium SPR (2-6): standard post-flop play; moderate leverage
  - Low SPR (<2): commit or fold; no future threat available

  HOW LEVERAGE WORKS:
  - On the flop, with 20x pot behind, a small bet says "I can bet 20x pot more"
  - Villain must consider calling flop, turn, AND river -- not just the current bet
  - This "implied threat" induces folds on early streets beyond the immediate pot odds
  - High leverage => bluffs require less hand strength; smaller bet => large threat

  LEVERAGE AND BET SIZING:
  - High leverage: bet smaller early (threat does the work), larger later
  - Low leverage: bet larger now (last chance to extract before commitment)
  - Overbetting is leveraged on earlier streets only when stack is deep

  LEVERAGE AND BLUFFING:
  - Leverage bonus: how much fold equity you gain from implied threat
  - Very high leverage (+18%): villain is aware of future streets; folds more now
  - Low leverage (-10%): no future bets implied; villain calls with any equity

  LEVERAGE AND BOARD TEXTURE:
  - Wet board: leverage matters MORE (villain draws improve if they call)
  - Dry board: leverage matters LESS (villain's equity static)
  - Draw-heavy: large bets = protection + leverage threat

DISTINCT FROM:
  bet_sizing.py:          General bet sizing guide
  pot_geometry_planner.py: Multi-street pot planning
  implied_odds_positional_adjustment.py: Implied odds for drawing hands
  THIS MODULE:            LEVERAGE PRESSURE specifically; SPR->fold-equity bonus;
                          recommended sizing by leverage zone and street.
"""

from dataclasses import dataclass, field
from typing import List


LEVERAGE_ZONES: dict = {
    'low':       (0.0, 2.0),
    'medium':    (2.0, 6.0),
    'high':      (6.0, 15.0),
    'very_high': (15.0, 9999.0),
}

LEVERAGE_FOLD_BONUS: dict = {
    'very_high': 0.18,
    'high':      0.10,
    'medium':    0.04,
    'low':       0.00,
}

LEVERAGE_BLUFF_ADJUSTMENT: dict = {
    'very_high': +0.15,
    'high':      +0.08,
    'medium':    +0.02,
    'low':       -0.10,
}

LEVERAGE_SIZING: dict = {
    'very_high': {'flop': 0.25, 'turn': 0.40, 'river': 0.70},
    'high':      {'flop': 0.33, 'turn': 0.55, 'river': 0.80},
    'medium':    {'flop': 0.50, 'turn': 0.67, 'river': 0.90},
    'low':       {'flop': 0.75, 'turn': 0.90, 'river': 1.00},
}

VILLAIN_LEVERAGE_SENSITIVITY: dict = {
    'fish':            0.60,
    'calling_station': 0.50,
    'rec':             0.80,
    'nit':             1.30,
    'lag':             0.85,
    'reg':             1.00,
}

BOARD_LEVERAGE_MULTIPLIER: dict = {
    'dry':      0.80,
    'semi_wet': 1.00,
    'wet':      1.20,
    'monotone': 1.30,
    'paired':   0.90,
}


def _spr_zone(spr: float) -> str:
    for zone, (lo, hi) in LEVERAGE_ZONES.items():
        if lo <= spr < hi:
            return zone
    return 'very_high'


def _fold_equity_with_leverage(
    base_fold_pct: float,
    spr_zone: str,
    villain_type: str,
    board_texture: str,
) -> float:
    bonus = LEVERAGE_FOLD_BONUS[spr_zone]
    vil_sens = VILLAIN_LEVERAGE_SENSITIVITY.get(villain_type, 1.00)
    board_mult = BOARD_LEVERAGE_MULTIPLIER.get(board_texture, 1.00)
    adjusted_bonus = bonus * vil_sens * board_mult
    return round(min(0.95, base_fold_pct + adjusted_bonus), 3)


def _recommended_sizing(spr_zone: str, street: str) -> float:
    sizes = LEVERAGE_SIZING.get(spr_zone, LEVERAGE_SIZING['medium'])
    return sizes.get(street, 0.60)


def _leverage_action(
    spr_zone: str,
    hand_pct: float,
    street: str,
    fold_equity: float,
) -> str:
    if spr_zone == 'low':
        if hand_pct >= 0.65:
            return 'BET_COMMIT_VALUE'
        elif hand_pct >= 0.45:
            return 'CALL_OR_FOLD_NO_LEVERAGE'
        else:
            return 'FOLD_NO_FUTURE_STREETS'

    if spr_zone in ('high', 'very_high') and fold_equity >= 0.55:
        return 'BET_SMALL_LEVERAGE_THREAT'

    if hand_pct >= 0.70:
        return 'BET_VALUE_LEVERAGE_SIZING'
    elif hand_pct >= 0.45 and fold_equity >= 0.45:
        return 'BET_BLUFF_LEVERAGE'
    elif hand_pct >= 0.45:
        return 'CHECK_CALL_MEDIUM_HAND'
    else:
        return 'CHECK_FOLD_WEAK'


@dataclass
class LeveragePressureResult:
    spr: float
    street: str
    villain_type: str
    board_texture: str
    hand_pct: float

    spr_zone: str
    fold_bonus: float
    total_fold_equity: float
    recommended_sizing: float
    bluff_adjustment: float
    action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_leverage_pressure(
    spr: float = 8.0,
    street: str = 'flop',
    hand_pct: float = 0.60,
    base_fold_pct: float = 0.40,
    villain_type: str = 'reg',
    board_texture: str = 'semi_wet',
) -> LeveragePressureResult:
    """
    Quantify leverage pressure and recommend bet sizing by SPR zone.

    Args:
        spr:            Stack-to-pot ratio (remaining stack / pot)
        street:         Current street ('flop','turn','river')
        hand_pct:       Hero hand percentile (0-1)
        base_fold_pct:  Base fold equity before leverage adjustment (0-1)
        villain_type:   Villain type ('fish','rec','nit','lag','reg')
        board_texture:  Board texture ('dry','semi_wet','wet','monotone','paired')

    Returns:
        LeveragePressureResult
    """
    zone = _spr_zone(spr)
    fold_eq = _fold_equity_with_leverage(base_fold_pct, zone, villain_type, board_texture)
    sizing = _recommended_sizing(zone, street)
    bluff_adj = LEVERAGE_BLUFF_ADJUSTMENT[zone]
    action = _leverage_action(zone, hand_pct, street, fold_eq)
    fold_bonus = LEVERAGE_FOLD_BONUS[zone]

    verdict = (
        f'[LEV spr={spr:.1f}|{zone}|{street}] '
        f'fold_eq={fold_eq:.0%} sizing={sizing:.0%}pot action={action}'
    )

    reasoning = (
        f'Leverage pressure: SPR={spr:.1f} ({zone} zone) on {street}. '
        f'Villain={villain_type}, board={board_texture}. '
        f'Fold bonus from leverage={fold_bonus:.0%}; '
        f'total fold equity={fold_eq:.0%}. '
        f'Recommended sizing={sizing:.0%}pot. '
        f'Bluff freq adjustment={bluff_adj:+.0%}. '
        f'Action: {action}.'
    )

    tips = []

    tips.append(
        f'LEVERAGE (SPR={spr:.1f}, {zone.upper()} zone): '
        f'{"Deep stacks -- use small bets early; threat of future streets does the work." if zone == "very_high" else "High leverage -- moderate sizing; future bet threats still relevant." if zone == "high" else "Standard leverage -- balanced sizing." if zone == "medium" else "Low SPR -- no future leverage; bet to commit or check-fold."}'
    )

    tips.append(
        f'FOLD EQUITY: base={base_fold_pct:.0%} + leverage bonus={fold_bonus:.0%} = {fold_eq:.0%} total. '
        f'Recommended {street} sizing: {sizing:.0%} pot. '
        f'{"Villain sensitivity HIGH to leverage." if VILLAIN_LEVERAGE_SENSITIVITY.get(villain_type, 1.0) >= 1.20 else "Villain sensitivity LOW -- leverage less effective." if VILLAIN_LEVERAGE_SENSITIVITY.get(villain_type, 1.0) <= 0.70 else "Villain responds normally to leverage pressure."}'
    )

    if zone in ('high', 'very_high'):
        tips.append(
            f'HIGH LEVERAGE STRATEGY: Bet {sizing:.0%} pot on {street} to set up future barrels. '
            f'With SPR={spr:.1f}, you can fire {sizing:.0%} flop + larger turn + large river. '
            f'Villain must factor ALL future streets when deciding to call the {street}.'
        )

    if bluff_adj >= 0.05:
        tips.append(
            f'BLUFF FREQUENCY: Increase bluffs by {bluff_adj:+.0%} due to high leverage. '
            f'High SPR amplifies fold equity of bluffs -- small bet implies large future threat. '
            f'Use hands with equity + good blockers for leverage bluffs.'
        )
    elif bluff_adj <= -0.05:
        tips.append(
            f'BLUFF FREQUENCY: Decrease bluffs by {bluff_adj:.0%} due to low SPR. '
            f'Without leverage, villain calls with any equity -- bluffs less effective. '
            f'Focus on value betting; check-fold weak hands.'
        )

    return LeveragePressureResult(
        spr=spr,
        street=street,
        villain_type=villain_type,
        board_texture=board_texture,
        hand_pct=hand_pct,
        spr_zone=zone,
        fold_bonus=fold_bonus,
        total_fold_equity=fold_eq,
        recommended_sizing=sizing,
        bluff_adjustment=bluff_adj,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def lev_one_liner(r: LeveragePressureResult) -> str:
    return (
        f'[LEV spr={r.spr:.1f}|{r.spr_zone}|{r.street}] '
        f'fold_eq={r.total_fold_equity:.0%} sizing={r.recommended_sizing:.0%}pot'
    )
