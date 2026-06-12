"""
Short Stack Range Expander (shortstack_range_expander.py)

Advises push/fold and open-shove ranges for short stacks (under 40 BB).
Short-stack play is fundamentally different: pot odds, reverse implied
odds, and all-in EV dominate. Most hands become push-or-fold decisions.

THEORY:
  PUSH/FOLD DOMINATES below ~20 BB for open raises.
  Between 20-40 BB, open-raising with a min-raise becomes viable, but
  shoves are often better vs. tight opponents.

  PUSH/FOLD PRINCIPLE (Nash Equilibrium):
  When your raise will put you all-in (or commit you to go all-in vs.
  a 3-bet), push is better than min-raise because:
  1. Fold equity is highest with a shove (large bet = more folds)
  2. Avoids awkward min-raise-then-fold situations
  3. Simple to execute; less post-flop decision needed
  4. Prevents villain from flatting cheap and outplaying post-flop

  PUSH RANGES BY STACK AND POSITION (simplified ICM-adjusted):
  Stack    UTG     HJ      CO      BTN     SB(vs_BB)
  5BB      ~60%    ~75%    ~85%    ~95%    ~99%
  10BB     ~20%    ~28%    ~40%    ~60%    ~75%
  15BB     ~10%    ~15%    ~24%    ~40%    ~55%
  20BB     ~8%     ~11%    ~17%    ~30%    ~42%
  25BB     ~6%     ~9%     ~13%    ~22%    ~32%
  30BB     ~5%     ~7%     ~10%    ~17%    ~25%

  These are approximate push-or-fold ranges assuming villain calls correctly.
  Adjust: loosen ~10-15% vs. passive/tight villains; tighten ~10% vs. LAGs.

  CALLING RANGES (facing a shove):
  Use pot odds: call if equity > call_amount / (pot + call_amount)
  EV(call) = equity * (pot + call_amount) - call_amount >= 0
  Hands worth calling: AA-88, AKs-ATs, AKo-AJo, KQs (adjusted by pot odds)

  SHOVE EV FORMULA:
  EV(shove) = fold_pct * blinds_in_pot
            + (1 - fold_pct) * [equity * (hero_stack + villain_call) - hero_stack]
  where blinds_in_pot = antes + posted_blinds already in pot

DISTINCT FROM:
  stack_protection.py:  Stack preservation strategy
  preflop_allin_guide.py: All-in preflop decisions
  THIS MODULE:          SHORT-STACK SPECIFIC push/fold ranges; stack depth
                        thresholds; when to shove vs. min-raise; calling ranges.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Approximate push range % by stack (BB) and position
PUSH_RANGE_PCT: dict = {
    #  position:  {stack: pct}
    'utg':  {5: 0.60, 10: 0.20, 15: 0.10, 20: 0.08, 25: 0.06, 30: 0.05, 35: 0.04, 40: 0.03},
    'hj':   {5: 0.75, 10: 0.28, 15: 0.15, 20: 0.11, 25: 0.09, 30: 0.07, 35: 0.05, 40: 0.04},
    'co':   {5: 0.85, 10: 0.40, 15: 0.24, 20: 0.17, 25: 0.13, 30: 0.10, 35: 0.08, 40: 0.06},
    'btn':  {5: 0.95, 10: 0.60, 15: 0.40, 20: 0.30, 25: 0.22, 30: 0.17, 35: 0.13, 40: 0.10},
    'sb':   {5: 0.99, 10: 0.75, 15: 0.55, 20: 0.42, 25: 0.32, 30: 0.25, 35: 0.19, 40: 0.15},
    'bb':   {5: 0.99, 10: 0.80, 15: 0.60, 20: 0.48, 25: 0.36, 30: 0.28, 35: 0.22, 40: 0.17},
}

# Hand rank percentile (approximate; higher = stronger)
HAND_RANK: dict = {
    'premium': 0.97,   # AA/KK/QQ/AKs
    'strong':  0.90,   # JJ/TT/AQs/AKo
    'good':    0.78,   # 99/88/AQo/AJs/KQs
    'medium':  0.60,   # 77/66/ATo/KJs/QJs
    'playable':0.42,   # 55/44/A9o/KTo/QTo
    'speculative': 0.28, # 33/22/A8o/K9o
    'marginal': 0.15,  # A5o/K8o/Q9o
    'weak':    0.05,   # 72o/83o/etc
}


def _nearest_stack_key(stack_bb: float, position: str) -> int:
    stack_dict = PUSH_RANGE_PCT.get(position, PUSH_RANGE_PCT['co'])
    keys = sorted(stack_dict.keys())
    nearest = min(keys, key=lambda k: abs(k - stack_bb))
    return nearest


def _push_range_pct(stack_bb: float, position: str) -> float:
    stack_dict = PUSH_RANGE_PCT.get(position, PUSH_RANGE_PCT['co'])
    keys = sorted(stack_dict.keys())

    if stack_bb <= keys[0]:
        return stack_dict[keys[0]]
    if stack_bb >= keys[-1]:
        return stack_dict[keys[-1]]

    lo = max(k for k in keys if k <= stack_bb)
    hi = min(k for k in keys if k >= stack_bb)
    if lo == hi:
        return stack_dict[lo]
    frac = (stack_bb - lo) / (hi - lo)
    return round(stack_dict[lo] + frac * (stack_dict[hi] - stack_dict[lo]), 3)


def _hand_is_in_push_range(hand_strength: str, push_pct: float) -> bool:
    hand_rank = HAND_RANK.get(hand_strength, 0.30)
    return hand_rank >= (1.0 - push_pct)


def _shove_ev(
    stack_bb: float,
    hero_equity: float,
    fold_pct: float,
    pot_blinds_bb: float,
) -> float:
    fold_ev = fold_pct * pot_blinds_bb
    call_ev = (1.0 - fold_pct) * (hero_equity * (stack_bb + stack_bb) - stack_bb)
    return round(fold_ev + call_ev, 2)


def _should_min_raise(stack_bb: float) -> bool:
    return stack_bb >= 30.0


@dataclass
class ShortstackResult:
    stack_bb: float
    position: str
    hand_strength: str

    push_range_pct: float
    hand_in_push_range: bool
    shove_ev_bb: float
    use_min_raise: bool

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_shortstack(
    stack_bb: float = 15.0,
    position: str = 'btn',
    hand_strength: str = 'good',
    hero_equity_vs_caller: float = 0.55,
    villain_fold_vs_shove: float = 0.55,
    pot_blinds_bb: float = 1.5,
    n_players_left: int = 1,
) -> ShortstackResult:
    """
    Analyze push/fold decision for a short stack.

    Args:
        stack_bb:              Hero's stack in BB
        position:              Hero's position
        hand_strength:         Hero's hand strength category
        hero_equity_vs_caller: Hero's equity when called
        villain_fold_vs_shove: Aggregate fold% facing a shove
        pot_blinds_bb:         Antes + posted blinds already in pot
        n_players_left:        Players yet to act after hero

    Returns:
        ShortstackResult
    """
    push_pct = _push_range_pct(stack_bb, position)
    in_range = _hand_is_in_push_range(hand_strength, push_pct)
    ev = _shove_ev(stack_bb, hero_equity_vs_caller, villain_fold_vs_shove, pot_blinds_bb)
    use_minr = _should_min_raise(stack_bb)

    if in_range and not use_minr:
        action = 'SHOVE'
    elif in_range and use_minr:
        action = 'MIN_RAISE_OR_SHOVE'
    elif ev > 0 and HAND_RANK.get(hand_strength, 0) >= 0.40:
        action = 'SHOVE_BORDERLINE'
    else:
        action = 'FOLD'

    hand_pct = HAND_RANK.get(hand_strength, 0.30)
    required_hand_strength = round(1.0 - push_pct, 2)

    verdict = (
        f'[SSR {hand_strength}|{position}|{stack_bb:.0f}BB] '
        f'{action} | range_top={push_pct:.0%} EV={ev:+.1f}BB | '
        f'{"IN_RANGE" if in_range else "NOT_IN_RANGE"}'
    )

    reasoning = (
        f'Short-stack analysis: {stack_bb:.0f}BB in {position.upper()}. '
        f'Hand: {hand_strength} (rank {hand_pct:.0%}). '
        f'Push range top: {push_pct:.0%} of hands. '
        f'Required rank for push: {required_hand_strength:.0%}+. '
        f'Villain fold vs shove: {villain_fold_vs_shove:.0%}. '
        f'Shove EV: {ev:+.1f}BB. '
        f'Recommendation: {action}.'
    )

    tips = []

    tips.append(
        f'PUSH RANGE ({position.upper()} at {stack_bb:.0f}BB): top {push_pct:.0%} of hands. '
        f'Your hand ({hand_strength}, rank {hand_pct:.0%}) '
        f'{"IS" if in_range else "is NOT"} in push range. '
        f'Shove EV={ev:+.1f}BB.'
    )

    if stack_bb <= 15:
        tips.append(
            f'PUSH-FOLD ZONE ({stack_bb:.0f}BB): Min-raise is wrong here. '
            f'Shove all-in or fold only. '
            f'Min-raising then folding to 3-bet is a massive ICM/EV mistake.'
        )
    elif stack_bb <= 25:
        tips.append(
            f'SEMI-SHORT ({stack_bb:.0f}BB): Shove is usually correct for opens. '
            f'Min-raise viable only with premium hands (AA/KK/QQ) that want action. '
            f'Stack is too short to play post-flop profitably vs. most villains.'
        )
    else:
        tips.append(
            f'MEDIUM STACK ({stack_bb:.0f}BB): Min-raise to 2-2.5BB is viable. '
            f'If 3-bet, you commit ~60%+ of stack; be willing to call/jam vs. 3-bet '
            f'with hands in your open range.'
        )

    if villain_fold_vs_shove >= 0.60:
        tips.append(
            f'HIGH FOLD% ({villain_fold_vs_shove:.0%}): Villain folds to shoves often. '
            f'Widen push range beyond standard. '
            f'Even marginal hands profitable to shove given immediate fold equity.'
        )
    elif villain_fold_vs_shove <= 0.35:
        tips.append(
            f'LOW FOLD% ({villain_fold_vs_shove:.0%}): Villain calls wide. '
            f'Tighten push range; need stronger equity ({hero_equity_vs_caller:.0%}) to justify shove. '
            f'Only push premium-to-good hands.'
        )

    if n_players_left >= 3:
        tips.append(
            f'MULTIPLE PLAYERS ({n_players_left} left): Tighten range. '
            f'Likelihood of at least one caller increases. '
            f'Subtract ~5-10% from push range width for each extra player.'
        )

    return ShortstackResult(
        stack_bb=stack_bb,
        position=position,
        hand_strength=hand_strength,
        push_range_pct=push_pct,
        hand_in_push_range=in_range,
        shove_ev_bb=ev,
        use_min_raise=use_minr,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ssr_one_liner(r: ShortstackResult) -> str:
    return (
        f'[SSR {r.hand_strength}|{r.position}|{r.stack_bb:.0f}BB] '
        f'{r.recommended_action} range_top={r.push_range_pct:.0%} EV={r.shove_ev_bb:+.1f}BB'
    )
