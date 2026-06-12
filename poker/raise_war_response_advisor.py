"""
Raise War Response Advisor (raise_war_response_advisor.py)

When facing escalating aggression (bet → raise → re-raise → 4-bet chain),
most players don't know whether they're trapped or being bluffed. This module
analyzes "raise wars" and recommends responses.

THEORY:
  RAISE WAR DEFINITION:
  A raise war occurs when multiple players keep re-raising each other:
  Open → 3-bet → 4-bet → 5-bet (shove) is the typical preflop raise war.
  Postflop: bet → raise → re-raise is a raise war on the flop/turn.

  PREFLOP RAISE WARS (4-bet+ situations):
  When you face a 4-bet, you are at the top of the escalation:
  - Villain's 4-bet range is very strong: typically QQ+/AKs vs TAG, JJ+/AK vs loose
  - At effective stacks 100BB: 4-bet or fold; calling 4-bet is usually wrong
  - Calling a 4-bet = 25-30% of stack committed without initiative
  - Either shove (for max fold equity + value) or fold

  POSTFLOP RAISE WARS:
  When villain raises your bet AND you consider re-raising (3-bet postflop):
  - Villain's raise is either: premium strong hand (set, 2-pair, nuts) OR check-raise bluff
  - Villain types matter hugely: nit never raise-bluffs; LAG often does
  - SPR determines commitment: low SPR = commit with top pair+; high SPR = only nuts

  RANGE ANALYSIS IN RAISE WARS:
  As escalation level increases, villain's range NARROWS:
  - Villain bets: 55% of hands
  - Villain raises: 25% of hands
  - Villain 3-bets postflop: 10% of hands (near-nuts or pure bluff)
  - Villain 4-bets postflop: 4% (essentially always nuts)

  POLARIZATION PRINCIPLE:
  At each raise level, villain's range becomes MORE POLARIZED:
  - 3-bet range: strong value + some bluffs
  - 4-bet range: ultra-strong value (nuts) + some A-blocker bluffs
  - Hero should have polarized re-raising range too

  KEY DECISION FRAMEWORK:
  1. What is SPR at decision point?
  2. What is villain's range given their escalation level?
  3. Does hero have enough equity to continue?
  4. Is this a spot where hero can profitably bluff?

DISTINCT FROM:
  facing_aggression.py:       Response to a single aggressive action
  facing_check_raise_response.py: Facing check-raise
  calldown_advisor.py:        Multi-street calldown planning
  THIS MODULE:                ESCALATING raise war; level analysis; polarization;
                              commitment thresholds; when to re-raise or fold.
"""

from dataclasses import dataclass, field
from typing import List


VILLAIN_RANGE_BY_LEVEL: dict = {
    1: 0.55,
    2: 0.25,
    3: 0.10,
    4: 0.04,
    5: 0.02,
}

VILLAIN_COMMITMENT_EQUITY: dict = {
    1: 0.38,
    2: 0.45,
    3: 0.55,
    4: 0.65,
    5: 0.75,
}

RERAISE_EQUITY_NEEDED: dict = {
    'low_spr':    0.45,
    'medium_spr': 0.55,
    'high_spr':   0.65,
}

VILLAIN_BLUFF_PCT_BY_LEVEL: dict = {
    'lag': {1: 0.40, 2: 0.30, 3: 0.20, 4: 0.10},
    'reg': {1: 0.35, 2: 0.20, 3: 0.10, 4: 0.05},
    'rec': {1: 0.25, 2: 0.12, 3: 0.05, 4: 0.02},
    'nit': {1: 0.15, 2: 0.05, 3: 0.01, 4: 0.00},
    'fish':{1: 0.30, 2: 0.20, 3: 0.12, 4: 0.05},
}


def _spr_zone(spr: float) -> str:
    if spr < 3:
        return 'low_spr'
    elif spr < 8:
        return 'medium_spr'
    return 'high_spr'


def _villain_range_pct(escalation_level: int) -> float:
    return VILLAIN_RANGE_BY_LEVEL.get(min(escalation_level, 5), 0.02)


def _villain_bluff_pct(villain_type: str, escalation_level: int) -> float:
    bluff_table = VILLAIN_BLUFF_PCT_BY_LEVEL.get(villain_type, VILLAIN_BLUFF_PCT_BY_LEVEL['reg'])
    return bluff_table.get(min(escalation_level, 4), 0.02)


def _hero_equity_vs_level(
    hero_hand_pct: float,
    villain_range_pct: float,
) -> float:
    raw_eq = hero_hand_pct * (villain_range_pct / 0.50) ** 0.5
    return round(max(0.05, min(0.95, raw_eq)), 3)


