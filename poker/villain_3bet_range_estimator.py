"""
Villain 3-Bet Range Estimator (villain_3bet_range_estimator.py)

When villain 3-bets, the optimal response depends critically on what range
they are 3-betting with. A villain who 3-bets 4% has a very different range
than one who 3-bets 15% — and hero's hand equity vs those ranges differs
drastically.

3-BET RANGE CONSTRUCTION MODEL:
  3bet_pct <= 5%:  Mostly value (AA/KK/QQ/AK). Very tight.
  3bet_pct 5-8%:   Value + premium semi-bluffs (JJ, TT, AQs, AJs, KQs)
  3bet_pct 8-12%:  Balanced (adds A5s-A2s as bluffs, 99, AQo, KQo)
  3bet_pct 12-18%: Wide/aggressive (adds more Ax suited, Kxs, broadways)
  3bet_pct 18%+:   Very wide, many bluffs (56s, 67s, suited connectors)

POSITION ADJUSTMENT:
  IP 3-bet (CO/BTN vs UTG/HJ) tends to be value-heavy (can flat in position)
  OOP 3-bet (BB vs BTN) tends to be wider (can't profitably flat many hands)
  3-bet from SB tends to be polar (value + bluffs, few calls OOP)

KEY OUTPUT:
  - Estimated hand combinations in villain's 3-bet range
  - Hero's equity vs that range
  - Optimal response: 4-bet value / 4-bet bluff / call / fold
  - Breakeven equity for calling
  - 4-bet EV vs fold EV

Usage:
    from poker.villain_3bet_range_estimator import estimate_3bet_range, ThreeBetRangeResult, tbre_one_liner

    result = estimate_3bet_range(
        villain_3bet_pct=0.09,
        villain_position='BB',
        hero_position='BTN',
        hero_hand_rank_pct=0.75,  # e.g., JJ = ~75th percentile
        hero_open_bb=2.5,
        villain_3bet_size_bb=8.5,
        effective_stack_bb=100.0,
    )
    print(tbre_one_liner(result))
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# --------------------------------------------------------------------------
# Range model: (3bet_pct) -> range breakdown
# --------------------------------------------------------------------------

# Approximate combos in range (out of 1326 total preflop combos)
# Value tier combos: AA=6, KK=6, QQ=6, JJ=6, AKs=4, AKo=12
_VALUE_CORE = 40   # AA(6)+KK(6)+QQ(6)+JJ(6)+AKs(4)+AKo(12) = 40 combos
_VALUE_MED = 60    # adds TT(6)+99(6)+AQs(4)+AQo(12)+KQs(4)+AJs(4)+ATs(4)+KQo(12) = ~60 more
_SEMIBLUFF = 30    # A5s-A2s (16) + KJs + QJs + JTs + T9s = ~30
_BLUFF_MED = 50    # more suited connectors, Kxs, broadway combos
_BLUFF_WIDE = 80   # wide suited connectors, small pairs, Axo combos

def _estimate_range_combos(threeb_pct: float, villain_pos: str, hero_pos: str) -> Dict:
    """Estimate villain's 3-bet range breakdown by hand category."""
    # Base estimates
    value_combos = _VALUE_CORE
    semibluff_combos = 0
    bluff_combos = 0
    total_combos = 0

    if threeb_pct <= 0.04:
        value_combos = int(_VALUE_CORE * 0.75)   # only top of value (AA/KK/AKs)
        total_combos = value_combos
    elif threeb_pct <= 0.06:
        value_combos = _VALUE_CORE
        semibluff_combos = 5
        total_combos = value_combos + semibluff_combos
    elif threeb_pct <= 0.08:
        value_combos = _VALUE_CORE + 20     # adds QQ+/TT/AQs
        semibluff_combos = 10
        total_combos = value_combos + semibluff_combos
    elif threeb_pct <= 0.10:
        value_combos = _VALUE_CORE + _VALUE_MED // 2
        semibluff_combos = _SEMIBLUFF // 2
        bluff_combos = 5
        total_combos = value_combos + semibluff_combos + bluff_combos
    elif threeb_pct <= 0.13:
        value_combos = _VALUE_CORE + _VALUE_MED // 2
        semibluff_combos = _SEMIBLUFF
        bluff_combos = 15
        total_combos = value_combos + semibluff_combos + bluff_combos
    elif threeb_pct <= 0.17:
        value_combos = _VALUE_CORE + _VALUE_MED
        semibluff_combos = _SEMIBLUFF
        bluff_combos = _BLUFF_MED // 2
        total_combos = value_combos + semibluff_combos + bluff_combos
    else:
        value_combos = _VALUE_CORE + _VALUE_MED
        semibluff_combos = _SEMIBLUFF
        bluff_combos = _BLUFF_MED + _BLUFF_WIDE // 2
        total_combos = value_combos + semibluff_combos + bluff_combos

    # OOP adjustment: wider 3-bet ranges OOP (BB, SB)
    oop_positions = ('BB', 'SB')
    if villain_pos in oop_positions:
        semibluff_combos = int(semibluff_combos * 1.30)
        bluff_combos = int(bluff_combos * 1.40)
        total_combos = value_combos + semibluff_combos + bluff_combos

    value_pct = value_combos / max(total_combos, 1)
    bluff_pct = (semibluff_combos + bluff_combos) / max(total_combos, 1)

    return {
        'value_combos': value_combos,
        'semibluff_combos': semibluff_combos,
        'bluff_combos': bluff_combos,
        'total_combos': total_combos,
        'value_pct': round(value_pct, 3),
        'bluff_pct': round(bluff_pct, 3),
    }


