"""
Pot Commitment Calculator (pot_commitment_calculator.py)

Analyzes precisely when hero becomes pot-committed at each decision point.
Commitment is NOT just about having already invested chips (sunk-cost fallacy).
Commitment is about whether CALLING/SHOVING has better EV than FOLDING given
the remaining chips and pot.

POT COMMITMENT THEORY:
  Hero is "pot-committed" when:
  1. The pot odds justify calling any bet with remaining stack (SPR-based)
  2. OR: The cost to fold exceeds the EV of folding
  3. OR: Shoving has higher EV than folding even with marginal equity

  COMMITMENT THRESHOLDS BY HAND:
    Monster (set/flush/straight/nuts):
      Committed at SPR <= 6.0 (will call off any bet)
    Strong value (two_pair/overpair):
      Committed at SPR <= 3.5
    Top pair good kicker:
      Committed at SPR <= 2.0
    Top pair weak kicker:
      Committed at SPR <= 1.2
    Draw:
      Committed at SPR <= 1.5 (needs equity to justify)
    Air:
      Never committed (always fold unless steal opportunity)

  SPR CALCULATION:
    SPR = effective_stack / pot
    "Commitment zone": when SPR < threshold, hero should not fold

  JAM ANALYSIS:
    If hero jams vs villain's probable range:
    EV(jam) = equity * (pot + 2*stack) - stack
    If EV(jam) > EV(fold) [0], then jam is better

  CRITICAL INSIGHT:
    Pot-committed does NOT mean "always call."
    It means folding would be a MISTAKE given the pot odds.
    If you've bet 80% of your stack and villain jams, you need ~33% equity to call.

DISTINCT FROM:
  spr_planner.py:        SPR-based multi-street planning
  spr_commitment.py:     SPR commitment thresholds
  stack_off_advisor.py:  Stack-off equity thresholds
  THIS MODULE:           Precise commitment calculation; when to jam/call/fold
                         given current pot and stack; EV of folding vs calling.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Commitment SPR threshold by hand category
COMMIT_SPR_THRESHOLD = {
    'nuts':         8.0,
    'near_nuts':    7.0,
    'full_house':   6.5,
    'flush':        6.0,
    'straight':     5.5,
    'set':          5.5,
    'two_pair':     3.5,
    'overpair':     3.0,
    'top_pair':     2.0,
    'top_pair_wk':  1.2,   # top pair weak kicker
    'middle_pair':  1.0,
    'combo_draw':   2.0,   # equity-based commitment
    'flush_draw':   1.5,
    'oesd':         1.5,
    'gutshot':      0.8,
    'air':          0.0,   # never committed
}

# Minimum equity to jam given pot odds
def _min_equity_to_jam(pot_bb: float, stack_bb: float) -> float:
    """Hero equity needed so EV(jam) >= EV(fold)=0."""
    total_pot = pot_bb + 2 * stack_bb
    if total_pot <= 0:
        return 1.0
    return round(stack_bb / total_pot, 3)


def _spr(stack_bb: float, pot_bb: float) -> float:
    if pot_bb <= 0:
        return 99.0
    return round(stack_bb / pot_bb, 2)


def _is_committed(
    hand_category: str,
    stack_bb: float,
    pot_bb: float,
) -> bool:
    spr = _spr(stack_bb, pot_bb)
    threshold = COMMIT_SPR_THRESHOLD.get(hand_category, 1.5)
    return spr <= threshold


def _ev_jam(
    equity: float,
    pot_bb: float,
    stack_bb: float,
) -> float:
    """EV of jamming all-in."""
    total_pot = pot_bb + 2 * stack_bb
    return round(equity * total_pot - stack_bb, 2)


def _ev_call_check(
    equity: float,
    call_amount: float,
    pot_bb: float,
) -> float:
    """EV of calling a specific bet."""
    total = pot_bb + 2 * call_amount
    return round(equity * total - call_amount, 2)


def _commit_action(
    hand_category: str,
    stack_bb: float,
    pot_bb: float,
    equity: float,
    villain_bet_bb: float,
) -> str:
    spr = _spr(stack_bb, pot_bb)
    threshold = COMMIT_SPR_THRESHOLD.get(hand_category, 1.5)

    # If villain overbets (bet > stack), hero must call or fold
    call_amount = min(villain_bet_bb, stack_bb)
    ev_c = _ev_call_check(equity, call_amount, pot_bb)
    ev_fold = 0.0
    ev_jam = _ev_jam(equity, pot_bb, stack_bb)

    if hand_category == 'air':
        return 'fold'

    if spr <= threshold:
        if ev_jam >= ev_fold:
            return 'jam'
        return 'call'

    # Not committed: compare EVs
    if ev_c > ev_fold + 0.5:
        return 'call_not_yet_committed'
    elif ev_c > ev_fold:
        return 'marginal_call'
    else:
        return 'fold'


def _percent_committed(stack_invested: float, starting_stack: float) -> float:
    if starting_stack <= 0:
        return 1.0
    return round(min(1.0, stack_invested / starting_stack), 3)


def _commitment_description(spr: float, threshold: float) -> str:
    ratio = spr / threshold if threshold > 0 else 99
    if ratio <= 0.5:
        return 'deeply_committed'
    elif ratio <= 1.0:
        return 'committed'
    elif ratio <= 1.5:
        return 'approaching_commitment'
    else:
        return 'not_committed'


@dataclass
class CommitmentAnalysis:
    # Inputs
    hand_category: str
    stack_bb: float
    pot_bb: float
    equity: float
    villain_bet_bb: float
    street: str

    # Analysis
    spr: float
    commit_spr_threshold: float
    is_committed: bool
    commitment_state: str   # deeply_committed / committed / approaching / not_committed
    ev_jam: float
    ev_call: float
    min_equity_to_jam: float
    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_commitment(
    hand_category: str = 'top_pair',
    stack_bb: float = 40.0,
    pot_bb: float = 20.0,
    equity: float = 0.60,
    villain_bet_bb: float = 15.0,
    street: str = 'flop',
    starting_stack_bb: float = 100.0,
) -> CommitmentAnalysis:
    """
    Analyze pot commitment situation.

    Args:
        hand_category:      Hero's hand category
        stack_bb:           Remaining effective stack in BB
        pot_bb:             Current pot in BB
        equity:             Hero's estimated equity
        villain_bet_bb:     Villain's bet/jam size in BB
        street:             'flop' / 'turn' / 'river'
        starting_stack_bb:  Original stack at start of hand

    Returns:
        CommitmentAnalysis
    """
    spr = _spr(stack_bb, pot_bb)
    threshold = COMMIT_SPR_THRESHOLD.get(hand_category, 1.5)
    committed = _is_committed(hand_category, stack_bb, pot_bb)
    commit_state = _commitment_description(spr, threshold)
    ev_j = _ev_jam(equity, pot_bb, stack_bb)
    call_amount = min(villain_bet_bb, stack_bb)
    ev_c = _ev_call_check(equity, call_amount, pot_bb)
    min_eq = _min_equity_to_jam(pot_bb, stack_bb)
    action = _commit_action(hand_category, stack_bb, pot_bb, equity, villain_bet_bb)
    pct_invested = _percent_committed(starting_stack_bb - stack_bb, starting_stack_bb)

    verdict = (
        f'[COMMIT {hand_category}|{street}|{commit_state}] '
        f'{action.upper()} | spr={spr:.1f} thresh={threshold:.1f} | '
        f'ev_jam={ev_j:+.1f}BB eq={equity:.0%}'
    )

    reasoning = (
        f'Commitment analysis: {hand_category} on {street}. '
        f'Stack={stack_bb:.1f}BB, Pot={pot_bb:.1f}BB, SPR={spr:.2f}. '
        f'Commit threshold for {hand_category}: SPR<={threshold:.1f}. '
        f'{"COMMITTED: SPR below threshold." if committed else "NOT committed: SPR above threshold."} '
        f'Equity={equity:.0%}. Min equity to jam: {min_eq:.0%}. '
        f'EV(jam)={ev_j:+.1f}BB, EV(call)={ev_c:+.1f}BB. '
        f'Recommended: {action}.'
    )

    tips = []

    tips.append(
        f'SPR COMMITMENT: {hand_category} commits at SPR<={threshold:.1f}. '
        f'Current SPR={spr:.2f}. '
        f'{"COMMITTED -- do not fold." if committed else "Not committed -- fold is viable."}'
    )

    tips.append(
        f'EV ANALYSIS: jam={ev_j:+.1f}BB vs fold=0. '
        f'{"JAM IS CORRECT: EV positive." if ev_j > 0 else "JAM EV negative. Consider fold unless committed."} '
        f'Min equity to jam: {min_eq:.0%}. Current equity: {equity:.0%}.'
    )

    if committed and ev_j < 0:
        tips.append(
            f'TRAP WARNING: Committed by SPR but EV(jam)<0 ({ev_j:+.1f}BB). '
            f'Villain may have {hand_category} dominated. '
            f'Consider calling instead of jamming; at least get more information.'
        )
    elif action == 'fold' and pct_invested > 0.25:
        tips.append(
            f'SUNK COST REMINDER: Hero invested {pct_invested:.0%} of stack. '
            f'Folding is still correct if equity={equity:.0%} < {min_eq:.0%} minimum. '
            f'Do not call just because you already invested chips.'
        )

    if street == 'river':
        tips.append(
            f'RIVER: No more cards. Equity is realized or not. '
            f'{"Call or jam: you have showdown equity." if equity >= min_eq else "Fold: equity insufficient."}'
        )

    return CommitmentAnalysis(
        hand_category=hand_category,
        stack_bb=stack_bb,
        pot_bb=pot_bb,
        equity=equity,
        villain_bet_bb=villain_bet_bb,
        street=street,
        spr=spr,
        commit_spr_threshold=threshold,
        is_committed=committed,
        commitment_state=commit_state,
        ev_jam=ev_j,
        ev_call=ev_c,
        min_equity_to_jam=min_eq,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pcc_one_liner(r: CommitmentAnalysis) -> str:
    return (
        f'[PCC {r.hand_category}|{r.street}] '
        f'{r.recommended_action.upper()} | '
        f'spr={r.spr:.1f}/{r.commit_spr_threshold:.1f} '
        f'{"COMMITTED" if r.is_committed else "FREE"} | '
        f'ev_jam={r.ev_jam:+.1f}BB'
    )
