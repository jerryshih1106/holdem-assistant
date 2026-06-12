"""
River Check-Fold Range Guide (river_check_fold_range_guide.py)

Determines which hands should CHECK-FOLD on the river (give up equity without
bluffing), as opposed to check-call, check-raise bluff, or lead bluff.

THEORY:
  RIVER CHECK-FOLD vs ALTERNATIVES:
  1. CHECK-FOLD:    Accept 0 EV; give up; avoid investing with weak equity
  2. CHECK-CALL:    Call villain's river bet with showdown value
  3. LEAD BLUFF:    Bet out as bluff with blockers and no SDV
  4. CHECK-RAISE BLUFF: Trap/bluff with strong hand rep after villain bets

  WHEN TO CHECK-FOLD:
  1. No showdown value (air, missed draw with no pairs)
  2. Weak showdown value below villain's leading range
  3. Poor blockers (not blocking villain's value range)
  4. Villain's betting frequency is low (< 40% = they have value when they bet)
  5. Villain is a calling station (cannot bluff-raise)

  CHECK-FOLD vs CHECK-CALL:
  - Check-fold when SDV < 0.35 (less than 35% equity vs villain's check range)
  - Check-call when SDV >= 0.35 and villain bet is reasonable size
  - Check-fold when villain's bet size suggests only strong hands

  CHECK-FOLD FREQUENCY:
  MDF = pot / (pot + bet) = fraction of range hero must continue
  Hero's check-fold frequency = 1 - MDF of villain's expected bet size
  Example: villain bets 2/3 pot -> MDF = 60% -> check-fold 40% of range

  HAND SELECTION FOR CHECK-FOLD RANGE:
  Put WEAKEST hands in check-fold range (lowest equity vs villain check range):
  - Missed draws (busted flush/straight)
  - Bottom pair on a paired board
  - Overcards with no pair

DISTINCT FROM:
  missed_draw_advisor.py:        Missed draw general advice
  river_decision.py:             General river decisions
  river_bluff_catch_advisor.py:  When to catch bluffs
  THIS MODULE:                   CHECK-FOLD SPECIFIC; SDV threshold; frequency
                                 calculation; hand selection priority for give-up.
"""

from dataclasses import dataclass, field
from typing import List


CHECK_FOLD_SDV_THRESHOLD: dict = {
    'fish':   0.30,  # fish bets with wider range; SDV threshold lower
    'rec':    0.33,
    'nit':    0.42,  # nit bets only value; high threshold to continue
    'lag':    0.28,  # lag bluffs more; call wider
    'reg':    0.36,
}

VILLAIN_RIVER_BET_FREQ: dict = {
    'fish':   0.45,
    'rec':    0.50,
    'nit':    0.32,
    'lag':    0.72,
    'reg':    0.55,
}

HAND_SDV_ESTIMATE: dict = {
    'missed_flush_draw':   0.05,
    'missed_straight':     0.05,
    'bottom_pair':         0.25,
    'middle_pair_weak':    0.38,
    'middle_pair':         0.45,
    'top_pair_wk':         0.52,
    'top_pair_gk':         0.65,
    'two_pair':            0.78,
    'set':                 0.90,
    'air':                 0.05,
    'overcard_no_pair':    0.10,
}


def _mdf_for_bet(bet_frac: float) -> float:
    return round(1.0 / (1.0 + bet_frac), 3)


def _check_fold_threshold(villain_type: str) -> float:
    return CHECK_FOLD_SDV_THRESHOLD.get(villain_type, 0.35)


def _hand_sdv(hand_strength: str) -> float:
    return HAND_SDV_ESTIMATE.get(hand_strength, 0.30)


def _villain_expected_bet_frac(villain_type: str) -> float:
    if villain_type == 'lag':
        return 0.70
    elif villain_type == 'nit':
        return 0.65
    elif villain_type == 'fish':
        return 0.55
    return 0.60


def _check_fold_frequency(villain_type: str) -> float:
    bet_frac = _villain_expected_bet_frac(villain_type)
    mdf = _mdf_for_bet(bet_frac)
    return round(1.0 - mdf, 3)


def _river_action(
    sdv: float,
    threshold: float,
    blocker_score: int,
    villain_bet_freq: float,
) -> str:
    if sdv >= threshold + 0.15:
        return 'CHECK_CALL'
    if sdv >= threshold:
        return 'CHECK_CALL_BORDERLINE'
    if sdv < 0.15 and blocker_score >= 6:
        return 'CONSIDER_LEAD_BLUFF'
    if sdv < 0.15 and villain_bet_freq >= 0.55:
        return 'CHECK_FOLD'  # lag bets wide; no value in calling air
    return 'CHECK_FOLD'


