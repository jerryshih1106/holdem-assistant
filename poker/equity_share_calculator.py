"""
Equity Share Calculator (equity_share_calculator.py)

Calculates what fraction of the pot each player "deserves" based on
equity, helping evaluate:
  1. Whether pot odds justify a call
  2. How much a check-raise should target (based on equity ownership)
  3. Whether hero is over/under-repping equity in a pot
  4. The "fair" price to pay for draws

EQUITY SHARE CONCEPT:
  If hero has 35% equity in a $100 pot, hero "owns" $35 of that pot.
  If villain bets $50 (total pot = $150), hero needs 35% > $50/$150 = 33.3%
  to have a +EV call (pot odds).

  EQUITY SHARE vs POT ODDS:
    Pot odds: minimum equity to break even calling
    Equity share: how much of the current pot hero "deserves"
    Fair call size: if hero's equity share < villain's bet, calling is poor

  EQUITY PERCENTAGE vs EQUITY SHARE:
    Equity %: probability of winning the pot (e.g. 35%)
    Equity share (in BB): equity_pct * pot_size (e.g. 35% * $100 = $35)

DISTINCT FROM:
  pot_odds_advisor.py:     Basic pot odds calculation
  kelly_bet_sizer.py:      Optimal bet sizing via Kelly criterion
  THIS MODULE:             Equity OWNERSHIP perspective -- how much of each
                           pot/bet "belongs" to hero; multi-way equity
                           allocation; surplus/deficit from pot odds vs equity

Usage:
    from poker.equity_share_calculator import calculate_equity_share, EquityShareResult, eqs_one_liner

    result = calculate_equity_share(
        hero_equity=0.35,
        pot_bb=40.0,
        villain_bet_bb=20.0,
        hero_call_bb=20.0,
        street='flop',
        num_players=2,
        hero_hand_category='flush_draw',
    )
    print(eqs_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


def _pot_odds_required(villain_bet_bb: float, pot_bb: float) -> float:
    """Minimum equity to justify a call: bet / (pot + bet + call)."""
    total = pot_bb + villain_bet_bb + villain_bet_bb
    if total <= 0:
        return 0.0
    return round(villain_bet_bb / total, 4)


def _equity_share_bb(hero_equity: float, pot_bb: float) -> float:
    """How many BBs of the current pot hero owns."""
    return round(hero_equity * pot_bb, 2)


def _equity_share_after_call(
    hero_equity: float, pot_bb: float, villain_bet_bb: float
) -> float:
    """Hero's equity share in the pot after calling villain's bet."""
    new_pot = pot_bb + villain_bet_bb + villain_bet_bb
    return round(hero_equity * new_pot, 2)


def _call_surplus(
    hero_equity: float,
    pot_bb: float,
    villain_bet_bb: float,
) -> float:
    """
    Call surplus = equity_share_after_call - cost_of_call.
    Positive = calling is +EV; negative = -EV (pure calling, no implicit odds).
    """
    share_after = _equity_share_after_call(hero_equity, pot_bb, villain_bet_bb)
    return round(share_after - villain_bet_bb, 2)


def _implied_odds_needed(
    hero_equity: float,
    pot_bb: float,
    villain_bet_bb: float,
    hero_stack_bb: float,
) -> float:
    """
    How much additional EV from future streets is needed to break even.
    Returns 0.0 if call is already +EV on pure equity.
    """
    surplus = _call_surplus(hero_equity, pot_bb, villain_bet_bb)
    if surplus >= 0:
        return 0.0
    return round(abs(surplus), 2)


def _multiway_equity_share(hero_equity: float, pot_bb: float, num_players: int) -> float:
    """Hero's equity share in a multiway pot (normalized by player count)."""
    if num_players <= 1:
        return pot_bb
    # In multiway pots, equity is already factored in (hero might have 20% vs 3 villains)
    return _equity_share_bb(hero_equity, pot_bb)


