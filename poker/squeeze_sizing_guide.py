"""
Squeeze Sizing Guide (squeeze_sizing_guide.py)

Calibrates squeeze raise size based on open size, number of callers,
position, and stack depth to achieve optimal SPR and fold equity.

THEORY:
  SQUEEZE SIZING PRINCIPLES:
  Squeeze size must be large enough to price out original raiser AND callers.
  Each caller adds dead money, requiring a larger absolute size.

  BASELINE FORMULA:
  squeeze_bb = open_bb * 3.0 + n_callers * 2.5 [+ oop_bonus]

  1 CALLER: ~9-11BB (3x open + dead money)
  2 CALLERS: ~12-14BB (more dead money, more to price out)
  3 CALLERS: ~15-18BB (pot is large; still need adequate sizing)

  SPR TARGET AFTER SQUEEZE:
  Prefer SPR 2-4 in 3-bet pot (committed enough to barrel all streets;
  not so shallow that villain has no fold equity to push back).

  OOP SQUEEZE BONUS:
  Add 1.0-2.0BB when squeezing OOP; need extra fold equity to compensate.

  JAM THRESHOLD:
  If squeeze_size >= 35% of effective stack: jam instead (pot committed).

DISTINCT FROM:
  squeeze_advisor.py:          When a squeeze spot is profitable
  squeeze_play_advisor.py:     Range selection for squeezes
  squeeze_ev_optimizer.py:     EV calculation for specific squeeze
  THIS MODULE:                 HOW MUCH to squeeze; SPR targeting;
                               jam vs raise-small decision; sizing calibration.
"""

from dataclasses import dataclass, field
from typing import List

BASE_SQUEEZE_OPEN_MULTIPLIER: float = 3.0
CALLER_DEAD_MONEY_BB: float = 2.5
OOP_SQUEEZE_BONUS_BB: float = 1.5

VILLAIN_SQUEEZE_SIZE_MOD: dict = {
    'fish':            -0.5,
    'calling_station': -0.5,
    'nit':             +1.0,
    'lag':             +1.5,
    'rec':             +0.0,
    'reg':              0.0,
}

JAM_THRESHOLD_RATIO: float = 0.35
LARGE_SQUEEZE_THRESHOLD_RATIO: float = 0.20

SPR_TARGET_LOW: float = 2.0
SPR_TARGET_HIGH: float = 5.0


def _squeeze_size_bb(
    open_bb: float,
    n_callers: int,
    position: str,
    effective_stack_bb: float,
    villain_type: str,
) -> float:
    base = open_bb * BASE_SQUEEZE_OPEN_MULTIPLIER + n_callers * CALLER_DEAD_MONEY_BB
    oop_bonus = OOP_SQUEEZE_BONUS_BB if position == 'oop' else 0.0
    vil_adj = VILLAIN_SQUEEZE_SIZE_MOD.get(villain_type, 0.0)
    raw = base + oop_bonus + vil_adj
    max_size = effective_stack_bb * 0.40
    return round(min(raw, max_size), 1)


def _pot_before_squeeze(open_bb: float, n_callers: int) -> float:
    return round(open_bb + n_callers * open_bb + 1.5, 1)


def _spr_if_called(
    squeeze_bb: float,
    pot_before: float,
    effective_stack_bb: float,
) -> float:
    pot_after = pot_before + squeeze_bb * 2
    stack_after = effective_stack_bb - squeeze_bb
    if pot_after <= 0:
        return 0.0
    return round(max(0.0, stack_after / pot_after), 2)


def _squeeze_action(squeeze_bb: float, effective_stack_bb: float) -> str:
    ratio = squeeze_bb / max(effective_stack_bb, 1.0)
    if ratio >= JAM_THRESHOLD_RATIO:
        return 'JAM_PREFERRED'
    if ratio >= LARGE_SQUEEZE_THRESHOLD_RATIO:
        return 'LARGE_SQUEEZE_COMMITTED'
    return 'STANDARD_SQUEEZE'


