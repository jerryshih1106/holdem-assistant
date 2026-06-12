"""
Preflop Sizing Optimizer (preflop_sizing_optimizer.py)

Computes the optimal open-raise size based on:
1. Position (BTN/CO/HJ/MP/UTG)
2. Villain 3-bet frequency from that position
3. Stack depth
4. Antes (affects pot size relative to open size)
5. Number of players left to act

THEORY:
  Open-raise sizing is not fixed -- it should adapt to:
  - Villain 3-bet frequency: if they 3-bet a lot, open smaller
    (you risk less to fold). If they rarely 3-bet, open bigger for value.
  - Position: IP opens can be smaller (position advantage compresses EV).
    OOP opens should be larger to deny IP callers' implied odds.
  - Antes: with antes, there's dead money in the pot. Open smaller
    (e.g., 2x instead of 3x) because pot odds are already worse.
  - Stack depth: at 25BB, open 2-2.5x. At 100BB+, 3x. Deep stack:
    larger opens to protect wider range.

MATHEMATICAL BASIS:
  Optimal open size balances:
    EV(fold) = dead_money in pot (antes + blinds already in)
    EV(call) = equity advantage × (pot + continuation bets) - open_size
    EV(3-bet) = -call_amount vs 3-bet
  We minimize the case where 3-bets are +EV for villain, which means
  when villain 3-bet freq is high, open smaller (less to fold).

KEY OUTPUTS:
  1. Recommended open size in BB
  2. Linear-scaled recommendation: tight/standard/max
  3. Defense frequency needed to protect opening range
  4. Stack-to-open ratio (SPR after open called)

POSITION NAMING:
  6-max: btn, co, hj, mp, sb, bb
  9-max: btn, co, hj, mp2, mp1, utg+1, utg, sb, bb

DISTINCT FROM:
  open_raise_guide.py:        Recommends WHICH hands to open from each position
  three_bet_strategy.py:      3-bet decision and sizing
  squeeze_ev_optimizer.py:    Squeeze EV optimization
  THIS MODULE:                Optimal SIZING of open-raise based on
                              position + villain tendencies + stack depth + antes.
"""

from dataclasses import dataclass, field
from typing import List


# Base open sizes (BB) for standard 100BB cash game
# (no antes, typical villain 3-bet freq)
BASE_OPEN_SIZE: dict = {
    'btn': 2.5,
    'co':  2.5,
    'hj':  3.0,
    'mp':  3.0,
    'mp2': 3.0,
    'utg': 3.0,
    'sb':  3.0,  # SB opens are large; BB has direct odds
}

# Adjustment to open size based on villain 3-bet frequency
# Higher 3-bet freq -> smaller open (less to fold)
THREE_BET_FREQ_ADJ: dict = {
    # 3-bet freq -> multiplier on open size
    'very_low':  1.20,   # <5%: open bigger; exploit by value-opening wider
    'low':       1.10,   # 5-8%: slight upsize
    'standard':  1.00,   # 9-12%: no change
    'high':      0.85,   # 13-18%: reduce open size
    'very_high': 0.75,   # >18%: min-raise or fold pre
}

# Stack depth multiplier
STACK_DEPTH_ADJ: dict = {
    'short':    0.90,   # 15-30BB: open smaller; less room for post-flop
    'medium':   1.00,   # 30-80BB
    'deep':     1.10,   # 80-150BB: open bigger for IP advantage
    'very_deep': 1.15,  # 150BB+
}

# Ante size multiplier: antes shrink optimal raise size
# (dead money already in pot reduces the need to open large)
ANTE_ADJ: dict = {
    'no_ante':   1.00,
    'btn_ante':  0.90,   # button posts ante (common in tournaments)
    'bb_ante':   0.90,   # BB posts big ante
    'full_ante': 0.80,   # all players post antes (live cash)
}


def _classify_3bet_freq(three_bet_pct: float) -> str:
    if three_bet_pct < 0.05:
        return 'very_low'
    elif three_bet_pct < 0.08:
        return 'low'
    elif three_bet_pct < 0.13:
        return 'standard'
    elif three_bet_pct < 0.18:
        return 'high'
    else:
        return 'very_high'


def _classify_stack(stack_bb: float) -> str:
    if stack_bb <= 30:
        return 'short'
    elif stack_bb <= 80:
        return 'medium'
    elif stack_bb <= 150:
        return 'deep'
    else:
        return 'very_deep'


def _compute_open_size(
    position: str,
    three_bet_freq: float,
    stack_bb: float,
    ante_type: str,
    n_players_to_act: int,
) -> float:
    base = BASE_OPEN_SIZE.get(position, 3.0)
    freq_class = _classify_3bet_freq(three_bet_freq)
    freq_adj = THREE_BET_FREQ_ADJ.get(freq_class, 1.0)
    stack_class = _classify_stack(stack_bb)
    stack_adj = STACK_DEPTH_ADJ.get(stack_class, 1.0)
    ante_adj = ANTE_ADJ.get(ante_type, 1.0)
    n_players_adj = 1.0 + (n_players_to_act - 2) * 0.05  # more players -> slightly bigger

    raw = base * freq_adj * stack_adj * ante_adj * n_players_adj

    if stack_bb <= 20:
        raw = min(raw, stack_bb * 0.20)  # don't open more than 20% of stack

    return round(max(2.0, min(5.0, raw)), 1)


def _defense_frequency(
    open_size_bb: float,
    pot_bb_before_open: float,
) -> float:
    """Minimum defense frequency needed to prevent villain from profitably stealing."""
    call_amount = open_size_bb
    total_pot = pot_bb_before_open + open_size_bb
    mdf = 1.0 - (call_amount / total_pot)
    return round(mdf, 3)


