"""
Live Poker Adjustments (live_poker_adjustments.py)

Strategy adjustments for live casino/cardroom poker vs online poker.
Live and online poker require meaningfully different strategies due to:
  - Player pool quality (live = much weaker/looser on average)
  - Game pace (live = 25-35 hands/hour vs 70-100 online)
  - Rake structure (often capped; more favorable at higher limits)
  - No HUD stats; reads are observational
  - Deep effective stacks (live games often play 150-300bb effective)
  - Limping is common and acceptable (online: mostly open-raise)
  - Larger preflop sizing norms (live: 4-5x; online: 2.5x)

LIVE GAME PLAYER POOL CHARACTERISTICS:
  Recreational players dominate live games:
  - Average VPIP ~45-65% vs ~22-28% online
  - Average PFR ~12-18% vs ~18-22% online
  - Very low 3-bet frequency (<5% live vs ~8-10% online)
  - High WTSD (~45-55% vs ~28-32% online)
  - Low fold-to-cbet (~35-45% vs ~45-55% online)

LIVE-SPECIFIC STRATEGY ADJUSTMENTS:
  1. OPEN SIZING: Use 4-5x (or even 6x) vs limpers.
     Live players call large opens just as often as small ones.
  2. VALUE BET THINNER: Any pair has value vs wide calling ranges.
     Middle pair is often a value bet in live games.
  3. BLUFF LESS: Live players call too much; pure bluffs lose value.
  4. 3-BET TIGHTER: Live 3-bet polarization is huge; value-only is fine.
  5. CALL 3-BETS WIDER: Live 3-bet ranges are tighter = more value.
  6. LIMP BEHIND: Live games have multi-limp pots; limp-raise traps.
  7. RAISE SIZING ON DRAWS: Larger draw raises get called anyway.
  8. IMPLIED ODDS BETTER: Deep stacks + calling stations = huge payoffs.
  9. ISOLATE LIMPERS: Iso-raise wide vs recreational limpers.

DISTINCT FROM:
  game_selection.py:          Which game to play
  game_selection_advisor.py:  Game selection criteria
  multitable_strategy_advisor.py: Adjustments for online multi-tabling
  THIS MODULE:                Specific tactical adjustments for LIVE
                              vs online poker; sizing, frequency, and
                              range changes for live player pool.

Usage:
    from poker.live_poker_adjustments import get_live_adjustments, LiveAdjustmentPlan, lap_one_liner

    result = get_live_adjustments(
        stakes='2_5',
        hero_position='btn',
        action_facing='limp_limp',
        hero_hand_category='top_pair',
        pot_bb=15.0,
        spr=8.0,
        board_texture='semi_wet',
        limpers=2,
        villain_estimated_vpip=0.55,
    )
    print(lap_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List


# Live vs online VPIP estimates by stakes
LIVE_VPIP_BY_STAKES = {
    '1_2':   0.65,   # very soft; home game quality
    '1_3':   0.60,
    '2_5':   0.52,
    '5_10':  0.42,
    '10_25': 0.35,
    '25_50': 0.28,
}

# Live open sizing norm (multiplier of BB)
LIVE_OPEN_SIZE = {
    'btn': 4.0,
    'co':  4.0,
    'hj':  4.0,
    'utg': 4.0,
    'sb':  4.0,
    'bb':  0.0,
}

# Iso-raise sizing with limpers (open_size + per_limper)
ISO_SIZE_PER_LIMPER = 1.5   # e.g. open=4x + 2 limpers -> 4 + 3 = 7x

# Live fold-to-cbet estimate by stakes
LIVE_FOLD_CBET = {
    '1_2':  0.32,
    '1_3':  0.34,
    '2_5':  0.38,
    '5_10': 0.44,
    '10_25': 0.50,
    '25_50': 0.54,
}

# Live thin value threshold: minimum hand to value bet all streets
LIVE_THIN_VALUE = {
    '1_2':   'middle_pair',
    '1_3':   'middle_pair',
    '2_5':   'top_pair_weak',
    '5_10':  'top_pair',
    '10_25': 'top_pair',
    '25_50': 'strong_top_pair',
}

# Live cbet recommended sizes (larger than online due to loose callers)
LIVE_CBET_SIZE = {
    'flop': 0.65,   # online: 0.50-0.60
    'turn': 0.70,
    'river': 0.75,
}

# Live game categories
LIVE_GAME_TYPE = {
    (0.0, 0.40):  'semi_tough',
    (0.40, 0.50): 'soft',
    (0.50, 0.60): 'very_soft',
    (0.60, 1.00): 'extremely_soft',
}


def _game_type(villain_estimated_vpip: float) -> str:
    for (lo, hi), gtype in LIVE_GAME_TYPE.items():
        if lo <= villain_estimated_vpip < hi:
            return gtype
    return 'standard'


def _iso_size(position: str, limpers: int) -> float:
    base = LIVE_OPEN_SIZE.get(position.lower(), 4.0)
    return base + limpers * ISO_SIZE_PER_LIMPER


def _live_cbet_size(board_texture: str, street: str) -> float:
    base = LIVE_CBET_SIZE.get(street, 0.65)
    if board_texture in ('wet', 'monotone'):
        base = max(0.50, base - 0.10)  # still larger than online
    return base


def _should_value_bet_live(hand_category: str, stakes: str, game_type: str) -> bool:
    threshold = LIVE_THIN_VALUE.get(stakes, 'top_pair')
    rank = {
        'air': 0, 'gutshot': 1, 'overcards': 1,
        'bottom_pair': 2, 'middle_pair': 3, 'top_pair_weak': 4,
        'top_pair': 5, 'strong_top_pair': 6, 'overpair': 7,
        'two_pair': 8, 'set': 9, 'straight': 10,
        'flush': 11, 'full_house': 12, 'nuts': 13,
    }
    hand_r = rank.get(hand_category, 0)
    thresh_r = rank.get(threshold, 5)
    if game_type == 'extremely_soft':
        thresh_r = max(0, thresh_r - 1)  # even thinner value
    return hand_r >= thresh_r


def _should_bluff_live(game_type: str, villain_estimated_vpip: float) -> bool:
    if villain_estimated_vpip >= 0.55:
        return False   # too many callers; bluffs unprofitable
    if villain_estimated_vpip >= 0.45:
        return False   # semi-bluff only with equity
    return True  # semi-tough games: balanced bluff frequency


def _three_bet_live(hand_category: str, game_type: str) -> str:
    strong_hands = {'nuts', 'near_nuts', 'full_house', 'flush', 'straight',
                    'set', 'two_pair', 'overpair'}
    if hand_category in strong_hands:
        return 'three_bet_value'
    if game_type in ('very_soft', 'extremely_soft'):
        return 'fold_or_call'   # bluff 3-bets are not profitable vs callers
    return 'consider_three_bet_balanced'


def _implied_odds_adjustment(spr: float, game_type: str) -> str:
    if spr >= 10 and game_type in ('very_soft', 'extremely_soft'):
        return 'excellent_implied_odds'
    elif spr >= 6:
        return 'good_implied_odds'
    else:
        return 'limited_implied_odds'


@dataclass
class LiveAdjustmentPlan:
    # Inputs
    stakes: str
    hero_position: str
    action_facing: str
    hero_hand_category: str
    pot_bb: float
    spr: float
    board_texture: str
    limpers: int
    villain_estimated_vpip: float

    # Analysis
    game_type: str               # 'soft' / 'very_soft' / 'extremely_soft'
    estimated_fold_cbet: float
    live_cbet_size: float        # recommended cbet size vs live field
    iso_raise_size: float        # recommended iso vs limpers
    should_value_bet: bool
    should_bluff: bool
    three_bet_recommendation: str
    implied_odds_quality: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def get_live_adjustments(
    stakes: str = '2_5',
    hero_position: str = 'btn',
    action_facing: str = 'limp_limp',
    hero_hand_category: str = 'top_pair',
    pot_bb: float = 15.0,
    spr: float = 8.0,
    board_texture: str = 'semi_wet',
    limpers: int = 2,
    villain_estimated_vpip: float = 0.55,
) -> LiveAdjustmentPlan:
    """
    Generate strategy adjustments for live poker environment.

    Args:
        stakes:                   Game stakes ('1_2', '2_5', '5_10', etc.)
        hero_position:            Hero's position
        action_facing:            Preflop situation ('limp_limp', 'open', 'three_bet')
        hero_hand_category:       Current hand strength
        pot_bb:                   Current pot in BB
        spr:                      Stack-to-pot ratio
        board_texture:            Board texture
        limpers:                  Number of limpers in the pot
        villain_estimated_vpip:   Estimated villain VPIP (visual read)

    Returns:
        LiveAdjustmentPlan
    """
    gtype = _game_type(villain_estimated_vpip)
    fold_cbet = LIVE_FOLD_CBET.get(stakes, 0.38)
    cbet_size = _live_cbet_size(board_texture, 'flop')
    iso_size = _iso_size(hero_position, limpers)
    value_ok = _should_value_bet_live(hero_hand_category, stakes, gtype)
    bluff_ok = _should_bluff_live(gtype, villain_estimated_vpip)
    tbet = _three_bet_live(hero_hand_category, gtype)
    implied = _implied_odds_adjustment(spr, gtype)

    verdict = (
        f'[LAP {gtype.upper()}|{stakes}|{hero_position}] '
        f'{"VALUE" if value_ok else "CHECK_FOLD"} | '
        f'iso={iso_size:.1f}x cbet={cbet_size:.0%} bluff={"Y" if bluff_ok else "N"}'
    )

    reasoning = (
        f'Live poker adjustment for {stakes} game at {hero_position}. '
        f'Game type: {gtype} (est. VPIP={villain_estimated_vpip:.0%}). '
        f'Fold-to-cbet estimate: {fold_cbet:.0%} (online avg: 50%). '
        f'Recommended iso-raise vs {limpers} limpers: {iso_size:.1f}x. '
        f'Hand {hero_hand_category}: value_bet={value_ok}, bluff={bluff_ok}. '
        f'Three-bet advice: {tbet}.'
    )

    tips = []

    tips.append(
        f'GAME TYPE: {gtype.upper()} live game (est. VPIP={villain_estimated_vpip:.0%}). '
        f'Live games are typically much softer than online. '
        f'Thin value threshold: {LIVE_THIN_VALUE.get(stakes, "top_pair")} and above is profitable.'
    )

    if limpers > 0 and 'limp' in action_facing:
        tips.append(
            f'ISO-RAISE SIZING: {iso_size:.1f}x (base {LIVE_OPEN_SIZE.get(hero_position.lower(), 4)}x + {limpers} limpers x {ISO_SIZE_PER_LIMPER}x). '
            f'Live players call large isos as often as small ones. '
            f'Isolate wide: suited connectors, any Broadway, pairs 22+, suited aces. '
            f'Goal: play heads-up in position vs a weak limper.'
        )

    tips.append(
        f'LIVE CBET SIZE: Use {cbet_size:.0%}pot on {board_texture} flop '
        f'(vs online standard 50-55%). '
        f'Estimated fold-to-cbet at {stakes}: {fold_cbet:.0%}. '
        f'{"Sizing up matters less since fold rate is already low." if fold_cbet <= 0.40 else "Larger sizing still folds out some hands."}'
    )

    if not bluff_ok:
        tips.append(
            f'NO BLUFFING IN {gtype.upper()} GAME: '
            f'VPIP={villain_estimated_vpip:.0%} means villain calls {1-fold_cbet:.0%} of cbets. '
            f'Pure bluffs are -EV. Semi-bluffs with 8+ outs are marginal. '
            f'Shift all "bluff" combos into value bets with thinner hands.'
        )
    else:
        tips.append(
            f'SEMI-TOUGH GAME: Occasional bluffs can work. '
            f'Only bluff: (1) on dry boards, (2) vs tight players, '
            f'(3) with clear fold equity (villain showed weakness). '
            f'Avoid bluffing passive recreational players who call with any pair.'
        )

    tips.append(
        f'THREE-BET LIVE: {tbet.upper()}. '
        f'Live 3-bet ranges are tighter than online. '
        f'Villain 3-bets = usually QQ+/AK. '
        f'Calling 3-bets wider is correct (villain range is strong not balanced). '
        f'Bluff 3-bets are NOT profitable vs calling stations.'
    )

    if implied == 'excellent_implied_odds':
        tips.append(
            f'EXCELLENT IMPLIED ODDS (spr={spr:.1f}, {gtype} game): '
            f'Set mine profitably with pairs 22+ (need 15:1 implied odds = roughly met). '
            f'Call suited connectors in multiway pots. '
            f'Speculative hands gain massive value when opponent cannot fold bottom set.'
        )

    return LiveAdjustmentPlan(
        stakes=stakes,
        hero_position=hero_position,
        action_facing=action_facing,
        hero_hand_category=hero_hand_category,
        pot_bb=pot_bb,
        spr=spr,
        board_texture=board_texture,
        limpers=limpers,
        villain_estimated_vpip=villain_estimated_vpip,
        game_type=gtype,
        estimated_fold_cbet=fold_cbet,
        live_cbet_size=cbet_size,
        iso_raise_size=iso_size,
        should_value_bet=value_ok,
        should_bluff=bluff_ok,
        three_bet_recommendation=tbet,
        implied_odds_quality=implied,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def lap_one_liner(r: LiveAdjustmentPlan) -> str:
    return (
        f'[LAP {r.game_type.upper()}|{r.stakes}|{r.hero_position}] '
        f'iso={r.iso_raise_size:.1f}x cbet={r.live_cbet_size:.0%} '
        f'| thin={LIVE_THIN_VALUE.get(r.stakes, "top_pair")} bluff={"N" if not r.should_bluff else "Y"}'
    )
