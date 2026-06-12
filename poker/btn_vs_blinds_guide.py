"""
BTN vs Blinds Guide (btn_vs_blinds_guide.py)

Theory: BTN vs BB is the most common heads-up postflop spot.
BTN has positional advantage throughout the hand:
  - Higher cbet frequency than other spots (60% dry, 48% wet)
  - Wider value range and more bluffs
  - High turn/river barrel frequency on bricks and scare cards

BB defense:
  - Must defend ~65% to avoid being exploited (MDF ~ 65%)
  - Raise with strong hands; call with implied-odds hands
  - Rarely 3-bet without premiums on flop

DISTINCT FROM:
  blind_vs_blind_strategy_guide.py  -- SB vs BB
  bb_defense_optimizer.py           -- BB defense calibration
  THIS MODULE                       -- BTN aggressor postflop strategy
"""

from dataclasses import dataclass, field
from typing import List


BTN_CBET_FREQ: dict = {
    'dry':      0.60,
    'semi_wet': 0.55,
    'wet':      0.48,
    'monotone': 0.52,
    'paired':   0.58,
}

BTN_TURN_BARREL: dict = {
    'brick':      0.52,
    'scare':      0.62,
    'completing': 0.45,
}

BTN_RIVER_BARREL: float = 0.45

BB_DEFENSE_VS_BTN: float = 0.65

BTN_OPEN_SIZE: float = 2.5


def _btn_cbet_freq(board_texture: str) -> float:
    return BTN_CBET_FREQ.get(board_texture, BTN_CBET_FREQ['semi_wet'])


def _btn_barrel_freq(street: str, turn_card_type: str = 'brick') -> float:
    if street == 'turn':
        return BTN_TURN_BARREL.get(turn_card_type, BTN_TURN_BARREL['brick'])
    if street == 'river':
        return BTN_RIVER_BARREL
    return _btn_cbet_freq('semi_wet')


def _bb_defense_freq(bb_style: str) -> float:
    mods = {
        'passive':   -0.05,
        'calling_station': +0.08,
        'aggressive': +0.03,
        'balanced':   0.00,
        'tight':     -0.10,
    }
    return round(min(0.85, max(0.45, BB_DEFENSE_VS_BTN + mods.get(bb_style, 0.0))), 3)


@dataclass
class BtnVsBlindsResult:
    board_texture: str
    turn_card_type: str
    street: str
    bb_style: str
    cbet_freq: float
    barrel_freq: float
    bb_defense_freq: float
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_btn_vs_blinds(
    board_texture: str = 'dry',
    turn_card_type: str = 'brick',
    street: str = 'flop',
    bb_style: str = 'balanced',
) -> BtnVsBlindsResult:
    """
    Analyze BTN strategy vs BB postflop.

    Args:
        board_texture:  'dry','semi_wet','wet','monotone','paired'
        turn_card_type: 'brick','scare','completing' (for turn street)
        street:         'flop','turn','river'
        bb_style:       'passive','calling_station','aggressive','balanced','tight'

    Returns:
        BtnVsBlindsResult
    """
    cf = _btn_cbet_freq(board_texture)
    bf = _btn_barrel_freq(street, turn_card_type)
    bdef = _bb_defense_freq(bb_style)

    verdict = (
        f'[BVB board={board_texture}] '
        f'cbet={cf:.0%} barrel={bf:.0%} bb_def={bdef:.0%}'
    )

    reasoning = (
        f'BTN vs BB on {street}. Board={board_texture}. '
        f'BTN cbet={cf:.0%}. '
        f'{"Turn card=" + turn_card_type + " barrel=" if street == "turn" else "Barrel="}'
        f'{bf:.0%}. BB ({bb_style}) defense={bdef:.0%}.'
    )

    tips: List[str] = []
    tips.append(
        f'BTN CBET: Bet {cf:.0%} on {board_texture} boards. Position gives you '
        f'the right to bet frequently and control pot size.'
    )
    tips.append(
        f'BB DEFENSE: {bb_style.upper()} BB defends {bdef:.0%}. '
        f'Adjust bluff frequency: vs tight BB bluff more; vs station value bet more.'
    )

    if board_texture == 'wet':
        tips.append(
            'WET BOARD: Lower cbet frequency (48%). Balance by checking back '
            'medium-strength hands and trapping on favorable runouts.'
        )
    if board_texture == 'dry':
        tips.append(
            'DRY BOARD: High cbet frequency (60%). BB has few draws; '
            'most of his range will fold to a bet.'
        )
    if street == 'turn' and turn_card_type == 'scare':
        tips.append(
            'SCARE CARD: Increase barrel frequency (62%). Scare cards hit BTN '
            'range harder; represent strong hands and apply pressure.'
        )
    if street == 'river':
        tips.append(
            f'RIVER: Barrel {BTN_RIVER_BARREL:.0%} of the time as BTN. '
            f'Polarize range: thin value and bluffs with good blockers.'
        )
    if bb_style == 'calling_station':
        tips.append(
            'CALLING STATION BB: Reduce bluffs; increase value bet frequency '
            'and thin-value bet threshold. Station never folds.'
        )

    return BtnVsBlindsResult(
        board_texture=board_texture,
        turn_card_type=turn_card_type,
        street=street,
        bb_style=bb_style,
        cbet_freq=cf,
        barrel_freq=bf,
        bb_defense_freq=bdef,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bvb_one_liner(r: BtnVsBlindsResult) -> str:
    return (
        f'[BVB board={r.board_texture}] '
        f'cbet={r.cbet_freq:.0%} barrel={r.barrel_freq:.0%} bb_def={r.bb_defense_freq:.0%}'
    )
