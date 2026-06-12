"""
River Polarization Guide (river_polarization_guide.py)

Guides how to structure a POLARIZED river range: nuts + bluffs,
no medium-strength hands. Polarization is crucial on the river because:
  - No more cards to come: medium hands have no room to improve
  - Villain can only call or fold (no raise bluff protection needed)
  - GTO river strategy requires mixing value + bluffs at optimal ratio

POLARIZATION THEORY:
  A polarized range = top of range (value) + bottom of range (bluffs).
  Medium-strength hands should CHECK (become bluff catchers).

  WHY POLARIZE?
  - If you bet medium hands: villain check-raises and you're in trouble
  - If you check medium hands: they still win at showdown (SDV = value)
  - Bluffing with low-SDV hands: if called, you would have lost anyway
  - Betting nuts: extracts max value; protects your checking range

  POLARIZATION RATIO (GTO):
    Bluff-to-value ratio = alpha = bet/(pot+bet)
    At 75% pot: alpha = 0.75/1.75 = 0.43 -- 43% bluffs, 57% value
    At 100% pot: alpha = 0.50 -- 50/50 bluff/value
    At 50% pot:  alpha = 0.33 -- 33% bluffs, 67% value

  KEY INSIGHT:
    Villain is indifferent to calling vs folding at GTO frequencies.
    If you have too many bluffs: villain should call with all bluff catchers.
    If you have too few bluffs: villain should fold all bluff catchers.

DISTINCT FROM:
  value_bluff_ratio_advisor.py:  How many bluffs to run (ratio guide)
  bluff_selection_advisor.py:    WHICH hands to bluff with
  river_bluff.py:                River bluff execution and EV
  THIS MODULE:                   HOW to polarize the full range on river;
                                 which hands go in value/bluff/check buckets;
                                 optimal bet sizing for polarized range

Usage:
    from poker.river_polarization_guide import guide_river_polarization, RiverPolarizationPlan, rpg_one_liner

    result = guide_river_polarization(
        hero_hand_category='top_pair',
        hero_has_nuts=False,
        hero_has_blocker=True,
        board_texture='dry',
        hero_position='ip',
        nut_advantage='significant',
        villain_wtsd=0.28,
        pot_bb=50.0,
        bet_size_pct=0.75,
    )
    print(rpg_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Value bet threshold by hand category
VALUE_BET_HANDS = {
    'nuts', 'near_nuts', 'full_house', 'flush', 'straight',
    'set', 'two_pair',
}

# Hands that should CHECK (bluff catchers -- let villain bluff into you)
CHECK_CALL_HANDS = {
    'top_pair', 'overpair', 'strong_top_pair',
    'bottom_two_pair',  # too weak to value bet 3 streets but beats bluffs
}

# Hands that should BLUFF (low SDV, can bluff-catch nothing)
BLUFF_HANDS = {
    'missed_flush_draw', 'missed_straight_draw', 'ace_high_no_pair',
    'missed_oesd', 'air', 'overcards',
}


def _alpha(bet_size_pct: float) -> float:
    return bet_size_pct / (1 + bet_size_pct)


def _gto_bluff_ratio(bet_size_pct: float) -> float:
    """GTO bluff:total ratio = alpha = bet/(pot+bet)"""
    return _alpha(bet_size_pct)


def _hand_bucket(
    hero_hand_category: str,
    hero_has_nuts: bool,
    hero_has_blocker: bool,
) -> str:
    """Assign hand to value/check/bluff bucket."""
    if hero_has_nuts or hero_hand_category in VALUE_BET_HANDS:
        return 'value_bet'
    if hero_hand_category in CHECK_CALL_HANDS:
        return 'check_call'
    if hero_hand_category in BLUFF_HANDS:
        if hero_has_blocker:
            return 'bluff'          # optimal bluff (has blocker)
        else:
            return 'bluff_marginal'  # suboptimal bluff (no blocker)
    return 'check_fold'


def _optimal_bet_size(
    nut_advantage: str,
    hero_position: str,
    villain_wtsd: float,
    hand_bucket: str,
) -> float:
    """Optimal bet size as fraction of pot for a polarized range."""
    if hand_bucket == 'check_call':
        return 0.0   # don't bet medium hands

    if nut_advantage == 'dominant':
        base = 1.00   # overbet when dominant
    elif nut_advantage == 'significant':
        base = 0.75
    elif nut_advantage == 'slight':
        base = 0.60
    else:
        base = 0.50   # standard size with no advantage

    # Calling station: can go bigger with value, but can't bluff
    if villain_wtsd >= 0.40 and hand_bucket == 'value_bet':
        base = max(base, 0.75)   # size up vs station for value
    elif villain_wtsd >= 0.40 and hand_bucket in ('bluff', 'bluff_marginal'):
        return 0.0   # don't bluff stations

    return round(min(1.50, base), 2)


def _polarization_advice(
    hand_bucket: str,
    nut_advantage: str,
    villain_wtsd: float,
    bet_size_pct: float,
    hero_has_blocker: bool,
) -> str:
    gto_bluff_pct = _gto_bluff_ratio(bet_size_pct)
    if hand_bucket == 'value_bet':
        return (
            f'VALUE BET: Bet polarized range. '
            f'At {bet_size_pct:.0%} pot, GTO bluff ratio = {gto_bluff_pct:.0%}. '
            f'For every value hand you bet, include {gto_bluff_pct / (1-gto_bluff_pct):.1f} bluffs.'
        )
    elif hand_bucket == 'check_call':
        return (
            f'CHECK-CALL (BLUFF CATCHER): Do not bet this medium-strength hand. '
            f'Check and call if villain bets. '
            f'Your hand beats villain\'s bluffs at showdown -- protect it by not folding.'
        )
    elif hand_bucket == 'bluff':
        return (
            f'BLUFF: Excellent bluff candidate (has blocker={hero_has_blocker}). '
            f'Bet {bet_size_pct:.0%} pot as part of polarized range. '
            f'WTSD={villain_wtsd:.0%}: {"fold equity exists" if villain_wtsd <= 0.35 else "villain calls a lot -- reduce bluff freq"}.'
        )
    elif hand_bucket == 'bluff_marginal':
        return (
            f'MARGINAL BLUFF (no blocker): Consider checking instead. '
            f'Without blockers, villain\'s calling range is stronger. '
            f'Only bluff if you need to balance range and have position.'
        )
    else:
        return (
            f'CHECK-FOLD: Weak hand with no SDV or blocker. '
            f'Give up vs villain\'s bet. '
            f'Check and fold to most bets.'
        )


@dataclass
class RiverPolarizationPlan:
    # Inputs
    hero_hand_category: str
    hero_has_nuts: bool
    hero_has_blocker: bool
    board_texture: str
    hero_position: str
    nut_advantage: str
    villain_wtsd: float
    pot_bb: float
    bet_size_pct: float

    # Analysis
    hand_bucket: str            # 'value_bet' / 'check_call' / 'bluff' / 'bluff_marginal' / 'check_fold'
    optimal_bet_size: float     # recommended size as fraction of pot
    gto_bluff_ratio: float      # alpha = bet/(pot+bet)
    polarization_advice: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def guide_river_polarization(
    hero_hand_category: str = 'top_pair',
    hero_has_nuts: bool = False,
    hero_has_blocker: bool = True,
    board_texture: str = 'dry',
    hero_position: str = 'ip',
    nut_advantage: str = 'significant',
    villain_wtsd: float = 0.28,
    pot_bb: float = 50.0,
    bet_size_pct: float = 0.75,
) -> RiverPolarizationPlan:
    """
    Guide on how to polarize river range optimally.

    Args:
        hero_hand_category:   Current hand category
        hero_has_nuts:        Hero has the nuts
        hero_has_blocker:     Hero holds blocker card
        board_texture:        'dry' / 'semi_wet' / 'wet' / 'monotone'
        hero_position:        'ip' / 'oop'
        nut_advantage:        'dominant' / 'significant' / 'slight' / 'none'
        villain_wtsd:         Villain's WTSD stat
        pot_bb:               Current pot
        bet_size_pct:         Planned bet size as fraction of pot

    Returns:
        RiverPolarizationPlan
    """
    bucket = _hand_bucket(hero_hand_category, hero_has_nuts, hero_has_blocker)
    opt_size = _optimal_bet_size(nut_advantage, hero_position, villain_wtsd, bucket)
    gto_bluff = _gto_bluff_ratio(bet_size_pct if bucket != 'check_call' else 0.75)
    advice = _polarization_advice(bucket, nut_advantage, villain_wtsd,
                                   opt_size if opt_size > 0 else bet_size_pct,
                                   hero_has_blocker)

    action_label = {
        'value_bet': 'BET_VALUE',
        'check_call': 'CHECK_CALL',
        'bluff': 'BLUFF',
        'bluff_marginal': 'CHECK_OR_BLUFF',
        'check_fold': 'CHECK_FOLD',
    }.get(bucket, 'CHECK')

    verdict = (
        f'[RPG {hero_hand_category}|river|{hero_position}] '
        f'{action_label} {opt_size:.0%}pot '
        f'| bucket={bucket} bluff_ratio={gto_bluff:.0%}'
    )

    reasoning = (
        f'River polarization: {hero_hand_category}. '
        f'Nuts={hero_has_nuts} blocker={hero_has_blocker}. '
        f'Nut advantage={nut_advantage}. Hand bucket={bucket}. '
        f'Optimal size={opt_size:.0%}pot. GTO bluff ratio={gto_bluff:.0%}. '
        f'WTSD={villain_wtsd:.0%}.'
    )

    tips = [advice]

    tips.append(
        f'POLARIZATION MATH at {opt_size if opt_size > 0 else bet_size_pct:.0%} pot: '
        f'alpha = {gto_bluff:.0%}. '
        f'For every 10 value bets, include {gto_bluff*10/(1-gto_bluff):.0f} bluffs (GTO). '
        f'Too many bluffs: villain calls everything. Too few: villain folds everything.'
    )

    if bucket == 'check_call':
        tips.append(
            f'MEDIUM-STRENGTH PROTECTION: {hero_hand_category} is a bluff catcher. '
            f'Betting this hand turns it into a bluff (worse hands fold, better hands call). '
            f'By checking, you protect your hand and induce villain bluffs.'
        )

    if villain_wtsd >= 0.38:
        tips.append(
            f'STATION ADJUSTMENT (WTSD={villain_wtsd:.0%}): '
            f'Value bet more; bluff less. '
            f'This villain reaches showdown often -- bluffs lose EV. '
            f'Size up value bets for maximum extraction.'
        )

    if nut_advantage == 'dominant' and bucket == 'value_bet':
        tips.append(
            f'DOMINANT NUT ADVANTAGE: Consider overbetting (>100% pot). '
            f'Your range has many more nutted hands -- villain cannot call wide. '
            f'Overbets work especially well IP with {board_texture} board.'
        )

    if hero_position == 'oop':
        tips.append(
            f'OOP POLARIZATION: Check-call more when OOP. '
            f'Betting into IP villain gives them information + last action. '
            f'OOP bet range should be very polarized (nuts or air).'
        )

    return RiverPolarizationPlan(
        hero_hand_category=hero_hand_category,
        hero_has_nuts=hero_has_nuts,
        hero_has_blocker=hero_has_blocker,
        board_texture=board_texture,
        hero_position=hero_position,
        nut_advantage=nut_advantage,
        villain_wtsd=villain_wtsd,
        pot_bb=pot_bb,
        bet_size_pct=bet_size_pct,
        hand_bucket=bucket,
        optimal_bet_size=opt_size,
        gto_bluff_ratio=gto_bluff,
        polarization_advice=advice,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rpg_one_liner(r: RiverPolarizationPlan) -> str:
    action = {
        'value_bet': 'BET_VALUE',
        'check_call': 'CHECK_CALL',
        'bluff': 'BLUFF',
        'bluff_marginal': 'CHECK_OR_BLUFF',
        'check_fold': 'CHECK_FOLD',
    }.get(r.hand_bucket, 'CHECK')
    return (
        f'[RPG {r.hero_hand_category}|river|{r.hero_position}] '
        f'{action} {r.optimal_bet_size:.0%}pot '
        f'| bluff_ratio={r.gto_bluff_ratio:.0%} bucket={r.hand_bucket}'
    )
