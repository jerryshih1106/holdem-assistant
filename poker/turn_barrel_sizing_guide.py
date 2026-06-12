"""
Turn Barrel Sizing Guide (turn_barrel_sizing_guide.py)

Calibrates double barrel (turn bet) sizing to maintain geometric pot building
and respond to how the turn card changes board dynamics.

THEORY:
  TURN BARREL SIZING PRINCIPLES:
  (1) GEOMETRIC SIZING: If planning 3 streets of betting, each bet should be
      a consistent fraction of pot to commit stacks evenly.
      Formula: if flop was 50% pot and stack/pot = 4 going to turn:
      Turn should be ~65-70% pot (escalating to commit by river).

  (2) BOARD CHANGE RESPONSE:
  Brick turn (low unconnected): maintain or reduce size (range still ahead)
  Scare card turn (A/K/Q on low board): size UP (protect range; deny equity)
  Turn completes draw: size UP as value; size DOWN as bluff
  Paired turn: check back often (top pair less valuable; villain may have trips)

  (3) FLOP CBET SIZE -> TURN SIZE CORRELATION:
  Small flop cbet (25-33%): turn should be 50-65% (escalate to commit)
  Medium flop cbet (40-55%): turn should be 55-70%
  Large flop cbet (65-80%): turn can be smaller 50-60% (already large range)

  (4) STACK DEPTH CONSIDERATION:
  Leave enough for river bet. Turn bet should leave SPR ~1-1.5 for river shove.
  Too large turn bet -> forced to check river or under-jam.

  (5) POSITION:
  IP: can go slightly smaller (position advantage; villain must act first)
  OOP: slightly larger (protect against free card / check-backs)

DISTINCT FROM:
  turn_barrel_advisor.py:   When to double barrel (yes/no decision)
  turn_barrel_decision.py:  Which hands to barrel on turn
  barrel.py:                General barrel logic
  THIS MODULE:              HOW MUCH to barrel on turn; geometric progression;
                            flop-to-turn sizing correlation; turn card adjustments.
"""

from dataclasses import dataclass, field
from typing import List

FLOP_TO_TURN_SIZE_ESCALATION: dict = {
    'small':    0.60,
    'medium':   0.65,
    'large':    0.55,
}

FLOP_SIZE_CATEGORY: dict = {
    'small':  0.38,
    'medium': 0.62,
    'large':  9.99,
}

TURN_CARD_SIZE_MODIFIER: dict = {
    'brick':     -0.05,
    'low':       -0.03,
    'medium':     0.00,
    'high':      +0.08,
    'ace_king':  +0.12,
    'flush_draw_complete': +0.10,
    'straight_complete':   +0.10,
    'paired':    -0.08,
}

BOARD_TEXTURE_TURN_SIZE: dict = {
    'dry':      -0.05,
    'semi_wet':  0.00,
    'wet':      +0.08,
    'monotone': +0.06,
    'paired':   -0.06,
}

POSITION_TURN_SIZE_MODIFIER: dict = {
    'ip':  -0.03,
    'oop': +0.05,
}

VILLAIN_TURN_SIZE_MODIFIER: dict = {
    'fish':            +0.08,
    'calling_station': +0.10,
    'nit':             -0.06,
    'lag':             +0.05,
    'reg':              0.00,
}

MIN_TURN_SIZE: float = 0.40
MAX_TURN_SIZE: float = 1.00


def _flop_size_category(flop_pct: float) -> str:
    for cat, thresh in FLOP_SIZE_CATEGORY.items():
        if flop_pct <= thresh:
            return cat
    return 'large'


def _optimal_turn_size(
    flop_pct: float,
    turn_card: str,
    board_texture: str,
    position: str,
    villain_type: str,
) -> float:
    flop_cat = _flop_size_category(flop_pct)
    base = FLOP_TO_TURN_SIZE_ESCALATION.get(flop_cat, 0.60)
    turn_adj = TURN_CARD_SIZE_MODIFIER.get(turn_card, 0.0)
    board_adj = BOARD_TEXTURE_TURN_SIZE.get(board_texture, 0.0)
    pos_adj = POSITION_TURN_SIZE_MODIFIER.get(position, 0.0)
    vil_adj = VILLAIN_TURN_SIZE_MODIFIER.get(villain_type, 0.0)
    raw = base + turn_adj + board_adj + pos_adj + vil_adj
    return round(min(MAX_TURN_SIZE, max(MIN_TURN_SIZE, raw)), 3)


def _spr_after_turn_bet(turn_pct: float, pot_bb: float, stack_bb: float) -> float:
    bet_bb = pot_bb * turn_pct
    new_pot = pot_bb + bet_bb * 2
    new_stack = stack_bb - bet_bb
    if new_pot <= 0:
        return 0.0
    return round(max(0.0, new_stack / new_pot), 2)


