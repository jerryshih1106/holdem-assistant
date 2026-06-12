"""
C-bet Defense Advisor (cbet_defense_advisor.py)

Tells hero how to respond when facing a villain c-bet, based on hand
category, board texture, position, and villain's tendencies.

THEORY:
  Facing a c-bet, hero must decide: fold / call / raise.

  CALLING RANGE vs C-BETS:
  - On DRY boards: villain c-bets wide with many bluffs; call wide
  - On WET boards: villain has more value; calling range is tighter
  - IP calls more than OOP: position allows realizing equity later
  - Drawing hands: often pure calls or semi-bluff raises
  - Made hands (top pair+): call or raise depending on aggression level

  MDF (MINIMUM DEFENSE FREQUENCY):
  To prevent villain from profitably c-betting any two cards:
    MDF = 1 - bet/(pot + bet)
  For 67% pot c-bet: MDF = 1 - 0.67/1.67 = 60%
  Hero's combined (call + raise) must reach MDF threshold.

  RAISING vs CALLING:
  - Check-raise with: strong draws (combo, OESD), sets, two pair
  - Call with: top pair, flush draws, gutshots (IP)
  - Fold: underpairs, weak backdoor draws OOP

  VILLAIN TYPE ADJUSTMENTS:
  - High FCBet (>70%): villain over-folds to raises; raise more
  - Low CBet% (<40%): villain is value-heavy; tighten calling range
  - High AF: villain barrels more; floating (calling to bluff later) works better
  - Low AF: villain checks turns; float more but expect showdown

DISTINCT FROM:
  facing_aggression.py:    General aggression equity adjustment
  check_raise.py:          Check-raise decision analysis
  calldown_advisor.py:     Multi-street calldown planning
  THIS MODULE:             Specifically FACING VILLAIN C-BET; fold/call/raise
                           thresholds by villain stats; MDF enforcement.
"""

from dataclasses import dataclass, field
from typing import List


# Minimum equity to call a c-bet by position and board texture
CALL_EQUITY_THRESHOLD: dict = {
    ('ip',  'dry'):      0.30,
    ('ip',  'medium'):   0.32,
    ('ip',  'wet'):      0.35,
    ('ip',  'paired'):   0.28,
    ('ip',  'monotone'): 0.32,
    ('oop', 'dry'):      0.36,
    ('oop', 'medium'):   0.38,
    ('oop', 'wet'):      0.42,
    ('oop', 'paired'):   0.34,
    ('oop', 'monotone'): 0.40,
}

# Minimum hand rank to check-raise vs c-bet (on each texture)
RAISE_HANDS: dict = {
    'dry':      frozenset({'set', 'two_pair', 'combo_draw', 'oesd', 'nuts', 'flush', 'straight', 'full_house'}),
    'wet':      frozenset({'set', 'combo_draw', 'nuts', 'flush', 'full_house'}),
    'medium':   frozenset({'set', 'two_pair', 'combo_draw', 'oesd', 'nuts', 'flush', 'straight', 'full_house'}),
    'paired':   frozenset({'set', 'full_house', 'nuts', 'flush'}),
    'monotone': frozenset({'flush', 'nuts', 'full_house', 'set'}),
}

# Villain c-bet adjustment by FCBet%
def _villain_cbet_adj(villain_fcbet: float, hero_action: str) -> float:
    """Adjust thresholds based on villain fold to c-bet frequency."""
    if hero_action == 'raise' and villain_fcbet >= 0.65:
        return -0.05  # lower raise threshold; villain folds too much
    if hero_action == 'call' and villain_fcbet <= 0.35:
        return 0.05   # tighten call; villain is value-heavy
    return 0.0


def _mdf(bet_fraction: float) -> float:
    return round(1.0 - bet_fraction / (1.0 + bet_fraction), 3)


def _determine_action(
    hand_category: str,
    hero_equity: float,
    hero_position: str,
    board_texture: str,
    cbet_size_frac: float,
    villain_fcbet: float,
    villain_af: float,
) -> tuple:
    """Return (action, confidence) where action in fold/call/raise."""
    key = (hero_position, board_texture)
    call_threshold = CALL_EQUITY_THRESHOLD.get(key, 0.35)
    call_threshold += _villain_cbet_adj(villain_fcbet, 'call')

    raise_hands = RAISE_HANDS.get(board_texture, RAISE_HANDS['dry'])

    # Raise with strong hands
    if hand_category in raise_hands:
        if hero_position == 'oop' or hero_equity >= 0.55:
            return ('raise', 0.90)
        return ('raise', 0.75)  # IP: may also just call for deception

    # Call with adequate equity
    if hero_equity >= call_threshold:
        return ('call', 0.80)

    # Fold
    return ('fold', 0.85)


def _raise_size(villain_bet_bb: float, pot_bb: float) -> float:
    """Optimal check-raise size."""
    return round(villain_bet_bb * 2.5 + pot_bb * 0.5, 1)


