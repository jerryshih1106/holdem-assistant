"""
Bluff Giving Up Guide (bluff_giving_up_guide.py)

When to ABANDON a multi-street bluff (check/fold instead of continuing to barrel).
Distinct from planning a bluff -- this is the in-session decision: after c-betting
the flop, should you continue on the turn? After two barrels, fire the third?

THEORY:
  THE GIVE-UP DECISION:
  After betting one or more streets as a bluff, hero must decide each street:
  - CONTINUE: Fire another barrel (higher risk, higher reward)
  - GIVE UP: Check/fold (save chips; concede the pot)

  WHEN TO CONTINUE:
  1. Runout favored hero's perceived range (connected hero story)
  2. Villain's calling frequency is low enough (nit/tight player)
  3. Hero still has backup equity (draw, overcards, live pair)
  4. Stack-to-pot ratio gives enough leverage (future streets threaten)

  WHEN TO GIVE UP:
  1. Villain's range connected strongly with runout (flush/straight completed)
  2. Villain showed strength (called two streets; range is strong)
  3. No backup equity remaining
  4. Villain is a calling station -- fold equity is near 0
  5. Stack is mostly committed -- giving up saves very little

  ADJUSTED CONTINUE FREQUENCY:
  base_freq = CONTINUE_FREQ_BY_STREET[n_streets_bet]
  adjustments: runout, villain_type, backup_equity, pot_commitment
  If adjusted_freq >= 0.50: continue barreling
  If adjusted_freq < 0.50: give up (check/fold)

  BACKING INTO SHOWDOWN VALUE:
  Sometimes the right play after giving up the bluff is to CHECK-CALL
  if hero has enough showdown value (SDV > 30%) -- don't auto-fold.

DISTINCT FROM:
  multi_street_bluff_planner.py:  Planning the bluff pre-flop/pre-turn
  triple_barrel.py:               Triple barrel analysis
  bluff_selection_advisor.py:     Which hands to bluff with
  THIS MODULE:                    IN-SESSION GIVE-UP DECISION specifically;
                                  runout evaluation; continue vs fold threshold.
"""

from dataclasses import dataclass, field
from typing import List


VILLAIN_CALL_FREQ: dict = {
    'fish':            0.78,
    'calling_station': 0.90,
    'rec':             0.62,
    'nit':             0.28,
    'lag':             0.52,
    'reg':             0.44,
}

RUNOUT_CONTINUE_ADJUSTMENT: dict = {
    'great_for_hero':   +0.20,
    'good_for_hero':    +0.12,
    'neutral':           0.00,
    'bad_for_hero':     -0.18,
    'very_bad_for_hero': -0.32,
}

BACKUP_EQUITY_BONUS: dict = {
    'combo_draw':     +0.18,
    'flush_draw':     +0.12,
    'oesd':           +0.10,
    'overcards':      +0.06,
    'gutshot':        +0.04,
    'backdoor_flush': +0.03,
    'none':            0.00,
}

BASE_CONTINUE_FREQ: dict = {
    1: 0.55,
    2: 0.42,
    3: 0.30,
}

GIVE_UP_THRESHOLD: float = 0.50

STREET_LABELS: dict = {
    1: 'flop->turn',
    2: 'turn->river',
    3: 'river (final)',
}


def _adjusted_continue_freq(
    n_streets_bet: int,
    villain_type: str,
    runout_type: str,
    backup_equity_type: str,
    pot_committed_pct: float,
) -> float:
    base = BASE_CONTINUE_FREQ.get(n_streets_bet, 0.30)
    villain_fold = 1.0 - VILLAIN_CALL_FREQ.get(villain_type, 0.44)
    fold_adj = (villain_fold - 0.56) * 0.5
    runout_adj = RUNOUT_CONTINUE_ADJUSTMENT.get(runout_type, 0.00)
    equity_bonus = BACKUP_EQUITY_BONUS.get(backup_equity_type, 0.00)
    commit_adj = min(0.10, pot_committed_pct * 0.15)
    result = base + fold_adj + runout_adj + equity_bonus + commit_adj
    return round(min(0.90, max(0.05, result)), 3)


def _give_up_decision(
    continue_freq: float,
    backup_equity_type: str,
    sdv: float,
) -> str:
    if continue_freq >= GIVE_UP_THRESHOLD + 0.15:
        return 'CONTINUE_BARREL_STRONG'
    if continue_freq >= GIVE_UP_THRESHOLD:
        return 'CONTINUE_BARREL_MARGINAL'
    if sdv >= 0.35 and backup_equity_type != 'none':
        return 'GIVE_UP_CHECK_CALL_SDV'
    return 'GIVE_UP_CHECK_FOLD'