@dataclass
class TurnBarrelSizingResult:
    flop_cbet_pct: float
    turn_card: str
    board_texture: str
    position: str
    villain_type: str
    pot_bb: float
    stack_bb: float

    flop_category: str
    optimal_turn_pct: float
    optimal_turn_bb: float
    spr_after_turn: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_turn_barrel_sizing(
    flop_cbet_pct: float = 0.50,
    turn_card: str = 'medium',
    board_texture: str = 'semi_wet',
    position: str = 'ip',
    villain_type: str = 'reg',
    pot_bb: float = 15.0,
    stack_bb: float = 85.0,
) -> TurnBarrelSizingResult:
    """
    Calibrate double barrel (turn bet) sizing.

    Args:
        flop_cbet_pct:  Flop cbet size as fraction of pot (0.33, 0.50, 0.75, etc.)
        turn_card:      Turn card type ('brick','low','medium','high','ace_king',
                        'flush_draw_complete','straight_complete','paired')
        board_texture:  Flop board texture ('dry','semi_wet','wet','monotone','paired')
        position:       Hero position ('ip' or 'oop')
        villain_type:   Villain type ('fish','nit','lag','reg','calling_station')
        pot_bb:         Pot size in BB at start of turn (after flop action)
        stack_bb:       Effective stack in BB at turn

    Returns:
        TurnBarrelSizingResult
    """
    flop_cat = _flop_size_category(flop_cbet_pct)
    opt_pct = _optimal_turn_size(flop_cbet_pct, turn_card, board_texture, position, villain_type)
    opt_bb = round(pot_bb * opt_pct, 1)
    spr_after = _spr_after_turn_bet(opt_pct, pot_bb, stack_bb)

    verdict = (
        f'[TBS flop={flop_cbet_pct:.0%}|{turn_card}|{board_texture}|{villain_type}] '
        f'turn={opt_pct:.0%}pot={opt_bb:.1f}BB SPR_after={spr_after}'
    )

    reasoning = (
        f'Turn barrel size: flop={flop_cbet_pct:.0%}({flop_cat}) '
        f'turn_card_adj={TURN_CARD_SIZE_MODIFIER.get(turn_card, 0):+.0%} '
        f'board_adj={BOARD_TEXTURE_TURN_SIZE.get(board_texture, 0):+.0%} '
        f'pos_adj={POSITION_TURN_SIZE_MODIFIER.get(position, 0):+.0%} '
        f'vil_adj={VILLAIN_TURN_SIZE_MODIFIER.get(villain_type, 0):+.0%}. '
        f'Optimal turn={opt_pct:.0%}pot={opt_bb:.1f}BB. SPR_after={spr_after}.'
    )

    tips = []

    tips.append(
        f'Double barrel: {opt_pct:.0%} pot = {opt_bb:.1f}BB on {turn_card} turn. '
        f'Flop was {flop_cbet_pct:.0%}({flop_cat}); escalating to {opt_pct:.0%} for commitment. '
        f'SPR after turn bet = {spr_after}: '
        f'{"river will be close to shove" if spr_after < 1.5 else "room for river decision"}.'
    )

    if turn_card in ('ace_king', 'high'):
        tips.append(
            f'HIGH/ACE-KING turn: SIZE UP to {opt_pct:.0%}. '
            f'Protect range vs villain who may have connected with scare card. '
            f'Also charges villain draws that picked up pair outs on the turn.'
        )
    elif turn_card in ('flush_draw_complete', 'straight_complete'):
        tips.append(
            f'DRAW COMPLETED turn: SIZE UP to {opt_pct:.0%} with value; size down or give up bluffs. '
            f'Value hands bet for protection and extraction. '
            f'Bluffs lose effectiveness when draws complete (villain has made hands).'
        )
    elif turn_card == 'brick':
        tips.append(
            f'BRICK turn: maintain range advantage; {opt_pct:.0%} pot is efficient. '
            f'Villain still has missed draws and air from flop. '
            f'No need to size up; smaller bet achieves same fold equity on brick runout.'
        )
    else:
        tips.append(
            f'Turn sizing calibrated: {opt_pct:.0%} pot vs {villain_type} on {board_texture}. '
            f'{"Fish/station: go larger to extract maximum" if villain_type in ("fish", "calling_station") else "Nit: smaller sizes work; nit folds without strong holdings" if villain_type == "nit" else "Standard geometric barrel"}.'
        )

    return TurnBarrelSizingResult(
        flop_cbet_pct=flop_cbet_pct,
        turn_card=turn_card,
        board_texture=board_texture,
        position=position,
        villain_type=villain_type,
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        flop_category=flop_cat,
        optimal_turn_pct=opt_pct,
        optimal_turn_bb=opt_bb,
        spr_after_turn=spr_after,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tbs_one_liner(r: TurnBarrelSizingResult) -> str:
    return (
        f'[TBS flop={r.flop_cbet_pct:.0%}|{r.turn_card}|{r.villain_type}] '
        f'turn={r.optimal_turn_pct:.0%}pot SPR_after={r.spr_after_turn}'
    )
