"""
Pot Control Sizing Guide (pot_control_sizing_guide.py)

Determines when and how to size bets to control pot size with medium-strength
hands that want to see cheap showdowns rather than build large pots.

THEORY:
  POT CONTROL DEFINITION:
  Keeping pot small with medium-strength hands to avoid difficult large-pot
  decisions on later streets. Preferred when:
  - Hand SDV is 0.40-0.65 (medium pair, two pair on wet board)
  - SPR is high (deep stacks; large pots become costly)
  - Board is wet (many hands that beat medium pairs)
  - OOP (position disadvantage makes large pots costly)

  WHEN TO POT CONTROL vs BET:
  Prefer pot control: medium pair (SDV 0.40-0.60) on wet/connected board
  Prefer betting: dry board or very strong hand (SDV > 0.70)
  Prefer small bet: when betting for protection but not value

  POT CONTROL SIZING:
  Check back (0%): IP with medium pair; deny free equity while keeping pot small
  Mini-bet (20-25%): OOP medium pair; small enough to keep pot controlled
  Small bet (28-35%): thin value + pot control; forces villain to define hand

  STACK DEPTH IMPACT:
  Deep stacks (SPR > 10): aggressive pot control; medium pairs cannot afford
    to build large pots they cannot win at showdown
  Shallow stacks (SPR < 3): pot control less important; almost committed

  POSITION IMPACT:
  IP: check back is primary pot control tool (free showdown if checked through)
  OOP: must bet small or check-call; large OOP bets invite raises/floats

DISTINCT FROM:
  pot_control_advisor.py: Whether to pot control or not (yes/no)
  bet_sizing.py:          General bet sizing
  THIS MODULE:            HOW TO SIZE when pot-controlling; bet/check decision;
                          SPR and street-based sizing for medium-strength hands.
"""

from dataclasses import dataclass, field
from typing import List

POT_CONTROL_TRIGGER_SDV_RANGE = (0.35, 0.68)
POT_CONTROL_SPR_THRESHOLD: float = 4.0

POT_CONTROL_ACTION_BY_POSITION: dict = {
    'ip':  'CHECK_BACK',
    'oop': 'SMALL_BET',
}

POT_CONTROL_SIZE_OOP: dict = {
    'flop':  0.25,
    'turn':  0.28,
    'river': 0.30,
}

BOARD_POT_CONTROL_MODIFIER: dict = {
    'dry':      -0.05,
    'semi_wet':  0.00,
    'wet':      +0.06,
    'monotone': +0.05,
    'paired':   -0.03,
}

SPR_POT_CONTROL_MODIFIER: dict = {
    'very_deep':  +0.08,
    'deep':       +0.04,
    'medium':      0.00,
    'shallow':    -0.05,
    'committed':  -0.10,
}

SPR_CATEGORY_THRESHOLDS: dict = {
    'committed':  1.5,
    'shallow':    3.0,
    'medium':     6.0,
    'deep':      12.0,
    'very_deep': 99.0,
}


def _spr_category(spr: float) -> str:
    for cat, thresh in SPR_CATEGORY_THRESHOLDS.items():
        if spr <= thresh:
            return cat
    return 'very_deep'


def _pot_control_needed(hand_sdv: float, spr: float, position: str, board_texture: str) -> bool:
    in_range = POT_CONTROL_TRIGGER_SDV_RANGE[0] <= hand_sdv <= POT_CONTROL_TRIGGER_SDV_RANGE[1]
    deep_enough = spr >= POT_CONTROL_SPR_THRESHOLD
    wet_board = board_texture in ('wet', 'monotone')
    return in_range and (deep_enough or (wet_board and position == 'oop'))


def _optimal_pc_size(street: str, board_texture: str, spr: float, position: str) -> float:
    if position == 'ip':
        return 0.0
    base = POT_CONTROL_SIZE_OOP.get(street, 0.27)
    board_adj = BOARD_POT_CONTROL_MODIFIER.get(board_texture, 0.0)
    spr_cat = _spr_category(spr)
    spr_adj = SPR_POT_CONTROL_MODIFIER.get(spr_cat, 0.0)
    return round(min(0.45, max(0.15, base + board_adj + spr_adj)), 3)


def _pot_control_decision(hand_sdv: float, spr: float, position: str, board_texture: str) -> str:
    needed = _pot_control_needed(hand_sdv, spr, position, board_texture)
    if not needed:
        if hand_sdv >= 0.68:
            return 'VALUE_BET_FULL'
        return 'CHECK_BACK_SHOWDOWN'
    if position == 'ip':
        return 'CHECK_BACK_POT_CONTROL'
    return 'SMALL_BET_POT_CONTROL'


