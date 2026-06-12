"""
Overbetting Frequency Guide (overbetting_frequency_guide.py)

Guides when and how often to use overbets (bets > 100% pot).
Overbetting is a powerful tool that polarizes your range and puts
maximum pressure on villain's bluff catchers.

OVERBET THEORY:
  An overbet says: "My range is polarized -- I have the nuts or a bluff."
  This forces villain to make a binary decision with limited information.

  GTO OVERBET SPOTS:
  1. RIVER with nut advantage: When hero has more nutted hands than villain
  2. Unimproved boards where hero has top of range: TPTK+ with no draws
  3. Range advantage: Hero's checking range includes many strong hands
  4. Scare cards that help hero's range more than villain's

  OVERBET SIZING:
  - 1.25x pot: Small overbet (light pressure, wide value range)
  - 1.50x pot: Standard overbet (balanced polarization)
  - 2.00x pot: Large overbet (strong polarization, only nuts/bluffs)
  - 3.00x pot: Shove territory / jam spots

  AVOID OVERBETTING WHEN:
  - Hero has medium-strength hand (loses to all bluff-catchers villain calls)
  - Board hits villain's range harder (range disadvantage)
  - Villain is a calling station (WTSD >= 40%)
  - SPR < 1.5 (no room for meaningful overbet)

POLARIZATION MATH:
  Villain's break-even call rate: alpha = bet/(pot+bet)
  For 1.5x pot: alpha = 1.5/(1+1.5) = 0.60 (villain needs 60% equity to call)
  This means villain folds hands losing to both nuts AND bluffs at high rate.

DISTINCT FROM:
  river_bluff.py:              River bluff execution
  value_bet_sizing.py:         General sizing guide
  board_runout_planner.py:     Planning runout-specific bets
  THIS MODULE:                 Overbet-specific guide; frequency analysis;
                               when overbets are GTO vs exploitative

Usage:
    from poker.overbetting_frequency_guide import guide_overbet, OverbetGuide, obg_one_liner

    result = guide_overbet(
        street='river',
        hero_hand_category='nuts',
        hero_position='ip',
        hero_role='pfr',
        board_texture='dry',
        nut_advantage='dominant',
        villain_wtsd=0.28,
        spr=4.0,
        pot_bb=40.0,
        villain_af=2.2,
    )
    print(obg_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Base overbet frequency by spot
BASE_OVERBET_FREQ = {
    ('river', 'dominant'):     0.40,   # river + nut advantage = primary overbet spot
    ('river', 'significant'):  0.25,
    ('river', 'slight'):       0.12,
    ('river', 'none'):         0.05,
    ('turn', 'dominant'):      0.20,
    ('turn', 'significant'):   0.12,
    ('turn', 'slight'):        0.05,
    ('turn', 'none'):          0.02,
    ('flop', 'dominant'):      0.10,
    ('flop', 'significant'):   0.05,
    ('flop', 'slight'):        0.02,
    ('flop', 'none'):          0.0,
}

# Recommended overbet sizes by nut advantage level
OVERBET_SIZE_BY_NUT = {
    'dominant':   1.50,   # 150% pot
    'significant': 1.25,
    'slight':     1.10,
    'none':       0.0,    # no overbet
}


def _alpha(bet_size_pct: float) -> float:
    """Required equity to call: bet/(pot+bet)"""
    return bet_size_pct / (1 + bet_size_pct)


def _overbet_frequency(
    street: str,
    nut_advantage: str,
    hero_hand_category: str,
    villain_wtsd: float,
    spr: float,
    hero_position: str,
) -> float:
    key = (street, nut_advantage)
    base = BASE_OVERBET_FREQ.get(key, 0.05)

    # Strong hand: overbet more
    if hero_hand_category in ('nuts', 'near_nuts', 'full_house', 'flush', 'straight', 'set'):
        base += 0.10
    # Medium hand: reduce overbet freq
    elif hero_hand_category in ('top_pair', 'overpair', 'middle_pair'):
        base -= 0.10

    # Calling station: reduce (they call off; can't polarize effectively)
    if villain_wtsd >= 0.40:
        base -= 0.15

    # IP position: slightly more overbet opportunities
    if hero_position == 'ip':
        base += 0.05

    # Low SPR: can't really overbet meaningfully
    if spr < 1.5:
        base = 0.0

    return round(max(0.0, min(0.80, base)), 3)


def _recommended_overbet_size(
    nut_advantage: str,
    street: str,
    hero_hand_category: str,
    villain_wtsd: float,
) -> float:
    base = OVERBET_SIZE_BY_NUT.get(nut_advantage, 0.0)
    # River + nuts = can go bigger
    if street == 'river' and hero_hand_category in ('nuts', 'near_nuts') and villain_wtsd <= 0.28:
        base = min(2.0, base + 0.25)
    return round(base, 2)


def _overbet_rationale(
    street: str,
    nut_advantage: str,
    hero_hand_category: str,
    hero_role: str,
    board_texture: str,
) -> str:
    if nut_advantage in ('dominant', 'significant') and street == 'river':
        return (
            f'River with {nut_advantage} nut advantage: '
            f'Primary overbet spot. Hero\'s range includes many more nut hands than villain. '
            f'Overbet forces villain to defend expensive bluff-catchers.'
        )
    elif board_texture == 'dry' and hero_role == 'pfr' and street in ('turn', 'river'):
        return (
            f'Dry board + PFR: Villain\'s range is capped on dry board. '
            f'Hero (PFR) has more top-of-range hands (overpairs, sets). '
            f'Overbet to extract max value and deny equity.'
        )
    elif hero_hand_category in ('nuts', 'near_nuts'):
        return (
            f'Hero has nuts/near-nuts: Maximum value extraction with overbet. '
            f'Balancing range protection: include some bluffs with missed draws.'
        )
    else:
        return (
            f'Standard spot: Overbet with care. '
            f'Polarization only effective when hero has clear nut advantage. '
            f'Consider standard sizing instead.'
        )


def _should_overbet(
    overbet_freq: float,
    nut_advantage: str,
    villain_wtsd: float,
    spr: float,
) -> bool:
    if spr < 1.5:
        return False
    if villain_wtsd >= 0.45:
        return False
    if nut_advantage in ('dominant', 'significant') and overbet_freq >= 0.15:
        return True
    if overbet_freq >= 0.30:
        return True
    return False


@dataclass
class OverbetGuide:
    # Inputs
    street: str
    hero_hand_category: str
    hero_position: str
    hero_role: str
    board_texture: str
    nut_advantage: str
    villain_wtsd: float
    spr: float
    pot_bb: float
    villain_af: float

    # Analysis
    overbet_frequency: float     # how often to overbet in this spot
    recommended_size: float      # overbet size as fraction of pot
    should_overbet: bool
    required_villain_equity: float  # alpha = bet/(pot+bet)
    rationale: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def guide_overbet(
    street: str = 'river',
    hero_hand_category: str = 'nuts',
    hero_position: str = 'ip',
    hero_role: str = 'pfr',
    board_texture: str = 'dry',
    nut_advantage: str = 'dominant',
    villain_wtsd: float = 0.28,
    spr: float = 4.0,
    pot_bb: float = 40.0,
    villain_af: float = 2.2,
) -> OverbetGuide:
    """
    Guide on when and how often to use overbets.

    Args:
        street:              'flop' / 'turn' / 'river'
        hero_hand_category:  'nuts' / 'near_nuts' / 'top_pair' / 'bluff' / etc.
        hero_position:       'ip' / 'oop'
        hero_role:           'pfr' / 'caller'
        board_texture:       'dry' / 'semi_wet' / 'wet' / 'monotone' / 'paired'
        nut_advantage:       'dominant' / 'significant' / 'slight' / 'none'
        villain_wtsd:        Villain's WTSD stat
        spr:                 Stack-to-pot ratio
        pot_bb:              Current pot
        villain_af:          Villain's AF

    Returns:
        OverbetGuide
    """
    freq = _overbet_frequency(street, nut_advantage, hero_hand_category,
                               villain_wtsd, spr, hero_position)
    size = _recommended_overbet_size(nut_advantage, street, hero_hand_category, villain_wtsd)
    do_overbet = _should_overbet(freq, nut_advantage, villain_wtsd, spr)
    alpha = _alpha(size) if size > 0 else 0.0
    rationale = _overbet_rationale(street, nut_advantage, hero_hand_category,
                                    hero_role, board_texture)

    verdict = (
        f'[OBG {nut_advantage.upper()}|{street}|{hero_position}] '
        f'{"OVERBET" if do_overbet else "NO_OVERBET"} {size:.0%}pot '
        f'| freq={freq:.0%} alpha={alpha:.0%}'
    )

    reasoning = (
        f'Overbet guide: {hero_hand_category} on {board_texture} {street}. '
        f'Nut advantage={nut_advantage}. Position={hero_position} ({hero_role}). '
        f'Overbet freq={freq:.0%}. Size={size:.0%}pot. Alpha={alpha:.0%}. '
        f'WTSD={villain_wtsd:.0%}. SPR={spr:.1f}. Do overbet={do_overbet}.'
    )

    tips = [rationale]

    tips.append(
        f'OVERBET MATH: Bet {size:.0%} pot = {size * pot_bb:.1f}BB into {pot_bb:.1f}BB pot. '
        f'Villain needs {alpha:.0%} equity to break-even on call. '
        f'This forces them to fold unless they have {alpha:.0%}+ equity.'
    )

    tips.append(
        f'FREQUENCY: Overbet in this spot {freq:.0%} of the time. '
        f'Mix with regular bets ({1-freq:.0%}) to stay balanced. '
        f'Polarize: overbet value hands ({hero_hand_category}) + missed draws as bluffs.'
    )

    if villain_wtsd >= 0.38:
        tips.append(
            f'CALLING STATION WARNING (WTSD={villain_wtsd:.0%}): Reduce overbet frequency. '
            f'Villain calls too often -- overbetting with bluffs is unprofitable. '
            f'Overbet ONLY with nutted hands vs this villain.'
        )

    if spr < 2.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): Overbetting may not be meaningful. '
            f'Consider shoving all-in instead of a "structured" overbet. '
            f'SPR < 2 = commit zone; all bets become pot-defining.'
        )

    if nut_advantage == 'none':
        tips.append(
            f'NO NUT ADVANTAGE: Overbetting without nut advantage is weak. '
            f'Villain calls with bluff-catchers that beat your range. '
            f'Use standard sizing instead until you establish nut advantage.'
        )

    return OverbetGuide(
        street=street,
        hero_hand_category=hero_hand_category,
        hero_position=hero_position,
        hero_role=hero_role,
        board_texture=board_texture,
        nut_advantage=nut_advantage,
        villain_wtsd=villain_wtsd,
        spr=spr,
        pot_bb=pot_bb,
        villain_af=villain_af,
        overbet_frequency=freq,
        recommended_size=size,
        should_overbet=do_overbet,
        required_villain_equity=alpha,
        rationale=rationale,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def obg_one_liner(r: OverbetGuide) -> str:
    return (
        f'[OBG {r.nut_advantage.upper()}|{r.street}|{r.hero_position}] '
        f'{"OVERBET" if r.should_overbet else "NO_OVERBET"} {r.recommended_size:.0%}pot '
        f'| freq={r.overbet_frequency:.0%} alpha={r.required_villain_equity:.0%}'
    )
