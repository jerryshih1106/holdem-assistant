"""
Combo Draw Specialist (combo_draw_specialist.py)

Analyzes COMBO DRAWS (flush draw + straight draw simultaneously) --
the strongest semi-bluffs in No-Limit Hold'em. These draws have equity
approaching 50-55% on the flop, making aggressive play (semi-bluff jams,
check-raises) often correct even when behind.

THEORY:
  COMBO DRAW = two or more draws simultaneously. Examples:
    - Flush draw (9 outs) + OESD (8 outs) = ~15 outs (some overlap)
    - Flush draw (9) + gutshot (4) = ~12 outs
    - Flush draw (9) + pair/overcard (3) = ~12 outs
    - Two overcards + OESD = ~14 outs
    - Flush draw + gutshot + overcard = ~15 outs

  OUT CALCULATION (avoid double-counting):
    outs = fd_outs + sd_outs + oc_outs - overlap
    overlap is typically 1-2 cards (cards that complete both draws)

  EQUITY WITH N OUTS:
    Flop equity (2 cards to come): ~N * 4% - 2% (for N>8, use N*3.8%)
    Turn equity (1 card to come):  ~N * 2%

  COMBO DRAW STRENGTH:
    >= 15 outs:  MONSTER_COMBO  (~54-58% equity)  -- often favorite
    12-14 outs:  STRONG_COMBO   (~46-52% equity)  -- semi-bluff aggressively
    9-11 outs:   GOOD_COMBO     (~38-44% equity)  -- standard semi-bluff
    6-8 outs:    WEAK_COMBO     (~28-34% equity)  -- be cautious; SPR-dependent

  RECOMMENDED ACTIONS:
    MONSTER_COMBO (SPR>4):  Raise / semi-bluff jam; pot equity favorite
    MONSTER_COMBO (SPR<=4): Jam / commit; pure +EV shove
    STRONG_COMBO  (IP):     Raise/semi-bluff; call is also fine
    STRONG_COMBO  (OOP):    Check-raise; or lead with 50-75%pot
    GOOD_COMBO    (IP):     Call or float; raise vs weak c-bets
    GOOD_COMBO    (OOP):    Lead small (30-40%); check-raise if likely bet
    WEAK_COMBO:             Usually call; jam only with fold equity + equity

  SPR BREAKEVEN SHOVE:
    EV(shove) = equity * total_pot - call_amount
    Hero should shove when equity > (call_amount / total_pot)

DISTINCT FROM:
  hand_equity.py:         Generic hand equity
  draw_equity.py:         Simple single-draw equity
  outs_calculator.py:     Counts outs only
  THIS MODULE:            COMBO DRAW-SPECIFIC analysis; out combination;
                          semi-bluff shove EV; check-raise spots;
                          multi-draw synergies; street-by-street strategy.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Out overlap between draw types (conservative; actual may vary by board)
DRAW_OUTS: dict = {
    'flush_draw':      9,
    'oesd':            8,
    'gutshot':         4,
    'overcard':        3,
    'double_overcard': 6,  # both overcards live
    'pair_draw':       2,  # drawing to 2-pair or better
    'backdoor_flush':  2,  # not full flush draw, partial
}

# Overlap between combo draw types
OVERLAP: dict = {
    frozenset(['flush_draw', 'oesd']):         2,
    frozenset(['flush_draw', 'gutshot']):       1,
    frozenset(['flush_draw', 'overcard']):      1,
    frozenset(['flush_draw', 'double_overcard']): 2,
    frozenset(['oesd', 'overcard']):            0,
    frozenset(['oesd', 'double_overcard']):     0,
    frozenset(['gutshot', 'overcard']):         0,
    frozenset(['gutshot', 'double_overcard']):  0,
}


def _total_outs(draw_types: list) -> int:
    raw = sum(DRAW_OUTS.get(d, 0) for d in draw_types)
    total_overlap = 0
    for i, d1 in enumerate(draw_types):
        for d2 in draw_types[i+1:]:
            total_overlap += OVERLAP.get(frozenset([d1, d2]), 0)
    return max(0, raw - total_overlap)


def _equity_flop(outs: int) -> float:
    """Rule of 4 adjusted for larger out counts."""
    if outs <= 8:
        return round(outs * 0.04, 3)
    else:
        return round(min(0.80, outs * 0.038), 3)


def _equity_turn(outs: int) -> float:
    return round(min(0.70, outs * 0.02), 3)


def _combo_strength(outs: int) -> str:
    if outs >= 15:
        return 'monster_combo'
    elif outs >= 12:
        return 'strong_combo'
    elif outs >= 9:
        return 'good_combo'
    else:
        return 'weak_combo'


def _shove_ev(equity: float, hero_stack: float, villain_stack: float, pot_bb: float) -> float:
    effective_stack = min(hero_stack, villain_stack)
    total_pot = pot_bb + 2 * effective_stack
    ev = equity * total_pot - effective_stack
    return round(ev, 1)


def _semi_bluff_shove_correct(
    equity: float,
    hero_stack: float,
    villain_stack: float,
    pot_bb: float,
    villain_fold_pct: float = 0.30,
) -> bool:
    eff = min(hero_stack, villain_stack)
    fold_ev = villain_fold_pct * pot_bb
    call_ev = (1.0 - villain_fold_pct) * _shove_ev(equity, hero_stack, villain_stack, pot_bb)
    total_ev = fold_ev + call_ev
    return total_ev > 0.0


def _action_recommendation(
    combo_strength: str,
    street: str,
    position: str,
    spr: float,
    equity: float,
    villain_fold_pct: float,
) -> str:
    if spr <= 2.0:
        return 'jam'

    if combo_strength == 'monster_combo':
        if spr <= 4.0:
            return 'semi_bluff_shove'
        return 'raise_semi_bluff'

    if combo_strength == 'strong_combo':
        if position == 'ip':
            if villain_fold_pct >= 0.55:
                return 'raise_semi_bluff'
            return 'call_and_evaluate'
        else:
            return 'check_raise_semi_bluff'

    if combo_strength == 'good_combo':
        if equity >= 0.40 and spr <= 5.0:
            return 'raise_semi_bluff'
        if position == 'ip':
            return 'call_float'
        return 'lead_small'

    # weak_combo
    if villain_fold_pct >= 0.65:
        return 'lead_bluff'
    return 'check_fold_or_call_cheaply'


@dataclass
class ComboDrawResult:
    draw_types: List[str]
    total_outs: int
    equity_flop: float
    equity_turn: float
    combo_strength: str

    street: str
    position: str
    spr: float
    pot_bb: float

    recommended_action: str
    shove_ev_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_combo_draw(
    draw_types: Optional[List[str]] = None,
    street: str = 'flop',
    position: str = 'ip',
    spr: float = 6.0,
    pot_bb: float = 15.0,
    hero_stack_bb: float = 90.0,
    villain_stack_bb: float = 90.0,
    villain_fold_pct: float = 0.40,
) -> ComboDrawResult:
    """
    Analyze a combo draw situation and recommend action.

    Args:
        draw_types:       List of draws (e.g. ['flush_draw','oesd'])
        street:           'flop' / 'turn'
        position:         'ip' / 'oop'
        spr:              Stack-to-pot ratio
        pot_bb:           Current pot in BB
        hero_stack_bb:    Hero's remaining stack in BB
        villain_stack_bb: Villain's remaining stack in BB
        villain_fold_pct: Villain's estimated fold frequency to aggression

    Returns:
        ComboDrawResult
    """
    if draw_types is None:
        draw_types = ['flush_draw', 'oesd']

    outs = _total_outs(draw_types)
    eq_flop = _equity_flop(outs)
    eq_turn = _equity_turn(outs)
    equity  = eq_flop if street == 'flop' else eq_turn
    strength = _combo_strength(outs)

    action = _action_recommendation(strength, street, position, spr, equity, villain_fold_pct)
    shove_ev = _shove_ev(equity, hero_stack_bb, villain_stack_bb, pot_bb)

    eq_pct = round(equity * 100, 1)
    eff_stack = min(hero_stack_bb, villain_stack_bb)

    verdict = (
        f'[CDS {"+".join(draw_types)}|{street}|{position}] '
        f'{strength.upper()} {outs}outs eq={eq_pct}% | '
        f'{action} | SPR={spr:.1f}'
    )

    reasoning = (
        f'Combo draw: {draw_types}. Total outs: {outs}. '
        f'Equity on {street}: {eq_pct}%. '
        f'Combo strength: {strength}. '
        f'Position: {position.upper()}, SPR={spr:.1f}. '
        f'Villain fold%: {villain_fold_pct:.0%}. '
        f'Recommended action: {action}. '
        f'Shove EV (if jamming): {shove_ev:+.1f}BB.'
    )

    tips = []

    tips.append(
        f'COMBO DRAW: {outs} outs ({draw_types}). '
        f'Equity on {street}: {eq_pct}% ({strength}). '
        f'Shove EV: {shove_ev:+.1f}BB vs {eff_stack:.0f}BB effective stack.'
    )

    tips.append(
        f'RECOMMENDED ACTION: {action.upper().replace("_", " ")}. '
        f'{"Equity favorite -- aggressive play extracts maximum value." if equity >= 0.48 else "Semi-bluff equity + fold equity = net positive."}'
    )

    if strength == 'monster_combo':
        tips.append(
            f'MONSTER COMBO ({outs} outs / {eq_pct}% equity): Nearly or fully a favorite. '
            f'Semi-bluff jam is correct at SPR {spr:.1f}. '
            f'Never just call off stack; build pot aggressively.'
        )
    elif strength == 'strong_combo':
        tips.append(
            f'STRONG COMBO ({outs} outs / {eq_pct}% equity): Check-raise or lead big. '
            f'vs {"IP villain: calling also fine" if position == "oop" else "OOP: check-raise as primary line"}. '
            f'Fold equity (villain folds {villain_fold_pct:.0%}) plus equity = +EV aggression.'
        )

    if street == 'flop' and outs >= 9:
        eq_if_miss = _equity_turn(outs)
        tips.append(
            f'TWO STREETS: Flop equity {eq_pct}% (2 cards to come). '
            f'If you miss turn, still {eq_if_miss*100:.0f}% equity (1 card). '
            f'Play aggressively NOW before equity diminishes.'
        )

    if villain_fold_pct >= 0.55:
        fold_ev = villain_fold_pct * pot_bb
        tips.append(
            f'FOLD EQUITY BONUS: Villain folds {villain_fold_pct:.0%} -> '
            f'immediate +{fold_ev:.1f}BB EV from folds alone. '
            f'Even without hitting, aggression is profitable.'
        )

    if action in ('raise_semi_bluff', 'semi_bluff_shove', 'jam'):
        suggested_raise = round(pot_bb * 2.5, 1)
        tips.append(
            f'SIZING: For semi-bluff raise, use ~2.5x pot ({suggested_raise:.0f}BB). '
            f'For shove, effective stack = {eff_stack:.0f}BB. '
            f'Shove EV = {shove_ev:+.1f}BB.'
        )

    return ComboDrawResult(
        draw_types=draw_types,
        total_outs=outs,
        equity_flop=eq_flop,
        equity_turn=eq_turn,
        combo_strength=strength,
        street=street,
        position=position,
        spr=spr,
        pot_bb=pot_bb,
        recommended_action=action,
        shove_ev_bb=shove_ev,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def cds_one_liner(r: ComboDrawResult) -> str:
    eq = r.equity_flop if r.street == 'flop' else r.equity_turn
    return (
        f'[CDS {r.combo_strength}|{r.street}|{r.position}] '
        f'{r.total_outs}outs eq={eq*100:.0f}% | {r.recommended_action}'
    )