def _call_decision(
    hero_equity: float,
    pot_odds_required: float,
    call_surplus: float,
    implied_odds_needed: float,
    hero_hand_category: str,
    street: str,
) -> tuple:
    """(decision: str, explanation: str)"""
    has_draws = hero_hand_category in (
        'flush_draw', 'straight_draw', 'draw', 'combo_draw',
        'gutshot', 'oesd', 'backdoor_flush_draw',
    )

    if call_surplus >= 0:
        return (
            'call',
            f'Direct call: equity {hero_equity:.0%} > pot odds {pot_odds_required:.0%}. '
            f'Surplus={call_surplus:.1f}BB is immediate +EV.',
        )
    elif implied_odds_needed <= 5.0 and has_draws and street != 'river':
        return (
            'call_implied',
            f'Implied odds call: need {implied_odds_needed:.1f}BB more from future streets. '
            f'Draw hand on {street} can realize this if villain stacks off when draw completes.',
        )
    elif implied_odds_needed <= 2.0 and street != 'river':
        return (
            'call_marginal',
            f'Marginal call: need {implied_odds_needed:.1f}BB from future streets. '
            f'Borderline; OK to call with position or if villain is sticky.',
        )
    else:
        return (
            'fold',
            f'Fold: equity {hero_equity:.0%} < pot odds {pot_odds_required:.0%}. '
            f'Need {implied_odds_needed:.1f}BB implied odds to break even.',
        )


