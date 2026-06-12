"""
River Check-Raise Bluff Advisor (river_xr_bluff.py)

Identifies when to CHECK-RAISE BLUFF on the river:
which hands are ideal CR bluffs, what fold% is needed,
and how to size the check-raise.

THEORY:
  RIVER CHECK-RAISE BLUFF requires all of:
  1. Hero is out-of-position (must check first)
  2. Villain bets river at high frequency (wide value+bluff range)
  3. Hero's hand has NO showdown value (pure air is ideal)
  4. Hero has BLOCKERS to villain's value hands or calling hands
  5. Board texture allows the story (hero's check-raise represents something)

  EV CALCULATION:
    fold_ev   = fold_pct * current_pot
    call_ev   = (1 - fold_pct) * (-cr_size)  [hero loses CR when called]
    EV(CR)    = fold_ev + call_ev
    Break-even fold% = cr_size / (pot_before_cr + cr_raise_amount)
    where cr_raise_amount = cr_size - villain_bet

  IDEAL CR BLUFF HAND PROPERTIES:
  1. No showdown value (0% equity at showdown)
  2. Blocks villain's CALLING range (nuts-blockers reduce villain calls)
  3. Does NOT block villain's FOLDING range (want villain to have fold hands)
  4. Represents a hand on the current board texture

  VILLAIN BET FREQUENCY:
  - AF >= 3.0 or river bet% >= 60%: villain bets many hands; CR bluff viable
  - AF 1.5-3.0: moderate; need good blockers and hand
  - AF < 1.5: villain bets rarely; CR bluff less effective

  CR SIZING:
  - Raise to 2.2x-2.8x villain's bet (standard CR size)
  - Larger CR: more fold equity but bigger risk
  - For bluffs: minimum effective CR size = 2.2x villain bet
  - Jamming: use when SPR makes it impossible to call without full commitment

  BLOCKER SCORE (0-10):
  - Holds nuts-blocker (Ace of flush suit, etc.): +4
  - Holds second-nut blocker: +2
  - Blocks nut-flush-draw that completed: +3
  - Blocks straight-completing cards: +2
  - Blocks none of villain's value combos: -2

  CHECK-RAISE PROFITABILITY SCORE (0-10):
  - Requires: villain_bet_pct, blocker_score, hero_showdown_value (low = good),
    board_helps_story, spr

DISTINCT FROM:
  check_raise_ev.py:    General check-raise EV for value and semi-bluffs
  river_line_solver.py: History-aware river action solver
  THIS MODULE:          RIVER CHECK-RAISE BLUFF specific; blocker analysis;
                        fold frequency needed; story-telling; CR-bluff hand selection.
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _breakeven_fold_pct(pot_bb: float, cr_total_bb: float) -> float:
    """Fold% villain must have for CR bluff to break even."""
    cr_raise_amount = cr_total_bb
    return round(cr_raise_amount / (pot_bb + cr_raise_amount), 3)


def _cr_size(villain_bet_bb: float, multiplier: float = 2.5) -> float:
    return round(villain_bet_bb * multiplier, 1)


def _cr_ev(
    pot_bb: float,
    villain_bet_bb: float,
    cr_total_bb: float,
    villain_fold_pct: float,
) -> float:
    fold_ev = villain_fold_pct * (pot_bb + villain_bet_bb)
    call_ev = (1.0 - villain_fold_pct) * (-cr_total_bb)
    return round(fold_ev + call_ev, 2)


def _blocker_score(blockers: list) -> int:
    score = 0
    for b in blockers:
        b = b.lower()
        if b in ('nut_flush_blocker', 'ace_flush_suit'):
            score += 4
        elif b in ('second_nut_blocker', 'king_flush_suit'):
            score += 2
        elif b in ('straight_blocker', 'nut_straight_card'):
            score += 2
        elif b in ('none', 'no_blockers'):
            score -= 2
    return max(0, min(10, score))


def _profitability_score(
    villain_bet_pct: float,
    blocker_score: int,
    hero_showdown_value: float,
    board_tells_story: bool,
    villain_fold_pct: float,
    be_fold_pct: float,
) -> float:
    score = 0.0
    fold_margin = villain_fold_pct - be_fold_pct
    score += min(4.0, fold_margin * 20.0)
    score += blocker_score * 0.30
    score += (1.0 - hero_showdown_value) * 2.0
    if board_tells_story:
        score += 1.5
    if villain_bet_pct >= 0.60:
        score += 1.0
    return round(min(10.0, max(0.0, score)), 1)


def _recommendation(profit_score: float, cr_ev: float) -> str:
    if profit_score >= 7.0 and cr_ev > 0:
        return 'CHECK_RAISE_BLUFF'
    elif profit_score >= 5.0 and cr_ev > 0:
        return 'CR_BLUFF_MARGINAL'
    elif profit_score >= 3.0:
        return 'CR_BLUFF_BORDERLINE_FOLD_BETTER'
    else:
        return 'FOLD_OR_CALL_ONLY'


@dataclass
class RiverXRBluffResult:
    hero_hand_category: str
    blockers: List[str]
    blocker_score: int
    villain_bet_pct: float
    villain_fold_pct: float

    pot_bb: float
    villain_bet_bb: float
    cr_size_bb: float
    breakeven_fold_pct: float
    cr_ev_bb: float
    profit_score: float

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_river_xr_bluff(
    hero_hand_category: str = 'air',
    hero_showdown_value: float = 0.0,
    blockers: Optional[List[str]] = None,
    villain_bet_pct: float = 0.55,
    villain_fold_pct: float = 0.45,
    villain_type: str = 'rec',
    pot_bb: float = 20.0,
    villain_bet_bb: Optional[float] = None,
    board_tells_story: bool = True,
    spr: float = 2.0,
) -> RiverXRBluffResult:
    """
    Analyze whether a river check-raise bluff is profitable.

    Args:
        hero_hand_category:   Hero's hand (e.g. 'air', 'missed_draw', 'weak_pair')
        hero_showdown_value:  0.0 = no showdown value; 1.0 = always wins at showdown
        blockers:             Blocker cards hero holds
        villain_bet_pct:      Villain's river bet frequency
        villain_fold_pct:     Villain's fold% facing a river check-raise
        villain_type:         Villain archetype
        pot_bb:               Pot size before villain's bet
        villain_bet_bb:       Villain's actual bet; if None, uses 60% of pot
        board_tells_story:    Does the board allow hero's range to credibly CR here?
        spr:                  Stack-to-pot ratio before villain's bet

    Returns:
        RiverXRBluffResult
    """
    if blockers is None:
        blockers = []
    if villain_bet_bb is None:
        villain_bet_bb = round(pot_bb * 0.60, 1)

    blk_score = _blocker_score(blockers)
    cr_bb = _cr_size(villain_bet_bb, multiplier=2.5)
    be_fold = _breakeven_fold_pct(pot_bb + villain_bet_bb, cr_bb)
    ev = _cr_ev(pot_bb, villain_bet_bb, cr_bb, villain_fold_pct)
    p_score = _profitability_score(
        villain_bet_pct, blk_score, hero_showdown_value, board_tells_story,
        villain_fold_pct, be_fold,
    )
    action = _recommendation(p_score, ev)

    verdict = (
        f'[XRB {hero_hand_category}|{villain_type}] '
        f'{action} | score={p_score:.0f}/10 EV={ev:+.1f}BB | '
        f'fold%={villain_fold_pct:.0%}(need:{be_fold:.0%})'
    )

    reasoning = (
        f'River CR bluff analysis: hero={hero_hand_category} showdown={hero_showdown_value:.0%}. '
        f'Blockers: {blockers} (score={blk_score}). '
        f'Villain: bet%={villain_bet_pct:.0%} fold%={villain_fold_pct:.0%}. '
        f'CR to {cr_bb:.1f}BB; break-even fold%={be_fold:.0%}. '
        f'EV={ev:+.1f}BB. Score={p_score:.0f}/10. Action: {action}.'
    )

    tips = []

    tips.append(
        f'CR BLUFF SIZING: Raise to {cr_bb:.1f}BB ({cr_bb/villain_bet_bb:.1f}x villain bet). '
        f'Break-even fold% = {be_fold:.0%}. '
        f'Villain folds {villain_fold_pct:.0%} -> EV={ev:+.1f}BB.'
    )

    fold_margin = villain_fold_pct - be_fold
    if fold_margin >= 0.10:
        tips.append(
            f'PROFITABLE: Villain folds {villain_fold_pct:.0%} vs need {be_fold:.0%} -> '
            f'+{fold_margin:.0%} margin. CR bluff has clear +EV edge.'
        )
    elif fold_margin >= 0:
        tips.append(
            f'MARGINAL: Fold margin only +{fold_margin:.0%}. '
            f'Need very good blockers or villain to over-fold vs your specific hand.'
        )
    else:
        tips.append(
            f'UNPROFITABLE: Villain folds {villain_fold_pct:.0%} but need {be_fold:.0%}. '
            f'CR bluff loses {-fold_margin:.0%} in expected fold frequency. '
            f'Prefer check-fold or call depending on showdown value.'
        )

    if blk_score >= 5:
        tips.append(
            f'GOOD BLOCKERS (score={blk_score}): Holding blockers to villain nuts-combos '
            f'reduces villain calling range. This is a KEY quality for CR bluffs.'
        )
    elif blk_score <= 2 and action == 'CHECK_RAISE_BLUFF':
        tips.append(
            f'WARNING: Poor blockers (score={blk_score}). '
            f'CR bluff profitable only due to fold equity; '
            f'villain may still call with wide value range.'
        )

    if hero_showdown_value > 0.15:
        tips.append(
            f'SHOWDOWN VALUE ({hero_showdown_value:.0%}): Hero has some showdown value. '
            f'Consider calling instead of bluffing; may win at showdown vs. villain bluffs. '
            f'CR bluff turns made hand into bluff -- only correct if fold%>{be_fold:.0%}.'
        )

    if villain_bet_pct >= 0.65:
        tips.append(
            f'HIGH VILLAIN BET FREQUENCY ({villain_bet_pct:.0%}): Villain bets wide. '
            f'Many of their bets are bluffs/thin; your CR fold equity is higher. '
            f'CR bluffs very effective vs. this villain.'
        )

    return RiverXRBluffResult(
        hero_hand_category=hero_hand_category,
        blockers=blockers,
        blocker_score=blk_score,
        villain_bet_pct=villain_bet_pct,
        villain_fold_pct=villain_fold_pct,
        pot_bb=pot_bb,
        villain_bet_bb=villain_bet_bb,
        cr_size_bb=cr_bb,
        breakeven_fold_pct=be_fold,
        cr_ev_bb=ev,
        profit_score=p_score,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def xrb_one_liner(r: RiverXRBluffResult) -> str:
    return (
        f'[XRB {r.hero_hand_category}] '
        f'{r.recommended_action} score={r.profit_score:.0f}/10 '
        f'EV={r.cr_ev_bb:+.1f}BB need_fold={r.breakeven_fold_pct:.0%}'
    )
