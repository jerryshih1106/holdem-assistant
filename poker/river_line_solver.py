"""
River Line Solver (river_line_solver.py)

Given the full hand history line (preflop action, flop action, turn action),
computes the optimal river action based on remaining ranges, pot odds,
and equity vs villain's perceived range.

THEORY:
  By the river, the hand history constrains both players' ranges significantly.
  A villain who:
    - Called a flop cbet AND called a turn barrel is unlikely to have air.
    - Checked both streets is unlikely to have the nuts.
    - Led the turn has a polarized range.
  We use these constraints to estimate villain's river range,
  compute hero's equity vs that range, and determine the optimal river action.

KEY CALCULATIONS:
  1. Villain range tightness from action history
  2. Hero equity vs narrowed villain range
  3. Pot odds for calling a villain bet
  4. Bet/check/fold decision for hero (IP or OOP)
  5. Value bet sizing recommendation

HAND HISTORY ACTIONS:
  Each action is a string: 'c' = check, 'b' = bet, 'r' = raise, 'f' = fold, 'x' = check-behind

  Line format: separate the streets with '/'
  Example: "rr/cb/cb" means preflop 3-bet, flop cbet called, turn cbet called

VILLAIN RANGE ESTIMATION:
  Double barrel caller: weighted toward pairs, draws. Excludes air.
  Single barrel caller: wide: has draws, pairs, some bluff catchers.
  Check-checker (villain): very wide; anything that didn't want to bet for value.
  Villain led turn: polarized (strong/bluffs).
  Villain raised: capped to very strong or bluff-raise hands.

RIVER DECISION LOGIC:
  Hero IP (check behind or bet):
    - If equity >= 65%: value bet (2/3 pot)
    - If equity >= 50%: thin value bet or check-behind depending on blocker advantage
    - If equity < 50%: check behind (realize equity)
  Hero OOP (lead or check-call/check-fold):
    - equity >= 60%: donk lead (50% pot)
    - equity >= 45%: check-call vs villain bet up to 50% pot
    - equity < 35%: check-fold vs any bet
  Facing villain bet (either position):
    - check_call threshold: pot_odds_required (call_amount / (pot + call_amount))
    - Bluff-catch if equity >= threshold + 0.05 (margin for villain having bluffs)

DISTINCT FROM:
  river_bluff_catcher.py:   Only handles catching bluffs on river
  river_value_sizing.py:    Only handles sizing optimal river value bet
  river_check_raise.py:     Only handles river check-raise
  THIS MODULE:              Full river line solver — history-aware range
                            narrowing, equity estimation, AND optimal decision.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Villain range tightness from action history
# Format: (flop_action, turn_action) -> range_description, equity_penalty
# equity_penalty applied to hero equity vs villain (positive = villain stronger)

HISTORY_RANGE_MAP = {
    # Villain called flop + called turn: strong range
    ('call', 'call'):     ('paired_or_draw_heavy', -0.10),
    # Villain called flop + checked turn (hero checked): wider range
    ('call', 'check'):    ('wide_bluffcatch', 0.00),
    # Villain folded at some point -- not in this scenario
    # Villain lead turn after flop call: polarized
    ('call', 'lead'):     ('polarized_strong_or_bluff', -0.05),
    # Villain check-check (passive): wide/marginal
    ('check', 'check'):   ('very_wide_marginal', 0.08),
    # Villain check-called flop, bet turn
    ('check', 'lead'):    ('semi_strong_delayed', -0.07),
    # Villain raised flop: very strong
    ('raise', 'call'):    ('strong_two_way', -0.18),
}

# Villain range labels and bluff frequency estimates
VILLAIN_RANGE_BLUFF_FREQ = {
    'paired_or_draw_heavy': 0.15,
    'wide_bluffcatch':      0.30,
    'polarized_strong_or_bluff': 0.40,
    'very_wide_marginal':   0.35,
    'semi_strong_delayed':  0.20,
    'strong_two_way':       0.10,
}

# Hero equity by hand category (river, already know all 5 community cards)
HAND_EQUITY_RIVER = {
    'nuts':           0.99,
    'full_house':     0.95,
    'flush':          0.85,
    'straight':       0.80,
    'set':            0.88,
    'two_pair':       0.65,
    'overpair':       0.62,
    'top_pair':       0.55,
    'top_pair_wk':    0.48,
    'middle_pair':    0.42,
    'low_pair':       0.35,
    'air':            0.05,
}

# Optimal bet sizing for river value bets (fraction of pot)
VALUE_BET_SIZE = {
    'thin':  0.40,  # thin value
    'medium': 0.65,
    'large': 0.85,
    'overbet': 1.20,
}


def _parse_action_line(action_line: str):
    """Parse 'flop_action/turn_action' into (flop, turn) tuple."""
    parts = action_line.split('/')
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    return 'call', 'call'


def _villain_range_from_history(flop_act: str, turn_act: str):
    key = (flop_act, turn_act)
    if key in HISTORY_RANGE_MAP:
        return HISTORY_RANGE_MAP[key]
    return ('wide_bluffcatch', 0.00)


def _hero_equity(
    hand_category: str,
    villain_range: str,
    equity_penalty: float,
) -> float:
    base = HAND_EQUITY_RIVER.get(hand_category, 0.50)
    eq = base + equity_penalty
    # Villain bluff frequency helps hero equity slightly
    bluff_freq = VILLAIN_RANGE_BLUFF_FREQ.get(villain_range, 0.25)
    eq = eq + bluff_freq * 0.05  # bonus for calling down vs bluffs
    return round(min(0.99, max(0.01, eq)), 3)


def _pot_odds_required(call_amount_bb: float, pot_bb: float) -> float:
    return round(call_amount_bb / (pot_bb + call_amount_bb), 3)


def _value_bet_sizing(hero_equity: float) -> str:
    if hero_equity >= 0.85:
        return 'large'
    elif hero_equity >= 0.70:
        return 'medium'
    elif hero_equity >= 0.55:
        return 'thin'
    else:
        return 'none'


def _optimal_river_action(
    hero_equity: float,
    hero_position: str,
    pot_bb: float,
    villain_bet_bb: float,
    hand_category: str,
    villain_bluff_freq: float,
) -> tuple:
    """
    Returns (action, detail) where action is: 'value_bet', 'check_behind',
    'check_call', 'check_fold', 'donk_lead', 'fold'.
    """
    pot_odds = _pot_odds_required(villain_bet_bb, pot_bb) if villain_bet_bb > 0 else 0.0

    # Facing villain bet
    if villain_bet_bb > 0:
        effective_threshold = pot_odds - (villain_bluff_freq * 0.10)
        if hero_equity >= effective_threshold:
            return ('check_call', f'eq={hero_equity:.0%} >= pot_odds={pot_odds:.0%} - bluff_adj; call')
        else:
            return ('check_fold', f'eq={hero_equity:.0%} < pot_odds={pot_odds:.0%}; fold')

    # Hero acts first (no villain bet yet)
    if hero_position == 'ip':
        if hero_equity >= 0.65:
            sz = VALUE_BET_SIZE.get(_value_bet_sizing(hero_equity), 0.65)
            bet_bb = round(pot_bb * sz, 1)
            return ('value_bet', f'eq={hero_equity:.0%} -> bet {sz:.0%} pot = {bet_bb:.1f}BB')
        elif hero_equity >= 0.50:
            sz = VALUE_BET_SIZE['thin']
            bet_bb = round(pot_bb * sz, 1)
            return ('thin_value', f'eq={hero_equity:.0%} -> thin value {sz:.0%} pot = {bet_bb:.1f}BB')
        else:
            return ('check_behind', f'eq={hero_equity:.0%} < 50%; realize equity; check behind')
    else:  # oop
        if hero_equity >= 0.60:
            sz = VALUE_BET_SIZE['thin']  # smaller donk lead OOP
            bet_bb = round(pot_bb * sz, 1)
            return ('donk_lead', f'eq={hero_equity:.0%} -> donk lead {sz:.0%} pot = {bet_bb:.1f}BB OOP')
        elif hero_equity >= 0.45:
            return ('check_call_if_bet', f'eq={hero_equity:.0%}: check/call up to 50% pot bet')
        else:
            return ('check_fold', f'eq={hero_equity:.0%} < 45% OOP; check/fold')


@dataclass
class RiverLineSolution:
    # Inputs
    flop_action: str
    turn_action: str
    hand_category: str
    hero_position: str
    pot_bb: float
    villain_bet_bb: float

    # Analysis
    villain_range: str
    villain_bluff_freq: float
    hero_equity: float
    pot_odds_required: float
    optimal_action: str
    action_detail: str
    value_bet_sizing: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def solve_river_line(
    flop_action: str = 'call',
    turn_action: str = 'call',
    hand_category: str = 'top_pair',
    hero_position: str = 'ip',
    pot_bb: float = 30.0,
    villain_bet_bb: float = 0.0,
    villain_vpip: float = 0.30,
) -> RiverLineSolution:
    """
    Solve the optimal river action given hand history.

    Args:
        flop_action:    Villain's flop action from hero's POV
                        ('call', 'check', 'raise', 'lead')
        turn_action:    Villain's turn action
                        ('call', 'check', 'lead', 'raise')
        hand_category:  Hero's hand on river
        hero_position:  'ip' / 'oop'
        pot_bb:         Pot size in BB before river action
        villain_bet_bb: Villain's bet size if they bet (0 = hero acts first)
        villain_vpip:   Villain's VPIP (affects range width)

    Returns:
        RiverLineSolution
    """
    villain_range, equity_penalty = _villain_range_from_history(flop_action, turn_action)
    villain_bluff_freq = VILLAIN_RANGE_BLUFF_FREQ.get(villain_range, 0.25)

    if villain_vpip >= 0.45:
        villain_bluff_freq = min(0.55, villain_bluff_freq * 1.25)
    elif villain_vpip <= 0.15:
        villain_bluff_freq = max(0.05, villain_bluff_freq * 0.70)

    hero_eq = _hero_equity(hand_category, villain_range, equity_penalty)
    pot_odds = _pot_odds_required(villain_bet_bb, pot_bb) if villain_bet_bb > 0 else 0.0
    optimal_action, action_detail = _optimal_river_action(
        hero_eq, hero_position, pot_bb, villain_bet_bb, hand_category, villain_bluff_freq
    )
    value_sz = _value_bet_sizing(hero_eq)

    verdict = (
        f'[RLS {hand_category}|river|{hero_position}] '
        f'{optimal_action.upper()} | eq={hero_eq:.0%} | {villain_range}'
    )

    reasoning = (
        f'River line: villain flop={flop_action}/turn={turn_action}. '
        f'Villain range: {villain_range} (bluff_freq={villain_bluff_freq:.0%}). '
        f'Hero equity: {hero_eq:.0%}. '
        f'Action: {optimal_action} -- {action_detail}.'
    )

    tips = []
    tips.append(
        f'VILLAIN RANGE: {flop_action}/{turn_action} line -> {villain_range}. '
        f'Estimated bluff frequency: {villain_bluff_freq:.0%}. '
        f'Equity penalty from range: {equity_penalty:+.2f}.'
    )

    tips.append(
        f'HERO EQUITY: {hand_category} vs {villain_range} = {hero_eq:.0%}. '
        f'{"Favorable -- bet value." if hero_eq >= 0.55 else "Marginal -- pot control."}'
    )

    if villain_bet_bb > 0:
        tips.append(
            f'FACING BET: Villain bet {villain_bet_bb:.1f}BB into {pot_bb:.1f}BB. '
            f'Pot odds required: {pot_odds:.0%}. '
            f'Hero equity: {hero_eq:.0%}. '
            f'{"CALL -- equity > pot odds." if optimal_action == "check_call" else "FOLD -- equity < pot odds."}'
        )
    else:
        if hero_eq >= 0.65:
            sz_frac = VALUE_BET_SIZE.get(value_sz, 0.65)
            tips.append(
                f'VALUE BET: {hand_category} has {hero_eq:.0%} equity. '
                f'Recommended size: {value_sz} ({sz_frac:.0%} pot = {pot_bb*sz_frac:.1f}BB). '
                f'Get max value on river.'
            )
        elif hero_eq >= 0.50:
            tips.append(
                f'THIN VALUE / CHECK: {hero_eq:.0%} equity is marginal. '
                f'Thin value if villain calls with worse; check-behind if risk of raise. '
                f'Villain bluff freq={villain_bluff_freq:.0%} -- {"thin bet OK" if villain_bluff_freq >= 0.25 else "prefer check"}.'
            )
        else:
            tips.append(
                f'CHECK BEHIND / GIVE UP: {hero_eq:.0%} equity is too low for value bet. '
                f'Check behind to realize equity and see showdown. '
                f'Avoid bet-folding on river with {hand_category}.'
            )

    return RiverLineSolution(
        flop_action=flop_action,
        turn_action=turn_action,
        hand_category=hand_category,
        hero_position=hero_position,
        pot_bb=pot_bb,
        villain_bet_bb=villain_bet_bb,
        villain_range=villain_range,
        villain_bluff_freq=villain_bluff_freq,
        hero_equity=hero_eq,
        pot_odds_required=pot_odds,
        optimal_action=optimal_action,
        action_detail=action_detail,
        value_bet_sizing=value_sz,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rls_one_liner(r: RiverLineSolution) -> str:
    return (
        f'[RLS {r.hand_category}|{r.hero_position}] '
        f'{r.optimal_action.upper()} | eq={r.hero_equity:.0%} | {r.villain_range}'
    )