def _raise_war_action(
    hero_equity: float,
    spr_zone: str,
    escalation_level: int,
    villain_bluff_pct: float,
    hero_hand_pct: float,
) -> str:
    reraise_eq = RERAISE_EQUITY_NEEDED.get(spr_zone, 0.55)
    commit_eq  = VILLAIN_COMMITMENT_EQUITY.get(min(escalation_level, 5), 0.65)

    if spr_zone == 'low_spr' and hero_equity >= 0.42:
        return 'SHOVE_COMMIT'
    if hero_equity >= reraise_eq:
        return 'RERAISE_VALUE'
    if villain_bluff_pct >= 0.20 and hero_hand_pct >= 0.40:
        return 'CALL_BLUFF_CATCH'
    if escalation_level >= 3 and hero_equity < commit_eq:
        return 'FOLD_RANGE_TOO_STRONG'
    if hero_equity >= 0.40:
        return 'CALL_MARGINAL'
    return 'FOLD'


@dataclass
class RaiseWarResult:
    escalation_level: int
    villain_type: str
    spr: float

    villain_range_pct: float
    villain_bluff_pct: float
    hero_equity: float

    reraise_threshold: float
    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_raise_war_response(
    escalation_level: int = 2,
    villain_type: str = 'reg',
    hero_hand_pct: float = 0.55,
    spr: float = 5.0,
    pot_bb: float = 30.0,
    raise_size_bb: float = 15.0,
) -> RaiseWarResult:
    """
    Analyze how to respond in a raise war (escalating aggression).

    Args:
        escalation_level: How many raises have been made (1=first raise, 2=re-raise, etc.)
        villain_type:     'fish','rec','nit','lag','reg'
        hero_hand_pct:    Hero's hand percentile (0-1)
        spr:              Stack-to-pot ratio at decision point
        pot_bb:           Current pot in BB
        raise_size_bb:    Villain's last raise/bet size in BB

    Returns:
        RaiseWarResult
    """
    vrange = _villain_range_pct(escalation_level)
    vbluff = _villain_bluff_pct(villain_type, escalation_level)
    hero_eq = _hero_equity_vs_level(hero_hand_pct, vrange)
    spr_z = _spr_zone(spr)
    reraise_thresh = RERAISE_EQUITY_NEEDED.get(spr_z, 0.55)
    action = _raise_war_action(hero_eq, spr_z, escalation_level, vbluff, hero_hand_pct)

    verdict = (
        f'[RWR level={escalation_level}|{villain_type}|spr={spr:.1f}] '
        f'{action} eq={hero_eq:.0%} vrange={vrange:.0%} bluff={vbluff:.0%}'
    )

    reasoning = (
        f'Raise war: level {escalation_level} vs {villain_type}. '
        f'Villain range narrows to {vrange:.0%}; bluff pct={vbluff:.0%}. '
        f'Hero equity={hero_eq:.0%}; reraise threshold={reraise_thresh:.0%}. '
        f'SPR={spr:.1f} ({spr_z}). Action: {action}.'
    )

    tips = []

    tips.append(
        f'RAISE WAR LEVEL {escalation_level}: Villain range = {vrange:.0%} of hands. '
        f'Bluff pct ({villain_type}) = {vbluff:.0%}. '
        f'Your equity vs this range = {hero_eq:.0%}. '
        f'Threshold to re-raise: {reraise_thresh:.0%}.'
    )

    tips.append(
        f'RECOMMENDED: {action}. '
        f'{"Commit -- low SPR makes folding too expensive." if "SHOVE" in action else "Strong enough to re-raise for value." if "RERAISE" in action else "Catching a bluff -- call and see river." if "CATCH" in action else "Villain range too strong at this level -- fold marginal hands." if "FOLD_RANGE" in action else "Marginal call -- villain may be bluffing." if "MARGINAL" in action else "Fold -- insufficient equity vs narrow range."}'
    )

    if escalation_level >= 3:
        tips.append(
            f'HIGH ESCALATION (level {escalation_level}): Villain range is extremely narrow ({vrange:.0%}). '
            f'Only {vbluff:.0%} of their range is bluffs (vs {villain_type}). '
            f'{"Need near-nuts to continue." if vbluff < 0.10 else "Some bluff-catching possible with strong holdings."}'
        )

    if villain_type in ('nit',) and escalation_level >= 2:
        tips.append(
            f'NIT ESCALATING: Nits rarely bluff raise wars. '
            f'At level {escalation_level}, nit bluffs only {vbluff:.0%} of time. '
            f'Treat this as near-always-value; fold unless holding top of range.'
        )

    return RaiseWarResult(
        escalation_level=escalation_level,
        villain_type=villain_type,
        spr=spr,
        villain_range_pct=vrange,
        villain_bluff_pct=vbluff,
        hero_equity=hero_eq,
        reraise_threshold=reraise_thresh,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rwr_one_liner(r: RaiseWarResult) -> str:
    return (
        f'[RWR level={r.escalation_level}|{r.villain_type}] '
        f'{r.recommended_action} eq={r.hero_equity:.0%} '
        f'vrange={r.villain_range_pct:.0%} bluff={r.villain_bluff_pct:.0%}'
    )