@dataclass
class BluffGiveUpResult:
    n_streets_bet: int
    villain_type: str
    runout_type: str
    backup_equity_type: str
    pot_committed_pct: float

    continue_freq: float
    threshold: float
    decision: str
    sdv: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_bluff_giving_up(
    n_streets_bet: int = 1,
    villain_type: str = 'reg',
    runout_type: str = 'neutral',
    backup_equity_type: str = 'none',
    pot_committed_pct: float = 0.20,
    sdv: float = 0.10,
) -> BluffGiveUpResult:
    """
    Decide whether to continue barreling or give up the bluff.

    Args:
        n_streets_bet:       How many streets have been bet already (1=flop, 2=turn, 3=river)
        villain_type:        Villain type ('fish','rec','nit','lag','reg')
        runout_type:         How the new card affects hero's perceived range
                             ('great_for_hero','good_for_hero','neutral','bad_for_hero','very_bad_for_hero')
        backup_equity_type:  Backup equity if called ('flush_draw','oesd','overcards','none',...)
        pot_committed_pct:   Fraction of stack already committed (0-1)
        sdv:                 Showdown value of hero's hand (0-1)

    Returns:
        BluffGiveUpResult
    """
    freq = _adjusted_continue_freq(
        n_streets_bet, villain_type, runout_type, backup_equity_type, pot_committed_pct
    )
    decision = _give_up_decision(freq, backup_equity_type, sdv)
    villain_call = VILLAIN_CALL_FREQ.get(villain_type, 0.44)
    label = STREET_LABELS.get(n_streets_bet, 'unknown')

    verdict = (
        f'[BGU {label}|{villain_type}|{runout_type}] '
        f'continue_freq={freq:.0%} decision={decision}'
    )

    reasoning = (
        f'Bluff give-up: after {n_streets_bet} street(s) bet ({label}). '
        f'Villain={villain_type} (call freq={villain_call:.0%}). '
        f'Runout={runout_type}. Backup equity={backup_equity_type}. '
        f'Stack committed={pot_committed_pct:.0%}. '
        f'Adjusted continue freq={freq:.0%} (threshold={GIVE_UP_THRESHOLD:.0%}). '
        f'Decision: {decision}.'
    )

    tips = []

    tips.append(
        f'GIVE-UP DECISION ({label}): continue_freq={freq:.0%} vs threshold={GIVE_UP_THRESHOLD:.0%}. '
        f'Decision: {decision}. '
        f'{"Strong continue signal -- runout favors your range AND villain folds enough." if decision == "CONTINUE_BARREL_STRONG" else "Marginal continue -- bet only with best bluff candidates." if decision == "CONTINUE_BARREL_MARGINAL" else "Give up; keep SDV hands as bluff catchers." if "SDV" in decision else "Give up -- check/fold; pot is lost."}'
    )

    tips.append(
        f'VILLAIN FACTOR: {villain_type} calls {villain_call:.0%} of the time. '
        f'Fold equity={1-villain_call:.0%}. '
        f'{"Low fold equity -- giving up saves chips vs calling station." if villain_call >= 0.70 else "Good fold equity -- worth continuing with correct runout." if villain_call <= 0.40 else "Moderate fold equity -- runout and backup equity determine continuation."}'
    )

    if runout_type in ('bad_for_hero', 'very_bad_for_hero'):
        tips.append(
            f'RUNOUT WARNING ({runout_type}): Board connected with villain calling range. '
            f'Penalty={RUNOUT_CONTINUE_ADJUSTMENT[runout_type]:+.0%} to continue frequency. '
            f'Give up unless you have strong backup equity. '
            f'Villain called previous street(s) -- their range is strong; runout helps them.'
        )
    elif runout_type in ('good_for_hero', 'great_for_hero'):
        tips.append(
            f'RUNOUT BONUS ({runout_type}): Card improves hero perceived range (Ace, King, or scare card). '
            f'Bonus={RUNOUT_CONTINUE_ADJUSTMENT[runout_type]:+.0%} to continue frequency. '
            f'This is a good spot to continue barrel -- villain expected to fold more.'
        )

    if backup_equity_type != 'none':
        bonus = BACKUP_EQUITY_BONUS.get(backup_equity_type, 0.00)
        tips.append(
            f'BACKUP EQUITY ({backup_equity_type}): +{bonus:.0%} to continue frequency. '
            f'Even if villain calls, you have {backup_equity_type} as backup. '
            f'Semi-bluff: gives two ways to win (fold equity + draw equity).'
        )

    return BluffGiveUpResult(
        n_streets_bet=n_streets_bet,
        villain_type=villain_type,
        runout_type=runout_type,
        backup_equity_type=backup_equity_type,
        pot_committed_pct=pot_committed_pct,
        continue_freq=freq,
        threshold=GIVE_UP_THRESHOLD,
        decision=decision,
        sdv=sdv,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bgu_one_liner(r: BluffGiveUpResult) -> str:
    return (
        f'[BGU n={r.n_streets_bet}|{r.villain_type}|{r.runout_type}] '
        f'freq={r.continue_freq:.0%} decision={r.decision}'
    )
