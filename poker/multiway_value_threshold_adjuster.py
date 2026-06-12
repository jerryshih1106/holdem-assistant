"""
Multiway Value Threshold Adjuster (multiway_value_threshold_adjuster.py)

In multiway pots, the value bet threshold rises because MORE opponents can
hold hands that beat you. A hand that is value-bet-worthy heads-up may be
a check/fold in a 4-way pot.

THEORY:
  HU vs MULTIWAY VALUE THRESHOLDS:
  - HU: Value bet any hand with >50% equity vs villain's range
  - 3-way: Need ~57-60% equity (at least one opponent has a playable hand)
  - 4-way: Need ~62-65% equity
  - 5-way: Need ~68-72% equity

  WHY THRESHOLDS RISE:
  - Each opponent has a probability P of holding a better hand
  - Combined probability of at least one opponent beating you = 1 - (1-P)^n
  - As n increases, combined probability grows rapidly

  VALUE BET SIZING IN MULTIWAY:
  - Bet BIGGER when value betting in multiway (wider calling range = more value)
  - Use 65-80% pot (not 50% like HU) -- opponents call with more hands
  - Don't bet thin in multiway -- check marginal hands instead

  CHECK FREQUENCY ADJUSTMENTS:
  - Check more with marginal hands in multiway (middle pair, weak top pair)
  - Bet only strong value (top pair good kicker+ in 3-way; 2-pair+ in 4-way+)
  - Exception: draw boards where protecting matters more

  BLUFF FREQUENCY IN MULTIWAY:
  - Drastically reduce bluffs -- combined fold rate drops exponentially
  - 2 opponents: ~(0.45)^2 = 20% fold-all
  - 3 opponents: ~(0.45)^3 = 9% fold-all
  - Bluffing multiway is almost always -EV

DISTINCT FROM:
  multiway.py:          General multiway pot analysis
  multiway_advisor.py:  Multiway advice
  multiway_call.py:     Calling thresholds in multiway
  THIS MODULE:          VALUE THRESHOLD SPECIFIC; per-opponent equity requirements;
                        sizing adjustments; bluff frequency reduction by N opponents.
"""

from dataclasses import dataclass, field
from typing import List


BASE_VALUE_THRESHOLD_HU: float = 0.52

OPPONENT_EQUITY_ADJUSTMENT: dict = {
    1: 0.000,
    2: 0.070,
    3: 0.140,
    4: 0.200,
    5: 0.250,
}

MULTIWAY_BET_SIZING: dict = {
    1: 0.55,
    2: 0.65,
    3: 0.72,
    4: 0.78,
    5: 0.85,
}

MULTIWAY_BLUFF_FOLD_PCT: dict = {
    1: 0.45,
    2: 0.20,
    3: 0.09,
    4: 0.04,
    5: 0.02,
}

HAND_EQUITY_VS_RANGE: dict = {
    'nuts':           0.92,
    'strong_value':   0.80,
    'top_pair_gk':    0.66,
    'top_pair_wk':    0.55,
    'overpair':       0.72,
    'two_pair':       0.74,
    'middle_pair':    0.44,
    'bottom_pair':    0.30,
    'nut_flush_draw': 0.38,
    'air':            0.18,
}

VILLAIN_FOLD_PCT: dict = {
    'fish':   0.35,
    'rec':    0.42,
    'nit':    0.58,
    'lag':    0.28,
    'reg':    0.48,
}


def _value_threshold(n_opponents: int) -> float:
    adj = OPPONENT_EQUITY_ADJUSTMENT.get(min(n_opponents, 5), 0.25)
    return round(BASE_VALUE_THRESHOLD_HU + adj, 3)


def _combined_fold_pct(opponent_types: List[str]) -> float:
    combined = 1.0
    for vt in opponent_types:
        combined *= VILLAIN_FOLD_PCT.get(vt, 0.42)
    return round(combined, 3)


def _hand_equity(hand_category: str) -> float:
    return HAND_EQUITY_VS_RANGE.get(hand_category, 0.50)


def _multiway_action(
    hero_equity: float,
    threshold: float,
    n_opponents: int,
    combined_fold: float,
    hand_category: str,
) -> str:
    if hero_equity >= threshold + 0.12:
        return 'VALUE_BET_STRONG'
    if hero_equity >= threshold:
        return 'VALUE_BET_MARGINAL'
    if hero_equity >= threshold - 0.10 and n_opponents <= 2:
        return 'CHECK_CALL'
    if hand_category in ('nut_flush_draw',) and combined_fold >= 0.10:
        return 'SEMIBLUFF_DRAW'
    return 'CHECK_FOLD'


