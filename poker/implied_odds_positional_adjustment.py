"""
Implied Odds Positional Adjustment (implied_odds_positional_adjustment.py)

IP draws are worth significantly more than OOP draws because of additional
information and betting control. This module quantifies the position premium
on implied odds and adjusts drawing decisions accordingly.

THEORY:
  POSITION PREMIUM ON DRAWS:
  IP: You see villain's action before deciding whether to bet/call on the next
      street. If your draw completes, you can extract maximum value. If it misses,
      you can check back cheaply.

  OOP: You must act first without information. If you check, you lose a free card
       bet opportunity. If you bet into a missed draw, you waste chips. Villain
       may also bet big on scary cards, putting you in a tough spot.

  IMPLIED ODDS MULTIPLIER BY POSITION:
  - IP draw: multiply effective implied odds by 1.25-1.40
  - OOP draw: multiply by 0.70-0.85 (reduced implied odds)

  WHY IP DRAWS ARE WORTH MORE:
  1. CONTROL: If draw hits, can bet or check-raise for value
  2. FREE CARDS: If draw misses, can check back cheaply
  3. BLUFF EFFICIENCY: Can semi-bluff with position support
  4. POT GEOMETRY: Can control pot size entering later streets

  DRAW TYPE POSITION PREMIUMS:
  - Flush draw IP: Need 4.5x call (vs 6x OOP) because better implied odds
  - OESD IP: Need 4.0x call (vs 5.5x OOP)
  - Combo draw IP: Very strong; can play almost any odds IP
  - Gutshot OOP: Almost never profitable; too few outs + OOP discount

  REQUIRED STACK:CALL RATIOS:
  IP_FLUSH_DRAW  = 4.5:1 (need 4.5 chips behind for every 1 chip to call)
  OOP_FLUSH_DRAW = 6.5:1
  IP_OESD        = 4.0:1
  OOP_OESD       = 6.0:1
  IP_GUTSHOT     = 8.0:1
  OOP_GUTSHOT    = 12.0:1

  POSITIONAL IMPLIED ODDS CALCULATION:
  adjusted_io = base_io × position_multiplier × villain_type_multiplier

  VILLAIN PAYOFF MULTIPLIER:
  - Fish: 1.40 (will pay off big when draw hits)
  - Calling station: 1.60
  - Nit: 0.70 (will fold to big river bets)
  - LAG: 0.85 (aggression disrupts extracting value)

DISTINCT FROM:
  implied_odds.py:          General implied odds formula
  implied_odds_advisor.py:  Implied odds advice
  draw_advisor.py:          General draw strategy
  THIS MODULE:              POSITION PREMIUM SPECIFICALLY; IP vs OOP multipliers;
                            required stack ratios by draw type; villain payoff factor.
"""

from dataclasses import dataclass, field
from typing import List


REQUIRED_STACK_CALL_RATIO: dict = {
    'flush_draw': {'ip': 4.5, 'oop': 6.5},
    'oesd':       {'ip': 4.0, 'oop': 6.0},
    'combo_draw': {'ip': 2.5, 'oop': 4.0},
    'gutshot':    {'ip': 8.0, 'oop': 12.0},
    'backdoor':   {'ip': 18.0, 'oop': 28.0},
}

POSITION_MULTIPLIER: dict = {
    'ip':  1.30,
    'oop': 0.78,
}

VILLAIN_PAYOFF_MULTIPLIER: dict = {
    'fish':             1.40,
    'calling_station':  1.60,
    'rec':              1.15,
    'nit':              0.70,
    'lag':              0.85,
    'reg':              1.00,
}

DRAW_OUTS: dict = {
    'flush_draw': 9,
    'oesd':       8,
    'combo_draw': 15,
    'gutshot':    4,
    'backdoor':   2,
}


def _pot_odds_needed(draw_type: str) -> float:
    outs = DRAW_OUTS.get(draw_type, 8)
    remaining = 47
    hit_prob = outs / remaining
    return round(1.0 / hit_prob, 2)


def _required_ratio(draw_type: str, position: str) -> float:
    pos = 'ip' if position.lower() == 'ip' else 'oop'
    return REQUIRED_STACK_CALL_RATIO.get(draw_type, {}).get(pos, 6.0)


def _adjusted_implied_odds(
    base_stack: float,
    call_bb: float,
    position: str,
    villain_type: str,
) -> float:
    pos_mult = POSITION_MULTIPLIER.get(position, 1.00)
    vil_mult = VILLAIN_PAYOFF_MULTIPLIER.get(villain_type, 1.00)
    effective_stack = base_stack * pos_mult * vil_mult
    return round(effective_stack / call_bb, 2)


def _draw_profitable(
    adjusted_io: float,
    required_ratio: float,
) -> bool:
    return adjusted_io >= required_ratio


