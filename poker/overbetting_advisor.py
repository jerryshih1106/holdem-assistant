"""
Overbetting Advisor (overbetting_advisor.py)

Identifies spots where oversized bets (>100% pot) are mathematically
optimal and provides sizing/frequency guidance.

THEORY:
  Overbets (1.25x-2.5x pot) work when hero has a POLARIZED range:
  - Nutted hands: want maximum value; villain must call or be exploited
  - Air/bluffs: need large size to compensate for low fold equity per hand
  - Merged ranges (top-pair type): prefer standard 50-75% sizes
  - Overbetting balanced: bet 1 bluff per 2-3 value combos for correct ratio

  WHY OVERBETS WORK:
  - On river: range advantage is strongest; villain cannot have nuts often
  - On turn: "building the pot" for a river jam
  - Key: villain's calling range is FIXED; oversized bet doesn't charge more
    for every hand in range, just polarizes the caller's range further

  OPTIMAL OVERBET SPOTS:
  1. River: hero has many nut combos + busted draws for bluffs
  2. Turn: setting up geometric pot-sized river shove (SPR ~2-3)
  3. Paired boards (flop): hero range full of trips/boats, villain has pairs
  4. Ace-high flops: hero 3-better has many AA/KK/AK; caller is capped

  BLUFF-TO-VALUE RATIO FOR OVERBETS:
  For bet = X (fraction of pot):
    alpha = X / (1 + X)  -- villain's required fold frequency for zero EV
    value_combos / bluff_combos = X / 1  (balanced ratio)
  Example: 1.5x pot overbet -> alpha = 1.5/2.5 = 60%
    -> need bluff_freq = 40% (1 bluff per 1.5 value combos)

DISTINCT FROM:
  river_value.py:       Standard value bet sizing
  bet_sizing_ev.py:     EV comparison by bet size
  THIS MODULE:          Overbet-SPECIFIC spots; polarization requirement;
                        bluff-to-value ratio; turn setup geometry.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Minimum range polarization score to justify overbet
MIN_POLARIZATION_FOR_OVERBET = 0.65

# Overbet sizes (fraction of pot)
OVERBET_SIZES = {
    'standard': 1.25,
    'large':    1.50,
    'pot_plus': 1.75,
    'jam_size': 2.00,
}

# Hand categories that support overbetting (polarized value)
OVERBET_VALUE_HANDS = frozenset({
    'nuts', 'full_house', 'flush', 'straight', 'set',
})

# Hand categories suitable as bluffs in overbet range
OVERBET_BLUFF_HANDS = frozenset({
    'air', 'gutshot', 'flush_draw',  # missed draws on river
})

# Board textures where overbets are most effective
GOOD_OVERBET_TEXTURES = frozenset({'dry', 'paired', 'monotone'})

# Street-specific overbet frequency limits
MAX_OVERBET_FREQ: dict = {
    'flop':  0.25,
    'turn':  0.35,
    'river': 0.50,
}


def _polarization_score(
    hand_category: str,
    board_texture: str,
    hero_is_pfr: bool,
    street: str,
) -> float:
    """Score how polarized hero's range is (0-1)."""
    score = 0.5

    if hand_category in OVERBET_VALUE_HANDS:
        score += 0.30
    elif hand_category in OVERBET_BLUFF_HANDS:
        score += 0.20
    else:
        score -= 0.25  # merged range (top_pair/overpair/two_pair); not polarized

    if board_texture in GOOD_OVERBET_TEXTURES:
        score += 0.10
    else:
        score -= 0.05

    if hero_is_pfr:
        score += 0.08  # PFR has more nut combos
    else:
        score -= 0.05

    if street == 'river':
        score += 0.12
    elif street == 'flop':
        score -= 0.10

    return round(min(1.0, max(0.0, score)), 3)


def _optimal_overbet_size(
    street: str,
    hand_category: str,
    spr: float,
) -> float:
    """Return optimal overbet fraction of pot."""
    if street == 'river':
        if hand_category in ('nuts', 'full_house'):
            return OVERBET_SIZES['large']
        elif hand_category in OVERBET_VALUE_HANDS:
            return OVERBET_SIZES['standard']
        elif hand_category in OVERBET_BLUFF_HANDS:
            return OVERBET_SIZES['large']  # big bluffs on river
    elif street == 'turn':
        if spr <= 3.0:
            return OVERBET_SIZES['pot_plus']  # set up jam
        return OVERBET_SIZES['standard']
    return OVERBET_SIZES['standard']


def _bluff_to_value_ratio(overbet_size: float) -> tuple:
    """Return (bluffs_per_value, required_fold_freq)."""
    alpha = overbet_size / (1.0 + overbet_size)  # fold freq for 0 EV bluff
    bluffs_per_value = round(1.0 - alpha, 3)      # balanced ratio
    return bluffs_per_value, round(alpha, 3)


def _overbet_ev(
    hero_equity: float,
    pot_bb: float,
    overbet_size: float,
    villain_call_freq: float,
) -> float:
    bet_bb = pot_bb * overbet_size
    ev_fold = (1.0 - villain_call_freq) * pot_bb
    ev_call = villain_call_freq * (hero_equity * (pot_bb + 2 * bet_bb) - bet_bb)
    return round(ev_fold + ev_call, 2)