@dataclass
class PotControlSizingResult:
    hand_sdv: float
    street: str
    board_texture: str
    position: str
    spr: float
    pot_bb: float

    pot_control_needed: bool
    spr_category: str
    pc_action: str
    pc_size_pct: float
    pc_size_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_pot_control_sizing(
    hand_sdv: float = 0.52,
    street: str = 'flop',
    board_texture: str = 'semi_wet',
    position: str = 'ip',
    spr: float = 8.0,
    pot_bb: float = 12.0,
) -> PotControlSizingResult:
    """
    Determine pot control action and sizing for medium-strength hands.

    Args:
        hand_sdv:      Hero's hand showdown value (0-1)
        street:        Current street ('flop','turn','river')
        board_texture: Board texture ('dry','semi_wet','wet','monotone','paired')
        position:      Hero position ('ip' or 'oop')
        spr:           Stack-to-pot ratio
        pot_bb:        Pot size in BB

    Returns:
        PotControlSizingResult
    """
    needed = _pot_control_needed(hand_sdv, spr, position, board_texture)
    spr_cat = _spr_category(spr)
    action = _pot_control_decision(hand_sdv, spr, position, board_texture)
    pc_pct = _optimal_pc_size(street, board_texture, spr, position) if needed and position == 'oop' else 0.0
    pc_bb = round(pot_bb * pc_pct, 1)

    verdict = (
        f'[PCS SDV={hand_sdv:.0%}|{board_texture}|{position}|SPR={spr:.1f}] '
        f'pc_needed={needed} action={action} size={pc_pct:.0%}pot'
    )

    reasoning = (
        f'Pot control: SDV={hand_sdv:.0%} range {POT_CONTROL_TRIGGER_SDV_RANGE} '
        f'SPR={spr}({spr_cat}) board={board_texture} pos={position}. '
        f'PC_needed={needed}. Action={action}. '
        f'Size={pc_pct:.0%}pot={pc_bb:.1f}BB (OOP only).'
    )

    tips = []

    tips.append(
        f'Pot control: SDV={hand_sdv:.0%} on {board_texture} board ({position}, SPR={spr:.1f}). '
        f'Action: {action}. '
        f'{"Check back IP: free showdown; deny free card to villain" if action == "CHECK_BACK_POT_CONTROL" else "Small bet OOP: " + str(pc_pct) + " pot keeps pot manageable" if action == "SMALL_BET_POT_CONTROL" else "Full value bet: hand too strong for pot control"}.'
    )

    if needed and position == 'ip':
        tips.append(
            f'CHECK BACK IP (pot control): SDV={hand_sdv:.0%} medium hand. '
            f'Free showdown if checked through. If villain bets, can call based on hand strength. '
            f'Avoid bloating pot with SDV={hand_sdv:.0%} vs unknown villain range on {board_texture} board.'
        )
    elif needed and position == 'oop':
        tips.append(
            f'SMALL BET OOP ({pc_pct:.0%} pot = {pc_bb:.1f}BB): medium hand on {board_texture}. '
            f'Small lead: define villain hand, protect equity, keep pot controlled. '
            f'If raised: fold or call based on SPR={spr:.1f}; avoid large pots with SDV={hand_sdv:.0%}.'
        )
    elif not needed and hand_sdv >= 0.68:
        tips.append(
            f'VALUE BET: SDV={hand_sdv:.0%} too strong for pot control. '
            f'Build pot now; extract value from villain weaker hands. '
            f'SPR={spr:.1f}: {"stack building is efficient" if spr > 4 else "already shallow; just get it in"}.'
        )

    tips.append(
        f'SPR={spr:.1f} ({spr_cat}): '
        f'{"Very deep -- aggressive pot control; medium hands cannot win large pots" if spr_cat == "very_deep" else "Deep -- pot control helps protect medium pairs" if spr_cat == "deep" else "Medium SPR -- pot control less critical; depends on board" if spr_cat == "medium" else "Shallow/committed -- pot control less important; near-commit anyway"}. '
        f'Board {board_texture}: {"wet boards threaten medium pairs more -- control more aggressively" if board_texture in ("wet", "monotone") else "dry board -- medium pairs safer; pot control less critical"}.'
    )

    return PotControlSizingResult(
        hand_sdv=hand_sdv,
        street=street,
        board_texture=board_texture,
        position=position,
        spr=spr,
        pot_bb=pot_bb,
        pot_control_needed=needed,
        spr_category=spr_cat,
        pc_action=action,
        pc_size_pct=pc_pct,
        pc_size_bb=pc_bb,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pcs_one_liner(r: PotControlSizingResult) -> str:
    return (
        f'[PCS SDV={r.hand_sdv:.0%}|{r.board_texture}|{r.position}|SPR={r.spr:.1f}] '
        f'{r.pc_action} {r.pc_size_pct:.0%}pot'
    )