@dataclass
class RiverCheckFoldResult:
    villain_type: str
    hand_strength: str

    hand_sdv: float
    sdv_threshold: float
    should_check_fold: bool

    mdf: float
    check_fold_frequency: float
    blocker_score: int

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_river_check_fold(
    villain_type: str = 'reg',
    hand_strength: str = 'missed_flush_draw',
    pot_bb: float = 20.0,
    villain_bet_frac: float = 0.60,
    blocker_score: int = 3,
    hero_range_sdv_distribution: float = 0.50,
) -> RiverCheckFoldResult:
    """
    Determine whether to check-fold or pursue an alternative line on the river.

    Args:
        villain_type:                Villain type ('fish','rec','nit','lag','reg')
        hand_strength:               Hero hand ('missed_flush_draw','missed_straight',
                                     'bottom_pair','air','overcard_no_pair', etc.)
        pot_bb:                      Current pot in BB
        villain_bet_frac:            Expected villain bet size if they bet (fraction of pot)
        blocker_score:               How well hero blocks villain's value range (1-10)
        hero_range_sdv_distribution: Average SDV of hero's range (for frequency calc)

    Returns:
        RiverCheckFoldResult
    """
    sdv = _hand_sdv(hand_strength)
    threshold = _check_fold_threshold(villain_type)
    mdf = _mdf_for_bet(villain_bet_frac)
    cf_freq = _check_fold_frequency(villain_type)
    vbet_freq = VILLAIN_RIVER_BET_FREQ.get(villain_type, 0.50)
    should_cf = sdv < threshold

    action = _river_action(sdv, threshold, blocker_score, vbet_freq)

    verdict = (
        f'[RCF {hand_strength}|{villain_type}] '
        f'{action} SDV={sdv:.0%} threshold={threshold:.0%} '
        f'MDF={mdf:.0%} cf_freq={cf_freq:.0%}'
    )

    reasoning = (
        f'River check-fold analysis: {hand_strength} vs {villain_type}. '
        f'Hand SDV={sdv:.0%}; threshold={threshold:.0%}; '
        f'should check-fold={should_cf}. '
        f'MDF for {villain_bet_frac:.0%}pot bet = {mdf:.0%}. '
        f'Range check-fold frequency={cf_freq:.0%}. '
        f'Action: {action}.'
    )

    tips = []

    tips.append(
        f'CHECK-FOLD DECISION: SDV={sdv:.0%} vs threshold={threshold:.0%}. '
        f'{"CHECK-FOLD: hand equity insufficient to continue." if should_cf else "SDV above threshold -- consider check-call."}'
    )

    tips.append(
        f'RANGE FREQUENCY: Check-fold {cf_freq:.0%} of range vs {villain_type}. '
        f'MDF={mdf:.0%} -- continue at least {mdf:.0%} of range to prevent exploitation. '
        f'This hand (SDV={sdv:.0%}) is in the bottom {(1-mdf):.0%} -- check-fold.'
    )

    if sdv < 0.15 and blocker_score >= 6:
        tips.append(
            f'LEAD BLUFF OPTION: Very low SDV but strong blockers (score={blocker_score}/10). '
            f'Consider leading as bluff instead of check-folding. '
            f'Blockers compensate for weak equity; villain forced to fold strong hands.'
        )
    elif sdv < 0.15:
        tips.append(
            f'GIVE UP: {hand_strength} has SDV={sdv:.0%} and weak blockers ({blocker_score}/10). '
            f'Check and fold to villain bet. No profitable continuation available.'
        )

    if hand_strength in ('missed_flush_draw', 'missed_straight'):
        tips.append(
            f'MISSED DRAW: {hand_strength} has minimal showdown value ({sdv:.0%}). '
            f'Villain often has made hand. Check-fold unless holding strong nut blockers. '
            f'Do not bluff-catch with missed draws against {villain_type}.'
        )

    return RiverCheckFoldResult(
        villain_type=villain_type,
        hand_strength=hand_strength,
        hand_sdv=sdv,
        sdv_threshold=threshold,
        should_check_fold=should_cf,
        mdf=mdf,
        check_fold_frequency=cf_freq,
        blocker_score=blocker_score,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rcf_one_liner(r: RiverCheckFoldResult) -> str:
    return (
        f'[RCF {r.hand_strength}|{r.villain_type}] '
        f'{r.recommended_action} SDV={r.hand_sdv:.0%} '
        f'cf_freq={r.check_fold_frequency:.0%} MDF={r.mdf:.0%}'
    )
