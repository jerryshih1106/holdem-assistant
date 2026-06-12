"""
Multiway Equity Allocator (multiway_equity_allocator.py)

Estimates hero's equity in multi-way pots (3-6 players) and adjusts
strategy based on the number of opponents and their likely range composition.

THEORY:
  In multiway pots (3+ players), equity drops significantly:
  - Top pair heads-up: ~65% equity
  - Top pair 3-way: ~45% equity
  - Top pair 4-way: ~35% equity
  - Top pair 5-way: ~28% equity

  This is because each additional opponent has some probability of having
  a better hand. The equity drop is approximately:
    equity_3way = equity_HU^(n-1) adjusted for correlated ranges

  VALUE HANDS SCALE DOWN LINEARLY:
    Sets/two-pair maintain more equity in multiway (less likely all opponents beat a set)
    Top pair loses equity much faster (more likely someone has better top pair or two-pair)

  DRAWING HANDS RETAIN MORE VALUE MULTIWAY:
    Implied odds increase with more opponents
    Flush draws/straights win multiple stacks when they hit

  STRATEGIC ADJUSTMENTS:
    1. Bet sizing: Larger in multiway to eliminate opponents; smaller if check-calling
    2. C-bet frequency: Drop sharply (each opponent can wake up with something)
    3. Hand threshold to continue: Higher; need stronger hands to commit
    4. Folding to aggression: If raised with multiway pot, range for raises is very strong

EQUITY CALCULATION:
  Using a simplified multiplicative model:
    adj_equity = base_equity * product(1 - P(opponent_beats_hero))
    P(opponent_beats_hero) depends on hand category and number of opponents

MULTIWAY BET SIZING THEORY:
  In multiway pots, larger bets:
  - Protect against draws hitting
  - Build pot faster for value
  - Price out multiple callers (don't want 3 callers on straight draw board)
  Smaller bets in multiway:
  - When polarized (nuts or bluff): can bet small for calls
  - Don't give good pot odds to all opponents

DISTINCT FROM:
  equity_calculator.py:    Raw equity calculation (heads-up focused)
  bayesian_villain_model.py: Range estimation
  preflop_3way_strategy.py:  Preflop 3-way decisions
  THIS MODULE:               POSTFLOP multiway equity with N opponents;
                             equity reduction model; multiway-specific
                             bet sizing and fold thresholds.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Base equity (heads-up) by hand category
BASE_EQUITY_HU: Dict[str, float] = {
    'nuts':          0.99,
    'full_house':    0.97,
    'flush':         0.87,
    'straight':      0.83,
    'set':           0.88,
    'two_pair':      0.75,
    'overpair':      0.70,
    'top_pair':      0.65,
    'top_pair_wk':   0.58,
    'middle_pair':   0.50,
    'low_pair':      0.42,
    'flush_draw':    0.38,
    'combo_draw':    0.52,
    'oesd':          0.35,
    'gutshot':       0.28,
    'air':           0.12,
}

# Per-opponent equity penalty (how much equity is lost per additional opponent)
# Expressed as fraction of base equity retained per opponent
EQUITY_RETENTION_PER_OPP: Dict[str, float] = {
    'nuts':          1.00,   # nuts stays nuts
    'full_house':    0.99,
    'flush':         0.93,
    'straight':      0.91,
    'set':           0.95,
    'two_pair':      0.88,
    'overpair':      0.85,
    'top_pair':      0.82,
    'top_pair_wk':   0.78,
    'middle_pair':   0.74,
    'low_pair':      0.70,
    'flush_draw':    0.98,   # draws actually improve with more opponents (implied odds)
    'combo_draw':    0.97,
    'oesd':          0.97,
    'gutshot':       0.96,
    'air':           0.90,
}

# Multiway cbet frequency (fraction of HU cbet)
MULTIWAY_CBET_REDUCTION: Dict[int, float] = {
    2: 1.00,   # HU: no reduction
    3: 0.58,   # 3-way: 58% of HU cbet frequency
    4: 0.40,   # 4-way
    5: 0.28,   # 5-way
    6: 0.20,   # 6-way
}

# Bet sizing increase for multiway (fraction of pot)
# More opponents = bet bigger to protect
MULTIWAY_BET_SIZE: Dict[int, float] = {
    2: 0.60,
    3: 0.70,
    4: 0.80,
    5: 0.90,
    6: 1.00,
}

# Minimum hand category rank to commit (by n_opponents)
COMMIT_THRESHOLD_BY_OPP: Dict[int, str] = {
    2: 'top_pair',
    3: 'two_pair',
    4: 'set',
    5: 'flush',
    6: 'straight',
}


def _multiway_equity(
    hand_category: str,
    n_opponents: int,
) -> float:
    """Compute equity with n_opponents."""
    base = BASE_EQUITY_HU.get(hand_category, 0.50)
    retention = EQUITY_RETENTION_PER_OPP.get(hand_category, 0.85)
    eq = base * (retention ** max(0, n_opponents - 1))
    return round(min(0.99, max(0.01, eq)), 3)


def _should_continue(
    hand_category: str,
    n_opponents: int,
    hero_equity: float,
    pot_odds: float = 0.0,
) -> bool:
    hand_rank_order = [
        'air', 'gutshot', 'oesd', 'flush_draw', 'low_pair', 'middle_pair',
        'top_pair_wk', 'top_pair', 'combo_draw', 'overpair',
        'two_pair', 'straight', 'flush', 'set', 'full_house', 'nuts',
    ]
    # Good pot odds override the threshold
    if pot_odds > 0 and hero_equity >= pot_odds:
        return True
    threshold_hand = COMMIT_THRESHOLD_BY_OPP.get(n_opponents, 'top_pair')
    hero_rank = hand_rank_order.index(hand_category) if hand_category in hand_rank_order else 7
    thresh_rank = hand_rank_order.index(threshold_hand) if threshold_hand in hand_rank_order else 7
    return hero_rank >= thresh_rank


def _implied_odds_bonus_multiway(
    hand_category: str,
    n_opponents: int,
    pot_bb: float,
    stack_bb: float,
) -> float:
    """Draws gain more implied odds with more opponents (more stacks to win)."""
    if hand_category not in ('flush_draw', 'combo_draw', 'oesd', 'gutshot'):
        return 0.0
    # More opponents = more dead money available
    implied = min(stack_bb, pot_bb * 2) * n_opponents * 0.10
    return round(implied, 2)


@dataclass
class MultiwayEquityResult:
    hand_category: str
    n_opponents: int
    n_total_players: int

    hu_equity: float
    multiway_equity: float
    equity_loss: float

    cbet_frequency: float
    bet_size_frac: float
    bet_size_bb: float
    should_continue: bool
    implied_odds_bonus_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_multiway_equity(
    hand_category: str = 'top_pair',
    n_opponents: int = 2,
    board_texture: str = 'dry',
    hero_position: str = 'ip',
    pot_bb: float = 20.0,
    stack_bb: float = 100.0,
    villain_bet_bb: float = 0.0,
    hero_is_pfr: bool = True,
) -> MultiwayEquityResult:
    """
    Analyze hero's equity and strategy in a multiway pot.

    Args:
        hand_category:  Hero's hand category
        n_opponents:    Number of active opponents (2 = 3-way total)
        board_texture:  Board texture
        hero_position:  'ip' / 'oop'
        pot_bb:         Current pot in BB
        stack_bb:       Effective stack in BB
        villain_bet_bb: Villain's bet size if facing a bet (0 = hero acts first)
        hero_is_pfr:    Is hero the preflop raiser?

    Returns:
        MultiwayEquityResult
    """
    hu_eq = BASE_EQUITY_HU.get(hand_category, 0.50)
    mw_eq = _multiway_equity(hand_category, n_opponents)
    eq_loss = round(hu_eq - mw_eq, 3)

    # Cbet frequency
    hu_cbet = {'dry': 0.62, 'medium': 0.52, 'wet': 0.45, 'paired': 0.55, 'monotone': 0.40}
    base_cbet = hu_cbet.get(board_texture, 0.55) if hero_is_pfr else 0.20
    mw_key = min(6, n_opponents + 1)  # total players = opponents + hero
    cbet_reduction = MULTIWAY_CBET_REDUCTION.get(mw_key, 0.25)
    cbet_freq = round(base_cbet * cbet_reduction, 2)
    if hero_position == 'oop':
        cbet_freq = round(cbet_freq * 0.80, 2)

    bet_frac = MULTIWAY_BET_SIZE.get(mw_key, 0.70)
    bet_bb = round(pot_bb * bet_frac, 1)

    pot_odds = (villain_bet_bb / (pot_bb + villain_bet_bb)) if villain_bet_bb > 0 else 0.0
    cont = _should_continue(hand_category, n_opponents, mw_eq, pot_odds)
    implied_bonus = _implied_odds_bonus_multiway(hand_category, n_opponents, pot_bb, stack_bb)

    total_players = n_opponents + 1
    verdict = (
        f'[MEA {hand_category}|{total_players}-way|{hero_position}] '
        f'{"CONTINUE" if cont else "CONSIDER_FOLD"} | '
        f'eq={mw_eq:.0%} (HU:{hu_eq:.0%},-{eq_loss:.0%}) | '
        f'cbet={cbet_freq:.0%}'
    )

    reasoning = (
        f'{total_players}-way pot. Hand: {hand_category}. '
        f'HU equity: {hu_eq:.0%} -> Multiway ({n_opponents} opponents): {mw_eq:.0%} '
        f'(loss: -{eq_loss:.0%}). '
        f'Cbet recommendation: {cbet_freq:.0%} (base: {base_cbet:.0%} x {cbet_reduction:.0%}). '
        f'Bet size: {bet_frac:.0%} pot = {bet_bb:.1f}BB. '
        f'Continue: {cont}.'
    )

    tips = []

    tips.append(
        f'EQUITY DROP: {hand_category} equity: {hu_eq:.0%} HU -> {mw_eq:.0%} ({total_players}-way). '
        f'Equity loss per opponent: ~{eq_loss:.0%} total ({n_opponents} opps). '
        f'{"Strong enough to continue." if cont else "Equity too low -- consider check/fold."}'
    )

    tips.append(
        f'CBET FREQUENCY: In {total_players}-way pot, cbet {cbet_freq:.0%} '
        f'(reduced from {base_cbet:.0%} HU by factor {cbet_reduction:.0%}). '
        f'More opponents = more likely someone has a piece. '
        f'{"Bet bigger to charge multiple draws." if n_opponents >= 3 else "Standard sizing."}'
    )

    if hand_category in ('flush_draw', 'combo_draw', 'oesd', 'gutshot'):
        tips.append(
            f'DRAW MULTIWAY: {hand_category} implied odds IMPROVE with more opponents. '
            f'Implied bonus: +{implied_bonus:.1f}BB (more stacks to win). '
            f'Semi-bluff against multiway pot is often profitable. '
            f'If hit: value bet vs all remaining opponents.'
        )
    elif n_opponents >= 3 and hand_category in ('top_pair', 'top_pair_wk', 'middle_pair'):
        tips.append(
            f'MARGINAL HAND MULTIWAY: {hand_category} in {total_players}-way = dangerous. '
            f'Equity {mw_eq:.0%} -- someone likely has two-pair or better. '
            f'Consider check/call instead of lead-bet. '
            f'Fold if facing two-streets of pressure from two different players.'
        )
    elif hand_category in ('set', 'flush', 'straight', 'full_house', 'nuts'):
        tips.append(
            f'STRONG HAND MULTIWAY: {hand_category} retains {mw_eq:.0%} equity. '
            f'Build pot fast. Bet {bet_frac:.0%} pot = {bet_bb:.1f}BB. '
            f'Players will call "for value" with worse -- maximize EV.'
        )

    return MultiwayEquityResult(
        hand_category=hand_category,
        n_opponents=n_opponents,
        n_total_players=total_players,
        hu_equity=hu_eq,
        multiway_equity=mw_eq,
        equity_loss=eq_loss,
        cbet_frequency=cbet_freq,
        bet_size_frac=bet_frac,
        bet_size_bb=bet_bb,
        should_continue=cont,
        implied_odds_bonus_bb=implied_bonus,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def mea_one_liner(r: MultiwayEquityResult) -> str:
    return (
        f'[MEA {r.hand_category}|{r.n_total_players}-way] '
        f'eq={r.multiway_equity:.0%} (vs HU:{r.hu_equity:.0%}) | '
        f'cbet={r.cbet_frequency:.0%} | {"CONTINUE" if r.should_continue else "FOLD"}'
    )