@dataclass
class ImpliedOddsPositionalResult:
    draw_type: str
    position: str
    villain_type: str

    effective_stack_bb: float
    call_bb: float

    raw_stack_call_ratio: float
    adjusted_implied_odds: float
    required_ratio: float
    is_profitable: bool

    position_premium_pct: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_implied_odds_positional(
    draw_type: str = 'flush_draw',
    position: str = 'ip',
    villain_type: str = 'rec',
    effective_stack_bb: float = 80.0,
    call_bb: float = 8.0,
    pot_bb: float = 16.0,
) -> ImpliedOddsPositionalResult:
    """
    Analyze whether a draw is profitable accounting for position.

    Args:
        draw_type:          'flush_draw','oesd','combo_draw','gutshot','backdoor'
        position:           'ip' or 'oop'
        villain_type:       Villain type ('fish','rec','nit','lag','reg')
        effective_stack_bb: Effective stack remaining after call (BB behind)
        call_bb:            Cost to call in BB
        pot_bb:             Current pot in BB

    Returns:
        ImpliedOddsPositionalResult
    """
    raw_ratio = round(effective_stack_bb / call_bb, 2)
    adj_io = _adjusted_implied_odds(effective_stack_bb, call_bb, position, villain_type)
    req_ratio = _required_ratio(draw_type, position)
    profitable = _draw_profitable(adj_io, req_ratio)

    pos_mult = POSITION_MULTIPLIER.get(position, 1.0)
    premium_pct = round((pos_mult - 1.0) * 100.0, 1)

    verdict = (
        f'[IOP {draw_type}|{position.upper()}|{villain_type}] '
        f'{"CALL" if profitable else "FOLD"} '
        f'adj_io={adj_io:.1f}x req={req_ratio:.1f}x '
        f'pos_premium={premium_pct:+.0f}%'
    )

    reasoning = (
        f'Implied odds with position: {draw_type} from {position.upper()} vs {villain_type}. '
        f'Stack={effective_stack_bb:.0f}BB call={call_bb:.0f}BB. '
        f'Raw ratio={raw_ratio:.1f}x; adjusted={adj_io:.1f}x (pos×{pos_mult:.2f}). '
        f'Required={req_ratio:.1f}x. Profitable={profitable}.'
    )

    tips = []

    tips.append(
        f'IMPLIED ODDS ({position.upper()}): Raw {raw_ratio:.1f}x stack:call. '
        f'Position-adjusted: {adj_io:.1f}x. Required for {draw_type}: {req_ratio:.1f}x. '
        f'{"CALL -- profitable with position." if profitable else "FOLD -- insufficient implied odds."}'
    )

    if position == 'ip':
        tips.append(
            f'IP PREMIUM (+{premium_pct:.0f}%%): Draws worth significantly more in position. '
            f'You control action on next streets, can extract max value when draw hits, '
            f'and check back cheaply when it misses.'
        )
    else:
        tips.append(
            f'OOP DISCOUNT ({premium_pct:.0f}%%): Draws worth less out of position. '
            f'Must act first; villain can bet big on scary cards; harder to extract. '
            f'Need {REQUIRED_STACK_CALL_RATIO[draw_type]["oop"]:.1f}x vs only '
            f'{REQUIRED_STACK_CALL_RATIO[draw_type]["ip"]:.1f}x IP.'
        )

    if villain_type in ('fish', 'calling_station'):
        tips.append(
            f'VS {villain_type.upper()}: Payoff multiplier {VILLAIN_PAYOFF_MULTIPLIER[villain_type]:.2f}x. '
            f'They pay off when you hit -- implied odds excellent. '
            f'Call wider; they will pay you off on the river.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT: Payoff multiplier {VILLAIN_PAYOFF_MULTIPLIER["nit"]:.2f}x. '
            f'Nit folds to river bets -- implied odds much lower. '
            f'Need larger raw ratio to compensate for poor payoff.'
        )

    return ImpliedOddsPositionalResult(
        draw_type=draw_type,
        position=position,
        villain_type=villain_type,
        effective_stack_bb=effective_stack_bb,
        call_bb=call_bb,
        raw_stack_call_ratio=raw_ratio,
        adjusted_implied_odds=adj_io,
        required_ratio=req_ratio,
        is_profitable=profitable,
        position_premium_pct=premium_pct,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def iop_one_liner(r: ImpliedOddsPositionalResult) -> str:
    return (
        f'[IOP {r.draw_type}|{r.position.upper()}] '
        f'{"CALL" if r.is_profitable else "FOLD"} '
        f'adj={r.adjusted_implied_odds:.1f}x req={r.required_ratio:.1f}x '
        f'pos={r.position_premium_pct:+.0f}%'
    )