def _bluff_ev(pot_bb: float, bet_bb: float, combined_fold: float) -> float:
    return round(combined_fold * pot_bb - (1.0 - combined_fold) * bet_bb, 2)


@dataclass
class MultiwayValueResult:
    n_opponents: int
    hand_category: str
    hero_equity: float

    value_threshold: float
    is_value_bet: bool
    recommended_sizing_frac: float
    combined_fold_pct: float
    bluff_ev: float

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_multiway_value_threshold(
    n_opponents: int = 2,
    hand_category: str = 'top_pair_gk',
    opponent_types: List[str] = None,
    pot_bb: float = 20.0,
    hero_equity: float = None,
) -> MultiwayValueResult:
    """
    Determine value bet threshold and action in multiway pots.

    Args:
        n_opponents:     Number of active opponents (1-5)
        hand_category:   Hand strength category
        opponent_types:  List of opponent types for fold calculation
        pot_bb:          Current pot in BB
        hero_equity:     Override equity (use hand_category lookup if None)

    Returns:
        MultiwayValueResult
    """
    n = max(1, min(5, n_opponents))
    if opponent_types is None:
        opponent_types = ['rec'] * n
    if hero_equity is None:
        hero_equity = _hand_equity(hand_category)

    threshold = _value_threshold(n)
    sizing_frac = MULTIWAY_BET_SIZING.get(n, 0.65)
    bet_bb = round(pot_bb * sizing_frac, 1)
    combined_fold = _combined_fold_pct(opponent_types)
    bluff_ev = _bluff_ev(pot_bb, bet_bb, combined_fold)
    is_value = hero_equity >= threshold
    action = _multiway_action(hero_equity, threshold, n, combined_fold, hand_category)

    verdict = (
        f'[MVT {hand_category}|{n}opp] '
        f'{action} eq={hero_equity:.0%} threshold={threshold:.0%} '
        f'size={sizing_frac:.0%}pot fold={combined_fold:.0%}'
    )

    reasoning = (
        f'Multiway value threshold: {n} opponents. '
        f'Hand={hand_category} equity={hero_equity:.0%} vs threshold={threshold:.0%}. '
        f'Combined fold={combined_fold:.0%}. '
        f'Bet sizing={sizing_frac:.0%}pot ({bet_bb:.1f}BB). '
        f'Bluff EV={bluff_ev:+.1f}BB. Action: {action}.'
    )

    tips = []

    tips.append(
        f'MULTIWAY THRESHOLD: {n}-way pot needs {threshold:.0%} equity to value bet '
        f'(vs {BASE_VALUE_THRESHOLD_HU:.0%} HU). '
        f'Your equity={hero_equity:.0%} -- '
        f'{"VALUE BET -- above threshold." if is_value else "CHECK -- below multiway threshold."}'
    )

    tips.append(
        f'MULTIWAY SIZING: Use {sizing_frac:.0%}pot ({bet_bb:.1f}BB) in {n}-way pot. '
        f'Wider calling field means bigger bets extract more value. '
        f'Do not use HU-sized bets ({MULTIWAY_BET_SIZING[1]:.0%}pot) in multiway.'
    )

    bluff_expected = MULTIWAY_BLUFF_FOLD_PCT.get(n, 0.04)
    tips.append(
        f'BLUFF FREQUENCY: Combined fold rate in {n}-way = {bluff_expected:.0%}. '
        f'{"Almost never bluff -- fold rate too low." if bluff_expected < 0.10 else "Very limited bluffing -- mostly fold with air." if bluff_expected < 0.20 else "Moderate bluffing OK -- consider fold equity."}'
    )

    if n >= 3 and hand_category in ('top_pair_wk', 'middle_pair'):
        tips.append(
            f'{n}-WAY POT: {hand_category} is typically a CHECK-CALL or CHECK-FOLD. '
            f'Not strong enough to value-bet {n} opponents (threshold={threshold:.0%}). '
            f'Check and re-evaluate based on opponents\' actions.'
        )

    return MultiwayValueResult(
        n_opponents=n,
        hand_category=hand_category,
        hero_equity=hero_equity,
        value_threshold=threshold,
        is_value_bet=is_value,
        recommended_sizing_frac=sizing_frac,
        combined_fold_pct=combined_fold,
        bluff_ev=bluff_ev,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def mvt_one_liner(r: MultiwayValueResult) -> str:
    return (
        f'[MVT {r.hand_category}|{r.n_opponents}opp] '
        f'{r.recommended_action} eq={r.hero_equity:.0%} '
        f'threshold={r.value_threshold:.0%} fold={r.combined_fold_pct:.0%}'
    )
