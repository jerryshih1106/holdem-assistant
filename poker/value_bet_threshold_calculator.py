"""
Value Bet Threshold Calculator (value_bet_threshold_calculator.py)

Calculates the minimum equity needed to profitably value bet, given bet size,
pot size, and villain calling frequency. This is the fundamental breakeven
equation for every value bet decision.

VALUE BET THRESHOLD THEORY:
  A value bet is profitable when:
    EV(bet) > EV(check)

  EV(bet) = call_rate * (eq * (pot + 2*bet) - bet) + fold_rate * pot
  EV(check) = eq * pot   (simplified: won when you have equity)

  Solving for break-even equity:
    eq_min = (bet * fold_rate) / (call_rate * (pot + 2*bet))

  This assumes:
  - When bet gets called: you win pot+2*bet at your equity rate
  - When bet folds: you win pot immediately
  - When checking: you win pot at your equity rate

  SIMPLIFIED FORMULA:
    eq_min = bet / (pot + bet + bet * call_rate)
    where call_rate = 1 - fold_rate

  IN PRACTICE:
  - If your equity > eq_min: value bet is profitable
  - The more villain calls, the MORE equity you need (calling range is stronger)
  - The bigger the bet: raises eq_min (riskier) but also raises max EV

  BET SIZING AND THRESHOLD:
  Small bet (25%): eq_min ~30-40% vs wide calling range
  Medium bet (50%): eq_min ~40-50%
  Large bet (75%): eq_min ~45-55%
  Overbet (150%): eq_min ~55-65%

  PRACTICAL EXAMPLES:
  Villain calls 70% (wide range): small bet needs ~35% equity to value bet
  Villain calls 40% (tight range): small bet needs only ~20% equity
  (Tighter calling range = lower threshold because worse hands call)

DISTINCT FROM:
  bet_sizing_ev.py:       Bet sizing EV calculations
  mdf.py:                 Minimum Defense Frequency (for defender)
  call_threshold.py:      Whether to call a bet
  THIS MODULE:            OFFENSIVE side; minimum equity to bet for VALUE;
                          exact threshold by bet size and call rate; which
                          hands are profitable value bets.

Usage:
    from poker.value_bet_threshold_calculator import calc_value_bet_threshold, VBTResult, vbt_one_liner

    result = calc_value_bet_threshold(
        bet_size_pct=0.75,
        pot_bb=30.0,
        villain_call_rate=0.55,
        hero_equity=0.62,
        hero_hand_category='top_pair',
        street='river',
    )
    print(vbt_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# GTO call rates by villain type and bet size (fraction of pot)
GTO_CALL_RATE = {
    0.25: 0.77,   # MDF for 25% bet = 77%
    0.33: 0.75,
    0.50: 0.67,   # MDF for 50% bet = 67%
    0.65: 0.61,
    0.75: 0.57,
    1.00: 0.50,
    1.50: 0.40,
}


def _min_equity_to_value_bet(
    bet_size_pct: float,
    villain_call_rate: float,
) -> float:
    """
    Minimum equity needed so that value bet is better than checking.
    Normalized with pot=1. Condition: EV(bet) > EV(check)
      fold*1 + call*(eq*(1+2*bet) - bet) > eq*1
      fold - call*bet > eq*(1 - call*(1+2*bet))
    Two cases based on sign of denominator = (1 - call*(1+2*bet)):
      denom > 0 (small bets/high fold): eq < numerator/denom; betting always better
      denom < 0 (large bets/low fold): inequality flips; need eq > numerator/denom
    """
    bet = bet_size_pct
    call = villain_call_rate
    fold = 1.0 - call
    numerator = fold - call * bet
    denominator = 1.0 - call * (1 + 2 * bet)
    if abs(denominator) < 1e-9:
        return 0.0
    if denominator > 0:
        # Betting is profitable for any eq < (numerator/denominator).
        # Since that ratio is always >= 1 for realistic params, betting always beats checking.
        return 0.0
    # denominator < 0: need eq >= numerator/denominator (flipped inequality)
    eq_min = numerator / denominator
    return round(min(0.95, max(0.0, eq_min)), 4)


def _nearest_gto_call_rate(bet_size_pct: float) -> float:
    """Find the closest GTO call rate for a given bet size."""
    sizes = list(GTO_CALL_RATE.keys())
    closest = min(sizes, key=lambda x: abs(x - bet_size_pct))
    return GTO_CALL_RATE[closest]


def _is_value_bet_profitable(hero_equity: float, eq_min: float) -> bool:
    return hero_equity >= eq_min


def _ev_of_value_bet(
    bet_size_pct: float,
    villain_call_rate: float,
    hero_equity: float,
    pot_bb: float,
) -> float:
    """EV of value bet in BB."""
    bet_bb = pot_bb * bet_size_pct
    fold_rate = 1.0 - villain_call_rate
    ev_fold = fold_rate * pot_bb
    ev_call = villain_call_rate * (hero_equity * (pot_bb + 2 * bet_bb) - bet_bb)
    return round(ev_fold + ev_call, 2)


def _ev_of_check(hero_equity: float, pot_bb: float) -> float:
    return round(hero_equity * pot_bb, 2)


def _optimal_bet_size(
    hero_equity: float,
    villain_call_rate: float,
    pot_bb: float,
) -> float:
    """Find the bet size that maximizes EV given hero equity and villain call rate."""
    best_ev = _ev_of_check(hero_equity, pot_bb)
    best_size = 0.0
    for size_pct in [0.25, 0.33, 0.50, 0.65, 0.75, 1.00, 1.50]:
        ev = _ev_of_value_bet(size_pct, villain_call_rate, hero_equity, pot_bb)
        if ev > best_ev:
            best_ev = ev
            best_size = size_pct
    return best_size


def _hand_equity_class(hero_equity: float, eq_min: float) -> str:
    gap = hero_equity - eq_min
    if gap >= 0.20:
        return 'clear_value'
    elif gap >= 0.10:
        return 'solid_value'
    elif gap >= 0.0:
        return 'thin_value'
    elif gap >= -0.10:
        return 'marginal_check'
    else:
        return 'clear_check'


@dataclass
class VBTResult:
    # Inputs
    bet_size_pct: float
    pot_bb: float
    villain_call_rate: float
    hero_equity: float
    hero_hand_category: str
    street: str

    # Analysis
    min_equity_threshold: float
    is_profitable: bool
    ev_of_bet: float
    ev_of_check: float
    ev_advantage: float         # bet EV - check EV
    optimal_bet_size: float     # EV-maximizing bet
    equity_class: str           # 'clear_value' / 'thin_value' / 'marginal_check'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calc_value_bet_threshold(
    bet_size_pct: float = 0.75,
    pot_bb: float = 30.0,
    villain_call_rate: float = 0.55,
    hero_equity: float = 0.62,
    hero_hand_category: str = 'top_pair',
    street: str = 'river',
) -> VBTResult:
    """
    Calculate minimum equity for profitable value bet.

    Args:
        bet_size_pct:         Bet as fraction of pot (e.g. 0.75 = 75% pot)
        pot_bb:               Current pot in big blinds
        villain_call_rate:    Probability villain calls (0.0-1.0)
        hero_equity:          Hero's equity (0.0-1.0)
        hero_hand_category:   Hand description
        street:               'flop' / 'turn' / 'river'

    Returns:
        VBTResult
    """
    eq_min = _min_equity_to_value_bet(bet_size_pct, villain_call_rate)
    profitable = _is_value_bet_profitable(hero_equity, eq_min)
    ev_bet = _ev_of_value_bet(bet_size_pct, villain_call_rate, hero_equity, pot_bb)
    ev_check = _ev_of_check(hero_equity, pot_bb)
    ev_adv = round(ev_bet - ev_check, 2)
    optimal = _optimal_bet_size(hero_equity, villain_call_rate, pot_bb)
    eq_class = _hand_equity_class(hero_equity, eq_min)

    bet_bb = pot_bb * bet_size_pct
    action = (
        f'VALUE_BET {bet_size_pct:.0%}pot ({bet_bb:.1f}BB)'
        if profitable
        else 'CHECK (below threshold)'
    )

    verdict = (
        f'[VBT {hero_hand_category}|{street}] {action} | '
        f'eq={hero_equity:.0%} >= min={eq_min:.0%}: {profitable} '
        f'ev_gain={ev_adv:+.1f}BB'
    )

    reasoning = (
        f'Value bet threshold: {hero_hand_category} on {street}. '
        f'Bet size={bet_size_pct:.0%}pot ({bet_bb:.1f}BB). '
        f'Villain call rate={villain_call_rate:.0%}. '
        f'Min equity threshold: {eq_min:.1%}. '
        f'Hero equity: {hero_equity:.1%}. '
        f'Profitable: {profitable} (class={eq_class}). '
        f'EV(bet)={ev_bet:.1f}BB vs EV(check)={ev_check:.1f}BB (gain={ev_adv:+.1f}BB). '
        f'Optimal bet size: {optimal:.0%}pot.'
    )

    tips = []

    tips.append(
        f'THRESHOLD FORMULA: min_eq = f(bet_size={bet_size_pct:.0%}, call_rate={villain_call_rate:.0%}). '
        f'Result: {hero_hand_category} needs >= {eq_min:.0%} equity to value bet {bet_size_pct:.0%}pot. '
        f'Your equity: {hero_equity:.0%}. '
        f'{"PROFITABLE value bet." if profitable else "BELOW THRESHOLD: check is better."}'
    )

    tips.append(
        f'EV COMPARISON: bet={ev_bet:.1f}BB vs check={ev_check:.1f}BB (gain={ev_adv:+.1f}BB). '
        f'Equity class: {eq_class}. '
        f'{"Bet confidently -- clear value." if eq_class == "clear_value" else ""}'
        f'{"Bet carefully -- thin value." if eq_class == "thin_value" else ""}'
        f'{"Lean toward checking." if eq_class == "marginal_check" else ""}'
    )

    if optimal > 0 and optimal != bet_size_pct:
        tips.append(
            f'OPTIMAL BET SIZE: {optimal:.0%}pot (vs your chosen {bet_size_pct:.0%}). '
            f'EV-maximizing bet given {hero_equity:.0%} equity and {villain_call_rate:.0%} call rate. '
            f'{"Size up: your hand has more equity than this bet requires." if optimal > bet_size_pct else "Size down: thinner value; smaller bet is higher EV."}'
        )

    tips.append(
        f'CALL RATE SENSITIVITY: '
        f'Villain calls {villain_call_rate:.0%}. '
        f'If they called {min(1.0, villain_call_rate + 0.20):.0%} (tighter calling): threshold rises to '
        f'{_min_equity_to_value_bet(bet_size_pct, max(0.1, villain_call_rate - 0.20)):.0%}. '
        f'KEY INSIGHT: Tighter calling range = LOWER threshold (they call with better hands = you need more equity). '
        f'Wait -- higher call rate means they call with worse hands = lower eq needed to beat their range.'
    )

    return VBTResult(
        bet_size_pct=bet_size_pct,
        pot_bb=pot_bb,
        villain_call_rate=villain_call_rate,
        hero_equity=hero_equity,
        hero_hand_category=hero_hand_category,
        street=street,
        min_equity_threshold=eq_min,
        is_profitable=profitable,
        ev_of_bet=ev_bet,
        ev_of_check=ev_check,
        ev_advantage=ev_adv,
        optimal_bet_size=optimal,
        equity_class=eq_class,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def vbt_one_liner(r: VBTResult) -> str:
    action = f'VALUE_BET {r.bet_size_pct:.0%}' if r.is_profitable else 'CHECK'
    return (
        f'[VBT {r.hero_hand_category}|{r.street}] '
        f'{action} eq={r.hero_equity:.0%} min={r.min_equity_threshold:.0%} | '
        f'ev_gain={r.ev_advantage:+.1f}BB class={r.equity_class}'
    )
