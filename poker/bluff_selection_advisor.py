"""
Bluff Selection Advisor (bluff_selection_advisor.py)

Given a board and hero's range, identifies and ranks the BEST hands
to use as bluffs. Not all bluffs are equal -- optimal bluffs have:
  1. Good blockers (reduce villain's strong hands)
  2. Low showdown value (gaining nothing by checking)
  3. Some equity (partial protection against calling)
  4. Good card removal (remove cards from villain's calling range)

BLUFF SELECTION CRITERIA:
  TIER 1 (Best bluffs):
    - Missed flush draws (have flush blockers, no SDV)
    - Ace blocker hands (A-high with no pair)
    - Missed OESD/straight draws

  TIER 2 (Good bluffs):
    - Backdoor missed draws
    - Weak pair with good kicker/blocker
    - Two overcards with specific blockers

  TIER 3 (Acceptable):
    - Pure air with position advantage
    - Low equity hands in favorable spots

  AVOID BLUFFING WITH:
    - Hands with showdown value (may win at showdown)
    - Hands that block villain's folds (calling range)
    - Hands without blockers on heavy texture boards

DISTINCT FROM:
  river_bluff.py:          River bluff execution (EV calculation)
  value_bluff_ratio_advisor.py: How many bluffs to use (ratio)
  triple_barrel.py:        Triple barrel bluff decision
  THIS MODULE:             WHICH specific hands to select as bluffs;
                           ranks hands by bluff quality score;
                           board-specific blocker analysis

Usage:
    from poker.bluff_selection_advisor import advise_bluff_selection, BluffSelectionAdvice, bsa_one_liner

    result = advise_bluff_selection(
        street='river',
        board_texture='semi_wet',
        hero_hand_category='missed_flush_draw',
        hero_has_ace_blocker=True,
        hero_has_flush_blocker=True,
        hero_has_straight_blocker=False,
        hero_equity=0.15,
        villain_wtsd=0.30,
        villain_af=2.5,
        pot_bb=40.0,
        bet_size_pct=0.75,
    )
    print(bsa_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Blocker quality scores
BLOCKER_SCORES = {
    'ace_blocker':         0.35,   # blocks AA/AK/Ax in villain's range
    'flush_blocker':       0.30,   # blocks nut flush
    'straight_blocker':    0.20,   # blocks nut straight (specific card)
    'king_blocker':        0.20,   # blocks KK/KQ
    'set_blocker':         0.25,   # blocks specific set (trips)
    'two_pair_blocker':    0.15,   # blocks two pair combos
    'nuts_blocker':        0.40,   # direct nut blocker
}

# Hand category SDV scores (how much showdown value this hand has)
SDV_SCORES = {
    'missed_flush_draw':   0.05,   # almost zero SDV
    'missed_straight_draw': 0.05,
    'missed_oesd':         0.05,
    'missed_gutshot':      0.08,
    'ace_high_no_pair':    0.12,
    'king_high_no_pair':   0.08,
    'overcards':           0.10,
    'weak_pair':           0.30,   # has some SDV
    'middle_pair':         0.50,
    'bottom_pair':         0.35,
    'top_pair':            0.70,
    'air':                 0.02,
    'backdoor_missed':     0.06,
}

# Hand category equity (vs villain's range)
HAND_EQUITY = {
    'missed_flush_draw':   0.10,
    'missed_straight_draw': 0.08,
    'missed_oesd':         0.08,
    'ace_high_no_pair':    0.20,
    'overcards':           0.18,
    'weak_pair':           0.25,
    'air':                 0.05,
    'backdoor_missed':     0.08,
    'missed_gutshot':      0.08,
}


def _bluff_score(
    hero_hand_category: str,
    has_ace_blocker: bool,
    has_flush_blocker: bool,
    has_straight_blocker: bool,
    street: str,
    board_texture: str,
    villain_wtsd: float,
) -> float:
    """
    Score 0-1 for how good this hand is as a bluff.
    Higher = better bluff candidate.
    """
    score = 0.0

    # Blocker component (up to 0.40)
    if has_ace_blocker:
        score += BLOCKER_SCORES['ace_blocker']
    if has_flush_blocker and board_texture in ('semi_wet', 'wet', 'monotone'):
        score += BLOCKER_SCORES['flush_blocker']
    if has_straight_blocker:
        score += BLOCKER_SCORES['straight_blocker']

    # Low SDV component (good bluffs have no SDV)
    sdv = SDV_SCORES.get(hero_hand_category, 0.30)
    score += (1.0 - sdv) * 0.30   # 0-0.30 for low SDV

    # Some equity protection
    equity = HAND_EQUITY.get(hero_hand_category, 0.10)
    score += equity * 0.20   # 0-0.20 for equity

    # Fold success modifier
    if villain_wtsd <= 0.25:
        score += 0.10   # nit folds more; bluffs are more profitable
    elif villain_wtsd >= 0.40:
        score -= 0.10   # station; bluffs less profitable

    return round(min(1.0, max(0.0, score)), 3)


def _bluff_tier(score: float) -> str:
    if score >= 0.70:
        return 'tier1_optimal'
    elif score >= 0.50:
        return 'tier2_good'
    elif score >= 0.30:
        return 'tier3_acceptable'
    else:
        return 'tier4_avoid'


def _recommended_bet_size(
    hero_hand_category: str,
    has_flush_blocker: bool,
    bet_size_pct: float,
    street: str,
    villain_wtsd: float,
) -> float:
    """Optimal bluff bet size as fraction of pot."""
    base = bet_size_pct   # use requested size as starting point

    # Flush blocker bluffs: larger is better (represent flush)
    if has_flush_blocker:
        base = max(base, 0.75)

    # River: polarize bigger
    if street == 'river' and base < 0.75:
        base = 0.75

    # Vs calling station: bluffing is worse; reduce size or just don't bluff
    if villain_wtsd >= 0.40:
        base = min(base, 0.50)

    return round(base, 2)


def _ev_of_bluff(
    pot_bb: float,
    bet_size_pct: float,
    villain_wtsd: float,
    board_texture: str,
    street: str,
    bluff_score: float,
) -> float:
    """Estimated EV of bluffing."""
    bet_bb = bet_size_pct * pot_bb

    # Fold probability estimate
    base_fold = max(0.25, 1.0 - villain_wtsd)

    # Texture adjustment
    if board_texture in ('wet', 'monotone'):
        base_fold -= 0.05
    elif board_texture == 'dry':
        base_fold += 0.05

    # Bluff quality adjustment
    base_fold += (bluff_score - 0.50) * 0.15

    fold_prob = min(0.80, max(0.15, base_fold))
    ev = fold_prob * pot_bb - (1 - fold_prob) * bet_bb
    return round(ev, 2)


def _should_bluff(bluff_score: float, ev: float, villain_wtsd: float,
                  street: str) -> bool:
    if villain_wtsd >= 0.45:
        return False   # never bluff calling stations
    if ev <= -5.0:
        return False
    if bluff_score >= 0.40 and ev >= 0:
        return True
    if bluff_score >= 0.60:   # high quality bluff can tolerate slight neg EV
        return ev >= -2.0
    return False


@dataclass
class BluffSelectionAdvice:
    # Inputs
    street: str
    board_texture: str
    hero_hand_category: str
    hero_has_ace_blocker: bool
    hero_has_flush_blocker: bool
    hero_has_straight_blocker: bool
    hero_equity: float
    villain_wtsd: float
    villain_af: float
    pot_bb: float
    bet_size_pct: float

    # Analysis
    bluff_score: float         # 0-1 quality as bluff
    bluff_tier: str            # 'tier1_optimal' to 'tier4_avoid'
    recommended_bet_size: float
    bluff_ev: float            # estimated EV of bluffing
    should_bluff: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_bluff_selection(
    street: str = 'river',
    board_texture: str = 'semi_wet',
    hero_hand_category: str = 'missed_flush_draw',
    hero_has_ace_blocker: bool = True,
    hero_has_flush_blocker: bool = True,
    hero_has_straight_blocker: bool = False,
    hero_equity: float = 0.15,
    villain_wtsd: float = 0.30,
    villain_af: float = 2.5,
    pot_bb: float = 40.0,
    bet_size_pct: float = 0.75,
) -> BluffSelectionAdvice:
    """
    Advise on bluff selection quality for current hand and board.

    Args:
        street:                  'flop' / 'turn' / 'river'
        board_texture:           'dry' / 'semi_wet' / 'wet' / 'monotone' / 'paired'
        hero_hand_category:      'missed_flush_draw' / 'ace_high_no_pair' / 'air' / etc.
        hero_has_ace_blocker:    Hero holds an Ace
        hero_has_flush_blocker:  Hero holds a card in the flush suit
        hero_has_straight_blocker: Hero holds a card completing the straight
        hero_equity:             Current equity
        villain_wtsd:            Villain's WTSD stat
        villain_af:              Villain AF
        pot_bb:                  Current pot
        bet_size_pct:            Intended bet size as fraction of pot

    Returns:
        BluffSelectionAdvice
    """
    score = _bluff_score(
        hero_hand_category, hero_has_ace_blocker, hero_has_flush_blocker,
        hero_has_straight_blocker, street, board_texture, villain_wtsd
    )
    tier = _bluff_tier(score)
    rec_size = _recommended_bet_size(hero_hand_category, hero_has_flush_blocker,
                                      bet_size_pct, street, villain_wtsd)
    ev = _ev_of_bluff(pot_bb, rec_size, villain_wtsd, board_texture, street, score)
    bluff_ok = _should_bluff(score, ev, villain_wtsd, street)

    verdict = (
        f'[BSA {tier.upper()}|{street}|{board_texture}] '
        f'score={score:.2f} ev={ev:+.1f}BB | '
        f'bluff={"YES" if bluff_ok else "NO"} size={rec_size:.0%}pot'
    )

    reasoning = (
        f'Bluff selection: {hero_hand_category} on {board_texture} {street}. '
        f'Blockers: ace={hero_has_ace_blocker} flush={hero_has_flush_blocker} '
        f'straight={hero_has_straight_blocker}. '
        f'Bluff score={score:.2f} ({tier}). EV={ev:+.1f}BB. '
        f'Should bluff={bluff_ok}. Rec size={rec_size:.0%}pot.'
    )

    tips = []
    if bluff_ok:
        tips.append(
            f'BLUFF RECOMMENDED: {hero_hand_category} scores {score:.2f} ({tier}) as a bluff. '
            f'Bet {rec_size:.0%} pot ({rec_size * pot_bb:.1f}BB). '
            f'Estimated EV = {ev:+.1f}BB vs pot={pot_bb:.1f}BB.'
        )
    else:
        tips.append(
            f'AVOID BLUFFING: Score={score:.2f} ({tier}). '
            f'EV={ev:+.1f}BB -- not profitable enough. '
            f'Check or use this hand to bluff catch instead.'
        )

    blocker_list = []
    if hero_has_ace_blocker:
        blocker_list.append('ace_blocker')
    if hero_has_flush_blocker:
        blocker_list.append('flush_blocker')
    if hero_has_straight_blocker:
        blocker_list.append('straight_blocker')

    tips.append(
        f'BLOCKER ANALYSIS: Active blockers: {", ".join(blocker_list) if blocker_list else "none"}. '
        f'Hand SDV={SDV_SCORES.get(hero_hand_category, "n/a")} (lower = better bluff). '
        f'Best bluffs: missed flush draws (0.05 SDV) + ace blocker.'
    )

    if villain_wtsd >= 0.40:
        tips.append(
            f'CALLING STATION (WTSD={villain_wtsd:.0%}): Do NOT bluff. '
            f'This villain reaches showdown too often. '
            f'Reserve bluffs for villains with WTSD < 30%.'
        )
    elif villain_wtsd <= 0.22:
        tips.append(
            f'FOLDER (WTSD={villain_wtsd:.0%}): Excellent bluff spot. '
            f'This villain folds too often. Increase bluff frequency above GTO. '
            f'Bluff more freely -- especially with position.'
        )

    if board_texture == 'dry' and not hero_has_ace_blocker:
        tips.append(
            f'DRY BOARD WITHOUT ACE: Bluffs are riskier on dry boards without blockers. '
            f'Villain often has top pair or better. '
            f'Consider giving up unless you have strong fold equity.'
        )

    return BluffSelectionAdvice(
        street=street,
        board_texture=board_texture,
        hero_hand_category=hero_hand_category,
        hero_has_ace_blocker=hero_has_ace_blocker,
        hero_has_flush_blocker=hero_has_flush_blocker,
        hero_has_straight_blocker=hero_has_straight_blocker,
        hero_equity=hero_equity,
        villain_wtsd=villain_wtsd,
        villain_af=villain_af,
        pot_bb=pot_bb,
        bet_size_pct=bet_size_pct,
        bluff_score=score,
        bluff_tier=tier,
        recommended_bet_size=rec_size,
        bluff_ev=ev,
        should_bluff=bluff_ok,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bsa_one_liner(r: BluffSelectionAdvice) -> str:
    return (
        f'[BSA {r.bluff_tier.upper()}|{r.street}|{r.board_texture}] '
        f'score={r.bluff_score:.2f} ev={r.bluff_ev:+.1f}BB | '
        f'{"BLUFF" if r.should_bluff else "NO_BLUFF"} {r.recommended_bet_size:.0%}pot'
    )