def _hero_equity_vs_range(
    hero_rank_pct: float,
    value_pct: float,
    threeb_pct: float,
) -> float:
    """
    Estimate hero's equity vs villain's 3-bet range.
    hero_rank_pct: percentile strength of hero's hand (0=worst, 1=best)
    """
    # Against pure value range (AA/KK): hero equity is very low
    # Against bluff range: hero equity is ~50%
    # Weighted by value_pct
    eq_vs_value = 0.28 + hero_rank_pct * 0.30     # ranges from 0.28 (worst) to 0.58 (best)
    eq_vs_bluffs = 0.45 + hero_rank_pct * 0.20    # ranges from 0.45 to 0.65

    # High rank_pct = premium hand -> equity vs value is better
    if hero_rank_pct >= 0.95:   # AA/KK
        eq_vs_value = 0.65
        eq_vs_bluffs = 0.80
    elif hero_rank_pct >= 0.90:  # QQ/AK
        eq_vs_value = 0.50
        eq_vs_bluffs = 0.72
    elif hero_rank_pct >= 0.85:  # JJ/TT
        eq_vs_value = 0.42
        eq_vs_bluffs = 0.68
    elif hero_rank_pct >= 0.75:  # 99/AQs
        eq_vs_value = 0.35
        eq_vs_bluffs = 0.60

    bluff_pct = 1.0 - value_pct
    eq = value_pct * eq_vs_value + bluff_pct * eq_vs_bluffs
    return round(min(0.85, max(0.15, eq)), 3)


def _breakeven_equity_call(
    hero_open_bb: float,
    villain_3bet_bb: float,
    eff_stack: float,
) -> float:
    """Minimum equity needed to call the 3-bet."""
    call_cost = villain_3bet_bb - hero_open_bb
    pot_total = villain_3bet_bb + hero_open_bb   # approximate pot hero goes into
    return round(call_cost / (pot_total + call_cost), 3)


def _fourbet_size(hero_open_bb: float, villain_3bet_bb: float, ip: bool) -> float:
    mult = 2.2 if ip else 2.5
    return round(villain_3bet_bb * mult, 1)


