"""
Squeeze Play Advisor (squeeze_play_advisor.py)

Advises PREFLOP SQUEEZE plays: when to 3-bet after an open + caller(s),
optimal sizing, range construction, and expected value.

THEORY:
  SQUEEZE = 3-bet facing: [open] + [1+ callers]

  WHY SQUEEZE IS PROFITABLE:
  1. Multiple opponents = more folds needed, but callers have CAPPED ranges
     (they called, not 3-bet; so they rarely have premium hands)
  2. Callers behind the open are price-sensitive; large squeeze forces them out
  3. Original opener may fold decent hands facing large re-raise + callers
  4. Build large pot in position (if IP) with strong range
  5. Deny equity to multiple weak-ish hands simultaneously

  SIZING FORMULA:
  Squeeze_size = 3x-4x open + 1BB per caller (dead money)
  Examples:
    Open 3BB, 1 caller: Squeeze to ~12-14BB (4x + 1 = 13BB)
    Open 3BB, 2 callers: Squeeze to ~14-16BB (4x + 2 = 14BB)
    Open 2.5BB, 1 caller: Squeeze to ~11-12BB

  FOLD EQUITY vs. N CALLERS:
  - More callers = more players to fold = each contributes ~20-30BB to pot
  - But: more callers also means more players who could hit flop after call
  - Net effect: more callers generally INCREASES squeeze EV due to dead money
  - Each extra caller adds ~2BB to optimal squeeze size

  VALUE RANGE FOR SQUEEZE:
  - UTG open: AJ+, KQ, TT+ (tight open range; squeeze needs premium)
  - CO/BTN open: AJ+, KQ+, 99+ (wider open range; squeeze slightly less strong)
  - Vs. weak opens: can squeeze looser (ATo+, 88+, KQo)

  BLUFF RANGE FOR SQUEEZE (suited blockers):
  - AXs (blocks AA, AK combos)
  - KXs (blocks KK, AK combos)
  - Suited connectors (56s, 67s): have post-flop equity if called
  - Should represent ~1/3 of total squeeze range (alpha for 3.5x sizing)

  EXPECTED VALUE FORMULA:
  EV(squeeze) = fold_equity * pot_after_squeeze
               + (1 - fold_equity) * [post_flop_equity * final_pot - call_amount]
  where:
    fold_equity = P(all opponents fold)
    P(all fold) = product of each player's fold% vs. squeeze

DISTINCT FROM:
  three_bet_ranges.py:  General 3-bet range construction
  preflop_sizing_optimizer.py: Open size optimization
  THIS MODULE:          SQUEEZE-SPECIFIC: multi-opponent folds; dead money;
                        sizing with callers; squeeze range vs. opener type;
                        EV computation including dead money.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Base fold% vs. squeeze by player type
FOLD_VS_SQUEEZE: dict = {
    'fish':           0.55,
    'rec':            0.60,
    'calling_station': 0.40,
    'tight':          0.70,
    'nit':            0.78,
    'reg':            0.58,
    'lag':            0.45,
    'tag':            0.65,
    'unknown':        0.58,
}

# Opener fold% (higher; they opened but now face multi-way squeeze)
OPENER_FOLD_VS_SQUEEZE: dict = {
    'fish':           0.48,
    'rec':            0.52,
    'tight':          0.62,
    'nit':            0.72,
    'reg':            0.50,
    'lag':            0.38,
    'tag':            0.55,
    'unknown':        0.50,
}

# Open position -> implied strength
OPEN_POSITION_STRENGTH: dict = {
    'utg': 'strong',
    'utg1': 'strong',
    'utg2': 'strong',
    'mp': 'moderate',
    'hj': 'moderate',
    'co': 'moderate',
    'btn': 'wide',
    'sb': 'wide',
}


def _squeeze_size(open_bb: float, n_callers: int, multiplier: float = 4.0) -> float:
    size = open_bb * multiplier + n_callers * 1.5
    return round(size, 1)


def _dead_money(open_bb: float, callers: int) -> float:
    return round(open_bb + callers * open_bb, 1)


def _fold_probability(
    opener_type: str,
    caller_types: list,
) -> float:
    opener_fold = OPENER_FOLD_VS_SQUEEZE.get(opener_type, 0.50)
    total_fold = opener_fold
    for ct in caller_types:
        total_fold *= FOLD_VS_SQUEEZE.get(ct, 0.55)
    return round(total_fold, 3)


def _ev(
    fold_pct: float,
    pot_dead_money: float,
    squeeze_size: float,
    hero_equity: float,
    total_pot_if_called: float,
) -> float:
    fold_ev = fold_pct * (pot_dead_money + 1.5)  # win dead money
    call_ev = (1.0 - fold_pct) * (hero_equity * total_pot_if_called - squeeze_size)
    return round(fold_ev + call_ev, 1)


def _range_recommendation(hero_hand: str, opener_position: str) -> str:
    strength = OPEN_POSITION_STRENGTH.get(opener_position.lower(), 'moderate')
    if strength == 'strong':
        return 'premium_value_range_only: AA/KK/QQ/AKs for value; AXs/KXs as bluff'
    elif strength == 'moderate':
        return 'value: JJ+/AK/AQs; bluff: AXs/KXs suited-connectors'
    else:
        return 'value: TT+/AK/AQ; bluff: any suited-A/suited-K/sc-with-equity'


@dataclass
class SqueezeResult:
    open_bb: float
    n_callers: int
    opener_type: str
    caller_types: List[str]

    squeeze_size_bb: float
    dead_money_bb: float
    combined_fold_pct: float
    squeeze_ev_bb: float

    verdict: str
    range_advice: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_squeeze(
    open_bb: float = 3.0,
    n_callers: int = 1,
    opener_type: str = 'reg',
    caller_types: Optional[List[str]] = None,
    opener_position: str = 'co',
    hero_position: str = 'btn',
    hero_hand: str = 'AKs',
    hero_equity_if_called: float = 0.55,
    hero_stack_bb: float = 100.0,
    pot_before_bb: float = 1.5,
) -> SqueezeResult:
    """
    Advise on a preflop squeeze play.

    Args:
        open_bb:               Opener's raise size in BB
        n_callers:             Number of callers between opener and hero
        opener_type:           Opener's player type
        caller_types:          List of caller player types
        opener_position:       Opener's position (UTG, CO, BTN, etc.)
        hero_position:         Hero's position
        hero_hand:             Hero's hand category
        hero_equity_if_called: Hero's equity vs. the range that calls
        hero_stack_bb:         Hero's stack in BB
        pot_before_bb:         Blinds already in pot

    Returns:
        SqueezeResult
    """
    if caller_types is None:
        caller_types = ['rec'] * n_callers

    sq_size = _squeeze_size(open_bb, n_callers)
    dead = _dead_money(open_bb, n_callers)
    total_pot_if_called = sq_size + dead + pot_before_bb + sq_size
    fold_pct = _fold_probability(opener_type, caller_types)
    ev = _ev(fold_pct, dead + pot_before_bb, sq_size, hero_equity_if_called, total_pot_if_called)
    range_advice = _range_recommendation(hero_hand, opener_position)

    position_advantage = 'IP' if hero_position.lower() in ('btn', 'co', 'hj') else 'OOP'
    is_profitable = ev > 0 and fold_pct >= 0.40

    verdict = (
        f'[SQZ {n_callers}caller(s)|{opener_position}->open|{position_advantage}] '
        f'{"SQUEEZE" if is_profitable else "PASS"} to {sq_size:.0f}BB | '
        f'fold%={fold_pct:.0%} EV={ev:+.1f}BB dead={dead:.0f}BB'
    )

    reasoning = (
        f'Squeeze analysis: open={open_bb:.0f}BB from {opener_position} ({opener_type}). '
        f'{n_callers} caller(s) ({caller_types}). Dead money={dead:.0f}BB. '
        f'Squeeze to {sq_size:.0f}BB. '
        f'Combined fold%={fold_pct:.0%}. '
        f'EV={ev:+.1f}BB. Range: {range_advice}.'
    )

    tips = []

    tips.append(
        f'SQUEEZE SIZE: {sq_size:.0f}BB (={open_bb:.0f}BB x4 + {n_callers}x dead). '
        f'Dead money in pot: {dead:.0f}BB. '
        f'Pot if all fold: {dead + pot_before_bb:.0f}BB profit.'
    )

    if is_profitable:
        tips.append(
            f'SQUEEZE PROFITABLE: EV={ev:+.1f}BB. Fold%={fold_pct:.0%}. '
            f'{"Multiple rec callers: high fold equity + dead money." if any(ct in ("rec","fish") for ct in caller_types) else "Standard fold equity."}'
        )
    else:
        tips.append(
            f'SQUEEZE MARGINAL/UNFAVORABLE: EV={ev:+.1f}BB. '
            f'Fold%={fold_pct:.0%} may be too low. '
            f'Only squeeze value hands ({range_advice.split(":")[0].strip()}).'
        )

    if n_callers >= 2:
        tips.append(
            f'MULTI-WAY SQUEEZE: {n_callers} callers = more dead money ({dead:.0f}BB) '
            f'but also more players to fade if called. '
            f'Tighten your squeeze range; focus on premium value + high-equity semi-bluffs.'
        )

    if position_advantage == 'IP':
        tips.append(
            f'IP SQUEEZE advantage: If called, play post-flop in position. '
            f'Can take control with c-bets on most boards. '
            f'IP squeezes can be slightly wider.'
        )
    else:
        tips.append(
            f'OOP SQUEEZE: Tighten value range. OOP post-flop is difficult. '
            f'Need more equity or premium hand to justify OOP squeeze.'
        )

    tips.append(
        f'RANGE ADVICE ({opener_position} open): {range_advice}. '
        f'Balance value hands with ~33% bluffs using blockers (Ax/Kx suited).'
    )

    return SqueezeResult(
        open_bb=open_bb,
        n_callers=n_callers,
        opener_type=opener_type,
        caller_types=caller_types,
        squeeze_size_bb=sq_size,
        dead_money_bb=dead,
        combined_fold_pct=fold_pct,
        squeeze_ev_bb=ev,
        verdict=verdict,
        range_advice=range_advice,
        reasoning=reasoning,
        tips=tips,
    )


def sqz_one_liner(r: SqueezeResult) -> str:
    action = 'SQUEEZE' if r.squeeze_ev_bb > 0 and r.combined_fold_pct >= 0.40 else 'PASS'
    return (
        f'[SQZ {r.n_callers}caller] {action} {r.squeeze_size_bb:.0f}BB | '
        f'fold={r.combined_fold_pct:.0%} EV={r.squeeze_ev_bb:+.1f}BB'
    )