@dataclass
class OverbetAdvice:
    hand_category: str
    board_texture: str
    street: str
    hero_is_pfr: bool
    spr: float
    pot_bb: float

    polarization_score: float
    should_overbet: bool
    recommended_size: float
    bet_bb: float
    bluffs_per_value: float
    required_fold_freq: float
    overbet_ev: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_overbet(
    hand_category: str = 'nuts',
    board_texture: str = 'dry',
    street: str = 'river',
    hero_is_pfr: bool = True,
    hero_position: str = 'ip',
    spr: float = 3.0,
    pot_bb: float = 30.0,
    hero_equity: float = 0.90,
    villain_call_freq: float = 0.40,
) -> OverbetAdvice:
    """
    Advise whether and how to overbet in this spot.

    Args:
        hand_category:    Hero's hand
        board_texture:    Board texture
        street:           Current street
        hero_is_pfr:      Is hero the preflop raiser?
        hero_position:    'ip' / 'oop'
        spr:              Stack-to-pot ratio
        pot_bb:           Current pot in BB
        hero_equity:      Hero's equity vs villain's range
        villain_call_freq: Estimated villain call frequency vs overbet

    Returns:
        OverbetAdvice
    """
    pol_score = _polarization_score(hand_category, board_texture, hero_is_pfr, street)
    should_ob = pol_score >= MIN_POLARIZATION_FOR_OVERBET

    if hero_position == 'oop' and street == 'flop':
        should_ob = False  # OOP flop overbets rarely GTO

    ob_size = _optimal_overbet_size(street, hand_category, spr) if should_ob else 0.0
    bet_bb = round(pot_bb * ob_size, 1)
    bluffs_per_val, req_fold = _bluff_to_value_ratio(ob_size) if ob_size > 0 else (0.0, 0.0)
    ev = _overbet_ev(hero_equity, pot_bb, ob_size, villain_call_freq) if ob_size > 0 else 0.0

    verdict = (
        f'[OBA {hand_category}|{street}|{hero_position}] '
        f'{"OVERBET" if should_ob else "NO_OVERBET"} {ob_size:.0%}pot = {bet_bb:.1f}BB | '
        f'pol={pol_score:.0%}'
    )

    reasoning = (
        f'Overbet analysis: {hand_category} on {board_texture} {street} '
        f'({"PFR" if hero_is_pfr else "caller"}, {hero_position.upper()}). '
        f'Polarization score: {pol_score:.0%} (min: {MIN_POLARIZATION_FOR_OVERBET:.0%}). '
        f'{"OVERBET recommended." if should_ob else "Standard size; range not polarized enough."} '
        f'Size: {ob_size:.0%}pot = {bet_bb:.1f}BB. '
        f'Bluffs per value: {bluffs_per_val:.0%}. EV: {ev:+.1f}BB.'
    )

    tips = []

    tips.append(
        f'POLARIZATION: score={pol_score:.0%}. '
        f'{hand_category} on {board_texture} {street} = '
        f'{"well-polarized; overbet viable." if pol_score >= 0.70 else "moderately polarized; overbet marginal." if pol_score >= MIN_POLARIZATION_FOR_OVERBET else "not polarized enough; use standard sizing."}'
    )

    if should_ob:
        tips.append(
            f'OVERBET SIZING: {ob_size:.0%} pot = {bet_bb:.1f}BB. '
            f'Villain call freq: {villain_call_freq:.0%}. '
            f'EV: {ev:+.1f}BB. '
            f'Required fold: {req_fold:.0%}. '
            f'Balanced bluff ratio: {bluffs_per_val:.0%} bluffs per value bet.'
        )
        tips.append(
            f'RANGE CONSTRUCTION: For {ob_size:.0%}pot overbet, need '
            f'{bluffs_per_val:.0%} bluff combos per value combo. '
            f'Value: {", ".join(OVERBET_VALUE_HANDS)}. '
            f'Bluffs: missed {board_texture} draws, {", ".join(list(OVERBET_BLUFF_HANDS)[:2])}.'
        )
        if street == 'turn':
            river_bet = round((pot_bb + 2 * bet_bb) * 1.0, 1)
            tips.append(
                f'TURN SETUP: {ob_size:.0%}pot turn overbet builds pot to '
                f'{pot_bb + 2*bet_bb:.0f}BB. '
                f'River jam (1.0x) = {river_bet:.0f}BB. '
                f'SPR after overbet: {round((pot_bb * spr - bet_bb) / (pot_bb + 2*bet_bb), 1)}.'
            )
    else:
        tips.append(
            f'NO OVERBET: Use standard sizing (50-75% pot). '
            f'Range is {"merged" if hand_category in ("top_pair","overpair","two_pair") else "not polarized"}. '
            f'Overbets are exploitable when not balanced with enough bluffs.'
        )

    return OverbetAdvice(
        hand_category=hand_category,
        board_texture=board_texture,
        street=street,
        hero_is_pfr=hero_is_pfr,
        spr=spr,
        pot_bb=pot_bb,
        polarization_score=pol_score,
        should_overbet=should_ob,
        recommended_size=ob_size,
        bet_bb=bet_bb,
        bluffs_per_value=bluffs_per_val,
        required_fold_freq=req_fold,
        overbet_ev=ev,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def oba_one_liner(r: OverbetAdvice) -> str:
    return (
        f'[OBA {r.hand_category}|{r.street}] '
        f'{"OVERBET" if r.should_overbet else "STANDARD"} '
        f'{r.recommended_size:.0%}pot={r.bet_bb:.1f}BB | pol={r.polarization_score:.0%}'
    )