def _fourbet_ev(
    pot_before: float,
    fourbet_bb: float,
    fold_to_4b_pct: float,
    hero_equity: float,
) -> float:
    """EV of 4-betting."""
    ev_fold = fold_to_4b_pct * pot_before
    total_pot_if_called = pot_before + fourbet_bb * 2
    ev_call = (1.0 - fold_to_4b_pct) * (hero_equity * total_pot_if_called - fourbet_bb)
    return round(ev_fold + ev_call, 2)


def _call_ev(
    pot_before: float,
    call_cost: float,
    hero_equity: float,
    fold_to_cbet: float = 0.40,
) -> float:
    """EV of calling the 3-bet (simplified)."""
    total_pot = pot_before + call_cost
    ev_postflop = hero_equity * total_pot * 0.80 - call_cost  # 0.80 = equity realization OOP
    return round(ev_postflop, 2)


# --------------------------------------------------------------------------
# Response recommendation
# --------------------------------------------------------------------------

_RESPONSE_THRESHOLDS = {
    # (hero_rank_pct, value_pct) -> action
    'fourbet_value': 0.88,   # premium hands: 4-bet for value
    'fourbet_bluff': 0.60,   # A5s / blockers: 4-bet bluff if fold eq sufficient
    'call_ip':       0.45,   # in position: call with medium hands
    'call_oop':      0.55,   # out of position: need stronger hand to call
}


def _recommend_action(
    hero_rank_pct: float,
    hero_equity: float,
    be_equity: float,
    value_pct: float,
    threeb_pct: float,
    ip: bool,
    fold_to_4b: float,
    fourbet_ev: float,
    call_ev: float,
) -> Tuple[str, str]:
    """Returns (action, reasoning)."""
    # Premium value hands
    if hero_rank_pct >= 0.88:
        return ('fourbet_value', f'Premium hand (top {(1-hero_rank_pct):.0%}): 4-bet for value vs any range.')

    # Check if calling has positive EV
    can_call = hero_equity >= be_equity + 0.02

    # Bluff 4-bet conditions: A-blocker hands, sufficient fold equity
    is_blocker = 0.50 <= hero_rank_pct <= 0.68
    fold_eq_ok = fold_to_4b >= 0.50
    if is_blocker and fold_eq_ok and value_pct >= 0.60 and threeb_pct <= 0.10:
        return ('fourbet_bluff', f'Blocker hand with {fold_to_4b:.0%} fold equity: 4-bet bluff with Axs/KQs.')

    if hero_equity >= be_equity + 0.05:
        pos = 'IP' if ip else 'OOP'
        return ('call', f'Equity ({hero_equity:.0%}) exceeds breakeven ({be_equity:.0%}) {pos}: call.')

    if hero_equity < be_equity - 0.03:
        return ('fold', f'Equity ({hero_equity:.0%}) < breakeven ({be_equity:.0%}): fold.')

    return ('fold_marginal', f'Marginal: equity ({hero_equity:.0%}) close to breakeven ({be_equity:.0%}). Lean fold OOP.')


