"""
CBet Sizing Board Guide (cbet_sizing_board_guide.py)

Calibrates continuation bet size based on board texture, position,
villain type, and street to maximize EV of each cbet.

THEORY:
  BOARD TEXTURE -> OPTIMAL CBET SIZE:
  Dry boards (K72r): small 25-33% pot
    Range advantage high; villain range connected poorly; any bet wins
  Semi-wet boards (KT8tt): medium 40-50% pot
    Some draws; need moderate sizing for protection
  Wet boards (JT9r, connected): 50-67% pot
    Many draws; need larger size to charge draws and protect equity
  Monotone boards: 33-50% pot
    Villain likely has flush draws; balanced sizing

  POSITION MODIFIER:
  IP: can go smaller (position advantage; villain must act first on future streets)
  OOP: slightly larger (fewer opportunities to extract later)

  VILLAIN MODIFIER:
  Fish/calling_station: size UP (they call too wide; extract maximum)
  Nit: size DOWN (nit folds to any reasonable bet; overcbetting vs nit wastes value)
  LAG: size slightly UP (LAG calls wide; also harder to bluff)

  STREET MODIFIER:
  Flop: baseline sizes as above
  Turn: generally 50-70% pot (pot larger relative to stack; more committed)
  River: 65-100% pot (no more streets; max value or large bluff)

DISTINCT FROM:
  dynamic_cbet_size_optimizer.py: Dynamic sizing using equity calculations
  adaptive_sizing.py:              General adaptive sizing engine
  cbet_frequency_auditor.py:      Whether to cbet at all
  THIS MODULE:                    BOARD TEXTURE -> SIZE mapping; calibration
                                  guide; villain/position/street adjustments.
"""

from dataclasses import dataclass, field
from typing import List

CBET_SIZE_BY_TEXTURE: dict = {
    'dry':      0.28,
    'semi_wet': 0.45,
    'wet':      0.58,
    'monotone': 0.40,
    'paired':   0.33,
}

VILLAIN_CBET_SIZE_MODIFIER: dict = {
    'fish':            +0.12,
    'calling_station': +0.15,
    'nit':             -0.10,
    'lag':             +0.08,
    'rec':             +0.05,
    'reg':              0.00,
}

POSITION_SIZE_MODIFIER: dict = {
    'ip':  -0.03,
    'oop': +0.05,
}

STREET_SIZE_MODIFIER: dict = {
    'flop':  1.00,
    'turn':  1.15,
    'river': 1.30,
}

MIN_CBET_PCT: float = 0.20
MAX_CBET_PCT: float = 1.10


def _optimal_cbet_pct(
    board_texture: str,
    villain_type: str,
    position: str,
    street: str,
) -> float:
    base = CBET_SIZE_BY_TEXTURE.get(board_texture, 0.45)
    vil_mod = VILLAIN_CBET_SIZE_MODIFIER.get(villain_type, 0.00)
    pos_mod = POSITION_SIZE_MODIFIER.get(position, 0.00)
    str_mod = STREET_SIZE_MODIFIER.get(street, 1.00)
    raw = (base + vil_mod + pos_mod) * str_mod
    return round(min(MAX_CBET_PCT, max(MIN_CBET_PCT, raw)), 3)


def _cbet_size_category(pct: float) -> str:
    if pct <= 0.30:
        return 'SMALL_RANGE_BET'
    if pct <= 0.50:
        return 'MEDIUM_BET'
    if pct <= 0.75:
        return 'STANDARD_POLAR_BET'
    return 'LARGE_POLAR_BET'


@dataclass
class CbetSizingBoardResult:
    board_texture: str
    villain_type: str
    position: str
    street: str
    pot_bb: float

    optimal_pct: float
    optimal_bb: float
    size_category: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_cbet_sizing_board(
    board_texture: str = 'semi_wet',
    villain_type: str = 'reg',
    position: str = 'ip',
    street: str = 'flop',
    pot_bb: float = 10.0,
) -> CbetSizingBoardResult:
    """
    Calibrate CBet size for given board texture and situation.

    Args:
        board_texture: Flop texture ('dry','semi_wet','wet','monotone','paired')
        villain_type:  Villain type ('fish','nit','lag','reg','calling_station')
        position:      Hero position ('ip' or 'oop')
        street:        Current street ('flop','turn','river')
        pot_bb:        Current pot size in BB

    Returns:
        CbetSizingBoardResult
    """
    opt_pct = _optimal_cbet_pct(board_texture, villain_type, position, street)
    opt_bb = round(pot_bb * opt_pct, 1)
    cat = _cbet_size_category(opt_pct)

    verdict = (
        f'[CBS {board_texture}|{villain_type}|{position}|{street}] '
        f'size={opt_pct:.0%}pot={opt_bb:.1f}BB cat={cat}'
    )

    reasoning = (
        f'CBet sizing: board={board_texture} base={CBET_SIZE_BY_TEXTURE.get(board_texture, 0.45):.0%} '
        f'vil_adj={VILLAIN_CBET_SIZE_MODIFIER.get(villain_type, 0):+.0%} '
        f'pos_adj={POSITION_SIZE_MODIFIER.get(position, 0):+.0%} '
        f'str_mult={STREET_SIZE_MODIFIER.get(street, 1.0):.2f}x. '
        f'Optimal={opt_pct:.0%} pot = {opt_bb:.1f}BB. Category={cat}.'
    )

    tips = []

    tips.append(
        f'CBet size on {board_texture} board ({street}, {position}): {opt_pct:.0%} pot = {opt_bb:.1f}BB. '
        f'{cat}. '
        f'{"Dry board: small range bet -- any size achieves same fold equity" if board_texture == "dry" else "Wet board: size up to charge draws and protect made hands" if board_texture == "wet" else "Semi-wet: medium size balances protection and value"}.'
    )

    if villain_type in ('fish', 'calling_station'):
        tips.append(
            f'vs {villain_type}: SIZE UP to {opt_pct:.0%}. '
            f'{villain_type.upper()} calls too wide -- extract max value with made hands. '
            f'Never go below {CBET_SIZE_BY_TEXTURE.get(board_texture, 0.45):.0%} vs fish; they call anyway.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'vs NIT: SIZE DOWN to {opt_pct:.0%}. '
            f'Nit folds to any reasonable bet; overcbetting vs nit is EV-neutral. '
            f'Small size denies free cards AND extracts calling range; nit range is honest.'
        )
    elif villain_type == 'lag':
        tips.append(
            f'vs LAG: {opt_pct:.0%} is appropriate. '
            f'LAG floats wide and check-raises; use polarized sizes on {board_texture} boards. '
            f'IP: can go smaller and re-evaluate on turn; OOP: size to fold out LAG air.'
        )
    else:
        tips.append(
            f'vs REG ({position}): {opt_pct:.0%} pot achieves balanced EV. '
            f'{"IP: can use smaller sizes and take advantage of position" if position == "ip" else "OOP: slightly larger; limited future streets to extract value"}. '
            f'Street={street}: {"protect range for multi-street plan" if street == "flop" else "larger size; committed players"}.'
        )

    return CbetSizingBoardResult(
        board_texture=board_texture,
        villain_type=villain_type,
        position=position,
        street=street,
        pot_bb=pot_bb,
        optimal_pct=opt_pct,
        optimal_bb=opt_bb,
        size_category=cat,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def cbs_one_liner(r: CbetSizingBoardResult) -> str:
    return (
        f'[CBS {r.board_texture}|{r.villain_type}|{r.street}] '
        f'{r.optimal_pct:.0%}pot={r.optimal_bb:.1f}BB {r.size_category}'
    )