@dataclass
class EquityShareResult:
    # Inputs
    hero_equity: float
    pot_bb: float
    villain_bet_bb: float
    hero_call_bb: float
    street: str
    num_players: int
    hero_hand_category: str

    # Equity analysis
    equity_share_now_bb: float        # hero's share of current pot
    equity_share_after_call_bb: float # hero's share after calling
    pot_odds_required: float          # break-even equity for calling
    call_surplus_bb: float            # equity_share_after_call - cost (>0 = +EV)
    implied_odds_needed_bb: float     # how much more EV needed from future streets

    # Decision
    call_decision: str                # 'call' / 'call_implied' / 'call_marginal' / 'fold'
    call_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calculate_equity_share(
    hero_equity: float = 0.35,
    pot_bb: float = 40.0,
    villain_bet_bb: float = 20.0,
    hero_call_bb: float = 20.0,
    street: str = 'flop',
    num_players: int = 2,
    hero_hand_category: str = 'flush_draw',
    hero_stack_bb: float = 80.0,
) -> EquityShareResult:
    """
    Calculate equity share in the pot and inform call/fold decision.

    Args:
        hero_equity:        Hero's equity fraction (0-1)
        pot_bb:             Current pot size in BBs (before villain's bet)
        villain_bet_bb:     Villain's bet size in BBs
        hero_call_bb:       Amount hero would need to call (usually = villain_bet_bb for HU)
        street:             'preflop' / 'flop' / 'turn' / 'river'
        num_players:        Total players in hand
        hero_hand_category: Hero's current hand category
        hero_stack_bb:      Hero's remaining stack after call

    Returns:
        EquityShareResult
    """
    share_now = _equity_share_bb(hero_equity, pot_bb)
    share_after = _equity_share_after_call(hero_equity, pot_bb, villain_bet_bb)
    pot_odds = _pot_odds_required(villain_bet_bb, pot_bb)
    surplus = _call_surplus(hero_equity, pot_bb, villain_bet_bb)
    implied_needed = _implied_odds_needed(hero_equity, pot_bb, villain_bet_bb, hero_stack_bb)

    decision, explanation = _call_decision(
        hero_equity, pot_odds, surplus, implied_needed, hero_hand_category, street
    )

    reasoning = (
        f'Hero equity={hero_equity:.0%} in pot={pot_bb:.1f}BB. '
        f'Villain bet={villain_bet_bb:.1f}BB. '
        f'Equity share now={share_now:.1f}BB; after call={share_after:.1f}BB. '
        f'Pot odds required={pot_odds:.0%}. '
        f'Call surplus={surplus:+.1f}BB. '
        f'Implied odds needed={implied_needed:.1f}BB. '
        f'Decision={decision}.'
    )

    verdict = (
        f'[EQS {hero_hand_category}|{street}|{decision.upper()}] '
        f'equity={hero_equity:.0%} share={share_now:.1f}BB | '
        f'pot_odds={pot_odds:.0%} surplus={surplus:+.1f}BB'
    )

    tips = [explanation]

    tips.append(
        f'EQUITY SHARE BREAKDOWN: '
        f'Hero owns {share_now:.1f}BB of current {pot_bb:.1f}BB pot ({hero_equity:.0%} equity). '
        f'After calling {villain_bet_bb:.1f}BB, total pot={pot_bb + 2*villain_bet_bb:.1f}BB, '
        f'hero owns {share_after:.1f}BB. '
        f'Net equity gain from call: {share_after - villain_bet_bb:.1f}BB vs cost {villain_bet_bb:.1f}BB.'
    )

    if decision == 'call':
        tips.append(
            f'CLEAR CALL: Your {hero_equity:.0%} equity exceeds the {pot_odds:.0%} required. '
            f'You gain {surplus:.1f}BB in equity with each call. '
            f'Do not over-think this; call/raise for value.'
        )
    elif decision == 'call_implied':
        tips.append(
            f'IMPLIED ODDS REQUIRED: Need {implied_needed:.1f}BB more from future streets. '
            f'Check: (1) Will villain stack off if draw completes? '
            f'(2) Do you have position to control pot size? '
            f'(3) Stack sizes -- need villain to have >={implied_needed:.0f}BB remaining.'
        )
    elif decision == 'fold':
        if implied_needed > 10.0:
            tips.append(
                f'FOLD: Gap between equity ({hero_equity:.0%}) and required ({pot_odds:.0%}) is '
                f'too large ({implied_needed:.1f}BB needed from future streets). '
                f'Losing call even with position and sticky villain.'
            )
        else:
            tips.append(
                f'MARGINAL FOLD: Close spot. Need {implied_needed:.1f}BB implied odds. '
                f'Consider position, villain tendencies, and stack depth before folding.'
            )

    if num_players >= 3:
        tips.append(
            f'MULTIWAY POT ({num_players} players): Your {hero_equity:.0%} equity includes '
            f'winning vs ALL opponents. Multiway equity is typically lower than HU equity. '
            f'Be more conservative -- need higher equity to call in multiway situations.'
        )

    if villain_bet_bb > pot_bb:
        overbet_pct = villain_bet_bb / pot_bb
        tips.append(
            f'OVERBET ALERT ({overbet_pct:.0%} pot): Large bets polarize villain\'s range. '
            f'Call only with strong hands or strong draws. '
            f'Marginal hands (one-pair, weak draws) should typically fold vs overbets.'
        )

    if street == 'river' and decision in ('call_implied', 'call_marginal'):
        tips.append(
            f'RIVER SPOT: No more implied odds on river -- decision is purely based on '
            f'pot odds vs showdown equity. '
            f'Equity={hero_equity:.0%} < required {pot_odds:.0%}: fold unless equity is correct.'
        )

    return EquityShareResult(
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        villain_bet_bb=villain_bet_bb,
        hero_call_bb=hero_call_bb,
        street=street,
        num_players=num_players,
        hero_hand_category=hero_hand_category,
        equity_share_now_bb=share_now,
        equity_share_after_call_bb=share_after,
        pot_odds_required=pot_odds,
        call_surplus_bb=surplus,
        implied_odds_needed_bb=implied_needed,
        call_decision=decision,
        call_explanation=explanation,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def eqs_one_liner(r: EquityShareResult) -> str:
    return (
        f'[EQS {r.hero_hand_category}|{r.street}|{r.call_decision.upper()}] '
        f'equity={r.hero_equity:.0%} share={r.equity_share_now_bb:.1f}BB | '
        f'pot_odds={r.pot_odds_required:.0%} surplus={r.call_surplus_bb:+.1f}BB'
    )