@dataclass
class ThreeBetRangeResult:
    # Inputs
    villain_3bet_pct: float
    villain_position: str
    hero_position: str
    hero_hand_rank_pct: float
    hero_open_bb: float
    villain_3bet_size_bb: float
    effective_stack_bb: float

    # Range estimate
    value_combos: int
    semibluff_combos: int
    bluff_combos: int
    total_combos: int
    value_pct: float        # fraction of range that is value
    bluff_pct: float        # fraction of range that is bluffs
    range_type: str         # 'value_heavy', 'balanced', 'bluff_heavy'

    # Hero equity
    hero_equity_vs_range: float
    breakeven_equity: float
    equity_margin: float    # positive = hero has edge, negative = fold

    # EV
    fourbet_size_bb: float
    fourbet_ev: float
    call_ev: float
    fold_to_4b_estimate: float

    # Recommendation
    recommended_action: str   # 'fourbet_value', 'fourbet_bluff', 'call', 'fold', 'fold_marginal'
    action_reasoning: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def estimate_3bet_range(
    villain_3bet_pct: float = 0.09,
    villain_position: str = 'BB',
    hero_position: str = 'BTN',
    hero_hand_rank_pct: float = 0.75,
    hero_open_bb: float = 2.5,
    villain_3bet_size_bb: float = 8.5,
    effective_stack_bb: float = 100.0,
    villain_fold_to_4b: float = 0.55,
) -> ThreeBetRangeResult:
    """
    Estimate villain's 3-bet range and compute hero's optimal response.

    Args:
        villain_3bet_pct:      Villain's 3-bet % (0.0-1.0)
        villain_position:      Villain's position ('BB', 'SB', 'CO', 'BTN', 'HJ', 'UTG')
        hero_position:         Hero's position
        hero_hand_rank_pct:    Hero's hand percentile (0=worst, 1=best hand)
                               Examples: AA=0.99, KK=0.98, QQ=0.96, JJ=0.93,
                                         TT=0.89, AKs=0.97, AKo=0.92, AQs=0.87,
                                         99=0.83, AJs=0.80, KQs=0.77, AQo=0.74,
                                         TT=0.89, 76s=0.55, A5s=0.62, 72o=0.01
        hero_open_bb:          Hero's open raise size in BB
        villain_3bet_size_bb:  Villain's 3-bet size in BB
        effective_stack_bb:    Effective stack depth in BB
        villain_fold_to_4b:    Villain's estimated fold to 4-bet frequency

    Returns:
        ThreeBetRangeResult
    """
    rng = _estimate_range_combos(villain_3bet_pct, villain_position, hero_position)

    value_pct = rng['value_pct']
    bluff_pct = rng['bluff_pct']

    if value_pct >= 0.75:
        range_type = 'value_heavy'
    elif value_pct >= 0.55:
        range_type = 'balanced'
    else:
        range_type = 'bluff_heavy'

    hero_eq = _hero_equity_vs_range(hero_hand_rank_pct, value_pct, villain_3bet_pct)

    call_cost = villain_3bet_size_bb - hero_open_bb
    pot_before = villain_3bet_size_bb + hero_open_bb
    be_eq = _breakeven_equity_call(hero_open_bb, villain_3bet_size_bb, effective_stack_bb)
    eq_margin = round(hero_eq - be_eq, 3)

    ip = hero_position in ('BTN', 'CO', 'HJ', 'UTG')   # simplified: hero IP if villain is BB/SB
    if villain_position in ('BB', 'SB'):
        ip = True   # hero opened from position, villain 3-bets OOP
    else:
        ip = False  # villain 3-bets from position on hero

    fourbet_bb = _fourbet_size(hero_open_bb, villain_3bet_size_bb, ip)
    pot_before_4b = hero_open_bb + villain_3bet_size_bb
    fb_ev = _fourbet_ev(pot_before_4b, fourbet_bb, villain_fold_to_4b, hero_eq)
    c_ev = _call_ev(pot_before, call_cost, hero_eq)

    action, act_reason = _recommend_action(
        hero_rank_pct=hero_hand_rank_pct,
        hero_equity=hero_eq,
        be_equity=be_eq,
        value_pct=value_pct,
        threeb_pct=villain_3bet_pct,
        ip=ip,
        fold_to_4b=villain_fold_to_4b,
        fourbet_ev=fb_ev,
        call_ev=c_ev,
    )

    reasoning = (
        f'Villain {villain_position} 3-bets {villain_3bet_pct:.0%}: '
        f'range={range_type} ({rng["total_combos"]} combos, {value_pct:.0%} value). '
        f'Hero equity={hero_eq:.0%} vs breakeven={be_eq:.0%} (margin={eq_margin:+.1%}). '
        f'4-bet_ev={fb_ev:+.2f}BB call_ev={c_ev:+.2f}BB. '
        f'Action: {action}.'
    )

    verdict = (
        f'[3BET {villain_position}@{villain_3bet_pct:.0%}|{range_type}] '
        f'{action.upper()} | '
        f'eq={hero_eq:.0%} be={be_eq:.0%} margin={eq_margin:+.1%} | '
        f'4b_ev={fb_ev:+.2f}BB call_ev={c_ev:+.2f}BB'
    )

    tips = []

    if range_type == 'value_heavy':
        tips.append(
            f'VALUE-HEAVY RANGE: Villain 3-bets {villain_3bet_pct:.0%} from {villain_position}. '
            f'{value_pct:.0%} value combos. Only continue with hands that can 4-bet for value '
            f'(>={hero_hand_rank_pct:.0%}th pct need AA/KK/QQ or fold most hands).'
        )
    elif range_type == 'bluff_heavy':
        tips.append(
            f'BLUFF-HEAVY RANGE: Villain has {bluff_pct:.0%} bluffs. '
            f'Calling and 4-bet bluffing are both more profitable. '
            f'Widen your calling range; villain over-folds to 4-bets ({villain_fold_to_4b:.0%}).'
        )
    else:
        tips.append(
            f'BALANCED RANGE: {value_pct:.0%} value / {bluff_pct:.0%} bluffs. '
            f'Use standard 4-bet/call/fold frequencies.'
        )

    if action == 'fourbet_value':
        tips.append(
            f'4-BET FOR VALUE: EV={fb_ev:+.2f}BB. '
            f'Size: {fourbet_bb:.1f}BB. '
            f'If villain 5-bets, you are committed ({effective_stack_bb:.0f}BB stack).'
        )
    elif action == 'fourbet_bluff':
        tips.append(
            f'4-BET BLUFF: Fold equity={villain_fold_to_4b:.0%}, EV={fb_ev:+.2f}BB. '
            f'Use A5s/A4s/KQs (blockers to villain value range). '
            f'Size: {fourbet_bb:.1f}BB. Be prepared to fold to a 5-bet.'
        )
    elif action == 'call':
        tips.append(
            f'CALL: Equity={hero_eq:.0%} > breakeven={be_eq:.0%}. '
            f'EV={c_ev:+.2f}BB. {"IP gives you playability advantage." if ip else "OOP — pot control postflop."}'
        )
    elif action in ('fold', 'fold_marginal'):
        tips.append(
            f'FOLD: Equity ({hero_eq:.0%}) does not meet breakeven ({be_eq:.0%}). '
            f'vs {range_type} {villain_3bet_pct:.0%} 3-bet range, this hand does not have '
            f'sufficient equity to continue.'
        )

    return ThreeBetRangeResult(
        villain_3bet_pct=round(villain_3bet_pct, 3),
        villain_position=villain_position,
        hero_position=hero_position,
        hero_hand_rank_pct=round(hero_hand_rank_pct, 3),
        hero_open_bb=round(hero_open_bb, 1),
        villain_3bet_size_bb=round(villain_3bet_size_bb, 1),
        effective_stack_bb=round(effective_stack_bb, 1),
        value_combos=rng['value_combos'],
        semibluff_combos=rng['semibluff_combos'],
        bluff_combos=rng['bluff_combos'],
        total_combos=rng['total_combos'],
        value_pct=value_pct,
        bluff_pct=bluff_pct,
        range_type=range_type,
        hero_equity_vs_range=hero_eq,
        breakeven_equity=be_eq,
        equity_margin=eq_margin,
        fourbet_size_bb=fourbet_bb,
        fourbet_ev=fb_ev,
        call_ev=c_ev,
        fold_to_4b_estimate=round(villain_fold_to_4b, 3),
        recommended_action=action,
        action_reasoning=act_reason,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tbre_one_liner(r: ThreeBetRangeResult) -> str:
    return (
        f'[3BET {r.villain_position}@{r.villain_3bet_pct:.0%}|{r.range_type}] '
        f'{r.recommended_action.upper()} | '
        f'eq={r.hero_equity_vs_range:.0%} be={r.breakeven_equity:.0%} '
        f'margin={r.equity_margin:+.1%} | '
        f'4b_ev={r.fourbet_ev:+.2f}BB'
    )