def _spr_after_call(
    stack_bb: float,
    open_size_bb: float,
    dead_money_bb: float,
) -> float:
    """Stack-to-pot ratio if villain calls."""
    pot = open_size_bb * 2 + dead_money_bb  # hero open + villain call + antes/blinds
    remaining_stack = stack_bb - open_size_bb
    return round(remaining_stack / max(1.0, pot), 2)


def _size_label(open_size_bb: float, base_size: float) -> str:
    ratio = open_size_bb / base_size
    if ratio >= 1.15:
        return 'max_open'
    elif ratio >= 0.95:
        return 'standard_open'
    elif ratio >= 0.80:
        return 'small_open'
    else:
        return 'min_raise'


@dataclass
class PreflopSizingResult:
    position: str
    three_bet_freq: float
    stack_bb: float
    ante_type: str
    n_players_to_act: int

    recommended_open_bb: float
    size_label: str
    three_bet_freq_class: str
    stack_depth_class: str
    defense_frequency: float
    spr_after_call: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def optimize_preflop_sizing(
    position: str = 'btn',
    three_bet_freq: float = 0.10,
    stack_bb: float = 100.0,
    ante_type: str = 'no_ante',
    n_players_to_act: int = 3,
    dead_money_bb: float = 1.5,
) -> PreflopSizingResult:
    """
    Compute optimal open-raise size.

    Args:
        position:           Seat (btn/co/hj/mp/utg/sb)
        three_bet_freq:     Villain 3-bet frequency (0-1)
        stack_bb:           Effective stack in BB
        ante_type:          'no_ante' / 'btn_ante' / 'bb_ante' / 'full_ante'
        n_players_to_act:   Players yet to act (BB + any callers in)
        dead_money_bb:      Antes + posted blinds already in pot

    Returns:
        PreflopSizingResult
    """
    open_bb = _compute_open_size(
        position, three_bet_freq, stack_bb, ante_type, n_players_to_act
    )
    freq_class = _classify_3bet_freq(three_bet_freq)
    stack_class = _classify_stack(stack_bb)
    base_size = BASE_OPEN_SIZE.get(position, 3.0)
    size_lbl = _size_label(open_bb, base_size)
    defense_freq = _defense_frequency(open_bb, dead_money_bb)
    spr = _spr_after_call(stack_bb, open_bb, dead_money_bb)

    verdict = (
        f'[PSO {position}|{stack_bb:.0f}BB] '
        f'OPEN {open_bb:.1f}BB ({size_lbl}) | '
        f'3bet_freq={three_bet_freq:.0%}({freq_class}) | spr={spr:.1f}'
    )

    reasoning = (
        f'Position: {position}. Stack: {stack_bb:.0f}BB ({stack_class}). '
        f'Villain 3-bet freq: {three_bet_freq:.0%} ({freq_class}). '
        f'Ante: {ante_type}. Players to act: {n_players_to_act}. '
        f'Recommended open: {open_bb:.1f}BB ({size_lbl}). '
        f'SPR if called: {spr:.1f}. Defense needed: {defense_freq:.0%}.'
    )

    tips = []

    tips.append(
        f'OPEN SIZE: {position.upper()} {open_bb:.1f}BB ({size_lbl}). '
        f'3-bet freq {three_bet_freq:.0%} = {freq_class}. '
        f'{"Open smaller vs frequent 3-bettors (less to fold)." if freq_class in ("high","very_high") else "Open standard or bigger vs passive opponents."}'
    )

    tips.append(
        f'DEFENSE: To prevent profitable steals, defend {defense_freq:.0%} of hands. '
        f'(3-bet + call combined >= {defense_freq:.0%}). '
        f'With {three_bet_freq:.0%} villain 3-bet, your call range covers '
        f'{max(0.0, defense_freq - three_bet_freq):.0%} of range.'
    )

    tips.append(
        f'SPR: After {open_bb:.1f}BB open is called: SPR={spr:.1f}. '
        f'{"Deep SPR (>8): suited connectors / small pairs have good implied odds." if spr >= 8 else "Medium SPR (4-8): prefer equity-heavy hands." if spr >= 4 else "Low SPR (<4): open pairs/broadways. Suited connectors need bigger stacks."}'
    )

    if freq_class in ('high', 'very_high'):
        tips.append(
            f'HIGH 3-BET VILLAIN: {three_bet_freq:.0%} 3-bet means you lose {open_bb:.1f}BB often. '
            f'Counter: open {open_bb:.1f}BB (smaller), or add 4-bet bluff range (A5s, KQs). '
            f'Do NOT open small to fold -- widen 4-bet range instead.'
        )
    elif ante_type != 'no_ante':
        tips.append(
            f'ANTES IN PLAY: {ante_type} adds dead money. Pot odds for callers improve, '
            f'so defend wider vs opens. Your own opens can be {open_bb:.1f}BB (reduced by antes). '
            f'Steal-raises more profitable with antes.'
        )

    return PreflopSizingResult(
        position=position,
        three_bet_freq=three_bet_freq,
        stack_bb=stack_bb,
        ante_type=ante_type,
        n_players_to_act=n_players_to_act,
        recommended_open_bb=open_bb,
        size_label=size_lbl,
        three_bet_freq_class=freq_class,
        stack_depth_class=stack_class,
        defense_frequency=defense_freq,
        spr_after_call=spr,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pso_one_liner(r: PreflopSizingResult) -> str:
    return (
        f'[PSO {r.position}|{r.stack_bb:.0f}BB] '
        f'OPEN {r.recommended_open_bb:.1f}BB ({r.size_label}) | '
        f'3bet={r.three_bet_freq:.0%} | spr={r.spr_after_call:.1f}'
    )