@dataclass
class CbetDefenseResult:
    hand_category: str
    board_texture: str
    hero_position: str
    hero_equity: float
    villain_cbet_size: float
    villain_fcbet: float
    villain_af: float

    mdf: float
    call_threshold: float
    recommended_action: str
    confidence: float
    raise_size_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_cbet_defense(
    hand_category: str = 'top_pair',
    board_texture: str = 'dry',
    hero_position: str = 'ip',
    hero_equity: float = 0.55,
    villain_cbet_size_frac: float = 0.67,
    villain_fcbet: float = 0.50,
    villain_af: float = 2.0,
    pot_bb: float = 15.0,
) -> CbetDefenseResult:
    """
    Advise how to respond to a villain c-bet.

    Args:
        hand_category:          Hero's hand
        board_texture:          Board texture
        hero_position:          'ip' / 'oop'
        hero_equity:            Hero's equity vs villain's c-bet range
        villain_cbet_size_frac: Villain's c-bet as fraction of pot
        villain_fcbet:          Villain fold-to-c-bet %  (used for raise pressure)
        villain_af:             Villain aggression factor
        pot_bb:                 Pot before c-bet

    Returns:
        CbetDefenseResult
    """
    mdf_val = _mdf(villain_cbet_size_frac)
    villain_bet_bb = round(pot_bb * villain_cbet_size_frac, 1)
    pot_odds = round(villain_bet_bb / (pot_bb + villain_bet_bb), 3)
    call_threshold = CALL_EQUITY_THRESHOLD.get((hero_position, board_texture), 0.35)
    call_threshold += _villain_cbet_adj(villain_fcbet, 'call')

    action, conf = _determine_action(
        hand_category, hero_equity, hero_position, board_texture,
        villain_cbet_size_frac, villain_fcbet, villain_af,
    )

    raise_size = _raise_size(villain_bet_bb, pot_bb) if action == 'raise' else 0.0

    verdict = (
        f'[CBD {hand_category}|{board_texture}|{hero_position}] '
        f'{action.upper()} | eq={hero_equity:.0%} MDF={mdf_val:.0%} | '
        f'pot_odds={pot_odds:.0%}'
    )

    reasoning = (
        f'Facing {villain_cbet_size_frac:.0%}pot c-bet ({villain_bet_bb:.1f}BB into {pot_bb:.1f}BB). '
        f'Pot odds: {pot_odds:.0%}. MDF: {mdf_val:.0%}. '
        f'Call threshold: {call_threshold:.0%}. Hero equity: {hero_equity:.0%}. '
        f'Action: {action.upper()}. '
        f'Villain FCBet={villain_fcbet:.0%} AF={villain_af:.1f}.'
    )

    tips = []

    tips.append(
        f'MDF: Facing {villain_cbet_size_frac:.0%}pot bet, defend {mdf_val:.0%} of range '
        f'(call + raise). '
        f'Pot odds require {pot_odds:.0%} equity to break even on pure call.'
    )

    tips.append(
        f'DECISION: {action.upper()} with {hand_category} on {board_texture} board '
        f'{hero_position.upper()}. '
        f'Equity {hero_equity:.0%} vs call threshold {call_threshold:.0%}. '
        f'{"CHECK-RAISE to charge draws and protect range." if action == "raise" else "CALL and realize equity in position." if action == "call" else "FOLD: not enough equity to continue."}'
    )

    if villain_fcbet >= 0.65:
        tips.append(
            f'HIGH FCBet ({villain_fcbet:.0%}): Villain folds too much to raises. '
            f'Raise more frequently with semi-bluffs. '
            f'Value of raises increases significantly.'
        )
    elif villain_fcbet <= 0.35:
        tips.append(
            f'LOW FCBet ({villain_fcbet:.0%}): Villain is c-betting value-heavy. '
            f'Tighten calling range; fold marginal pairs OOP. '
            f'Raises need extra equity to compensate for villain not folding.'
        )

    if villain_af >= 3.0:
        tips.append(
            f'HIGH AF ({villain_af:.1f}): Villain will barrel multiple streets. '
            f'Float (call to bluff later) is risky. '
            f'Need real equity or plan for check-raise on good turns.'
        )

    if action == 'raise':
        tips.append(
            f'RAISE SIZE: {raise_size:.1f}BB (2.5x villain bet + 0.5x pot). '
            f'Forces villain to fold weak c-bets or over-commit with marginal hands.'
        )

    return CbetDefenseResult(
        hand_category=hand_category,
        board_texture=board_texture,
        hero_position=hero_position,
        hero_equity=hero_equity,
        villain_cbet_size=villain_bet_bb,
        villain_fcbet=villain_fcbet,
        villain_af=villain_af,
        mdf=mdf_val,
        call_threshold=call_threshold,
        recommended_action=action,
        confidence=conf,
        raise_size_bb=raise_size,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def cbd_one_liner(r: CbetDefenseResult) -> str:
    return (
        f'[CBD {r.hand_category}|{r.board_texture}|{r.hero_position}] '
        f'{r.recommended_action.upper()} | eq={r.hero_equity:.0%} '
        f'MDF={r.mdf:.0%} | conf={r.confidence:.0%}'
    )