@dataclass
class SqueezeSizingResult:
    open_bb: float
    n_callers: int
    position: str
    effective_stack_bb: float
    villain_type: str

    optimal_squeeze_bb: float
    pot_before_squeeze: float
    spr_if_called: float
    action_rec: str
    jam_threshold_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_squeeze_sizing(
    open_bb: float = 3.0,
    n_callers: int = 1,
    position: str = 'ip',
    effective_stack_bb: float = 100.0,
    villain_type: str = 'reg',
) -> SqueezeSizingResult:
    """
    Calculate optimal squeeze raise size.

    Args:
        open_bb:            Open raise size in BB (e.g., 3.0)
        n_callers:          Number of callers between raiser and hero
        position:           Hero's position vs original raiser ('ip' or 'oop')
        effective_stack_bb: Effective stack in BB
        villain_type:       Original raiser type ('fish','nit','lag','reg',etc.)

    Returns:
        SqueezeSizingResult
    """
    sq_bb = _squeeze_size_bb(open_bb, n_callers, position, effective_stack_bb, villain_type)
    pot_before = _pot_before_squeeze(open_bb, n_callers)
    spr_called = _spr_if_called(sq_bb, pot_before, effective_stack_bb)
    action = _squeeze_action(sq_bb, effective_stack_bb)
    jam_thresh = round(effective_stack_bb * JAM_THRESHOLD_RATIO, 1)

    verdict = (
        f'[SQ open={open_bb}BB|{n_callers}callers|{position}|{villain_type}] '
        f'squeeze={sq_bb}BB action={action} SPR={spr_called}'
    )

    reasoning = (
        f'Squeeze sizing vs {villain_type} open {open_bb}BB, {n_callers} caller(s): '
        f'base={open_bb}*{BASE_SQUEEZE_OPEN_MULTIPLIER:.0f}={open_bb*BASE_SQUEEZE_OPEN_MULTIPLIER:.1f}BB '
        f'+callers={n_callers}*{CALLER_DEAD_MONEY_BB:.1f}={n_callers*CALLER_DEAD_MONEY_BB:.1f}BB '
        f'+oop_bonus={OOP_SQUEEZE_BONUS_BB if position=="oop" else 0:.1f}BB '
        f'+vil_adj={VILLAIN_SQUEEZE_SIZE_MOD.get(villain_type, 0):+.1f}BB. '
        f'Optimal={sq_bb}BB. SPR if called={spr_called}. Action={action}.'
    )

    tips = []

    tips.append(
        f'Squeeze to {sq_bb}BB vs {villain_type} open {open_bb}BB ({n_callers} caller). '
        f'SPR if called={spr_called} -- '
        f'{"good SPR for 3-bet pot postflop" if SPR_TARGET_LOW <= spr_called <= SPR_TARGET_HIGH else "very low SPR; often jam or check/call flop" if spr_called < SPR_TARGET_LOW else "SPR high; may face 4-bet"}. '
        f'Action: {action}.'
    )

    if action == 'JAM_PREFERRED':
        tips.append(
            f'JAM recommended: squeeze size {sq_bb}BB >= {JAM_THRESHOLD_RATIO:.0%} of stack {effective_stack_bb:.0f}BB. '
            f'Pot-committed after squeeze; avoid non-jam squeezes that leave awkward stack. '
            f'Jam range vs {villain_type}: QQ+/AK at min; add JJ/AQs if fold equity high.'
        )
    elif action == 'LARGE_SQUEEZE_COMMITTED':
        tips.append(
            f'Large squeeze ({sq_bb}BB = {sq_bb/effective_stack_bb:.0%} of stack). '
            f'Committed postflop; will often stack off on any decent flop. '
            f'vs {villain_type}: include value hands (TT+/AQs+) and strong bluffs (A5s/76s).'
        )
    else:
        tips.append(
            f'Standard squeeze {sq_bb}BB vs {n_callers} caller(s). '
            f'OOP: add {OOP_SQUEEZE_BONUS_BB}BB bonus for fold equity. '
            f'vs {villain_type}: {"NIT folds to most 3-bets; larger size forces fold or commitment" if villain_type=="nit" else "LAG may 4-bet; be ready to 4-bet/call or fold" if villain_type=="lag" else "size achieves balanced fold equity"}.'
        )

    if n_callers >= 2:
        tips.append(
            f'{n_callers} callers: large dead money = {n_callers * CALLER_DEAD_MONEY_BB:.1f}BB extra. '
            f'Squeeze range should be tighter (callers behind have connected ranges). '
            f'Value-heavy: TT+/AK; bluffs: A5s/KQs with good blockers only.'
        )

    return SqueezeSizingResult(
        open_bb=open_bb,
        n_callers=n_callers,
        position=position,
        effective_stack_bb=effective_stack_bb,
        villain_type=villain_type,
        optimal_squeeze_bb=sq_bb,
        pot_before_squeeze=pot_before,
        spr_if_called=spr_called,
        action_rec=action,
        jam_threshold_bb=jam_thresh,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ssq_one_liner(r: SqueezeSizingResult) -> str:
    return (
        f'[SQ {r.open_bb}BB|{r.n_callers}call|{r.position}] '
        f'squeeze={r.optimal_squeeze_bb}BB SPR={r.spr_if_called} {r.action_rec}'
    )
