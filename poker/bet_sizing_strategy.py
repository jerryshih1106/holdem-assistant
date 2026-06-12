"""
Bet Sizing Strategy Advisor (bet_sizing_strategy.py)

GTO theory distinguishes THREE bet-sizing approaches:

1. RANGE BET (small, 25-40%pot):
   Use when your ENTIRE range continues to bet on this board.
   - PFR has overwhelming range advantage (AKQ-high dry after 3-bet)
   - All your hands have enough equity to fire
   - Opponent's range is too weak to profitably raise
   - Best on: A/K-high dry boards in 3-bet pots (IP 3-bettor)
   - Effect: forces villain to play for equity correctly, maximizes frequency

2. MERGED BET (medium, 40-60%pot):
   Use when betting most strong/medium hands but checking weak ones.
   - "Thick" value range with many medium-strong hands
   - Not heavily polarized between nuts and air
   - Best on: wet boards where draws and pairs both bet; flop in single-raised pot
   - Effect: villain cannot know your exact strength from the sizing

3. POLARIZED BET (large, 67-120%pot):
   Use when betting only NUTS + BLUFFS, checking everything in between.
   - Betting range is bimodal: top 20% and bottom 20%
   - Middle hands (top pair, overpair) CHECK for pot control
   - Best on: rivers (pure polarized); very dry boards vs range-disadvantaged villain
   - Effect: maximizes EV of nuts, maximizes fold equity of bluffs
   - RULE: bluff-to-value ratio must match bet_size/(pot+bet_size) = alpha

HAND SIZING BUCKETS:
  Value/nuts:     always go big (polarized) or bet merged for thin value
  Strong hands:   merged if betting, or check if trapping
  Medium hands:   merged-small or check (pot control)
  Draws:          merged if semi-bluffing, or check to realize equity
  Air/weak:       polarized-large if bluffing, otherwise check-fold

BOARD-SPECIFIC RECOMMENDATIONS:
  A-high dry (IP after 3-bet):  RANGE BET 25-33%pot entire range
  Low monotone (963sss):        POLARIZED: nuts bet 90%pot, mediums check
  Paired board (TT4):           MERGED 40-50%pot (pairs = medium value)
  Wet connected (J♥T♥9♦):      MERGED-SMALL 33-45%pot; avoid range bet

SOLVER INSIGHTS:
  - On boards where both players have many draws: smaller sizes are better
  - On boards where PFR has huge nut advantage: larger polarized sizes work
  - River: always use polarized or pure value - never merged on river
  - Turn: transition from range bet → merged/polarized as ranges narrow

ALPHA REQUIREMENT FOR POLARIZED BETS:
  bluff-to-value ratio >= alpha = bet / (pot + bet)
  e.g., 75%pot bet → alpha=0.43 → need 43 bluffs per 57 value combos
  e.g., PSB → alpha=0.50 → need 50 bluffs per 50 value combos

Usage:
    from poker.bet_sizing_strategy import advise_bet_sizing_strategy
    from poker.bet_sizing_strategy import BetSizingStrategy, sizing_strategy_one_liner

    strategy = advise_bet_sizing_strategy(
        board_type='dry',
        street='flop',
        hero_pos='IP',
        hero_hand_class='top_pair',
        pot_bb=12.0,
        spr=8.0,
        villain_vpip=0.28,
        villain_wtsd=0.25,
        pot_type='single_raised',
    )
    print(strategy.sizing_strategy)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ── Sizing bucket definitions ─────────────────────────────────────────────────

# (board_type, street, pot_type, hero_pos) → (strategy, small_size, large_size)
_SIZING_STRATEGY_TABLE = {
    # (board_type, street, pot_type, hero_pos): (strategy, small%, large%, notes)
    ('dry',    'flop',  'single_raised', 'IP'):  ('range_bet',  0.33, 0.33, 'Range advantage: bet entire range small'),
    ('dry',    'flop',  '3bet',          'IP'):  ('range_bet',  0.25, 0.33, '3-bet pot dry: range bet 25% entire range'),
    ('dry',    'flop',  'single_raised', 'OOP'): ('merged',     0.45, 0.55, 'OOP: merged betting, not range'),
    ('dry',    'flop',  '3bet',          'OOP'): ('merged',     0.40, 0.55, 'OOP 3bet dry: merged, smaller'),
    ('dry',    'turn',  'single_raised', 'IP'):  ('polarized',  0.55, 0.90, 'Turn: transition to polarized'),
    ('dry',    'turn',  'single_raised', 'OOP'): ('merged',     0.50, 0.65, 'OOP turn: merged, pot control'),
    ('dry',    'river', 'single_raised', 'IP'):  ('polarized',  0.70, 1.10, 'River: fully polarized'),
    ('dry',    'river', 'single_raised', 'OOP'): ('polarized',  0.65, 1.00, 'River OOP: polarized, smaller'),
    ('medium', 'flop',  'single_raised', 'IP'):  ('merged',     0.45, 0.60, 'Medium board: merged betting'),
    ('medium', 'flop',  '3bet',          'IP'):  ('merged',     0.40, 0.55, '3bet medium: merged-small'),
    ('medium', 'flop',  'single_raised', 'OOP'): ('merged',     0.40, 0.55, 'OOP medium: smaller merged'),
    ('medium', 'flop',  '3bet',          'OOP'): ('merged',     0.35, 0.50, 'OOP 3bet medium: small merged'),
    ('medium', 'turn',  'single_raised', 'IP'):  ('polarized',  0.60, 0.85, 'Medium turn: polarizing'),
    ('medium', 'turn',  'single_raised', 'OOP'): ('merged',     0.50, 0.65, 'OOP medium turn: merged'),
    ('medium', 'river', 'single_raised', 'IP'):  ('polarized',  0.75, 1.15, 'River: polarized'),
    ('medium', 'river', 'single_raised', 'OOP'): ('polarized',  0.65, 1.00, 'River OOP: polarized'),
    ('wet',    'flop',  'single_raised', 'IP'):  ('merged',     0.40, 0.55, 'Wet board: draws favor smaller merged'),
    ('wet',    'flop',  '3bet',          'IP'):  ('merged',     0.35, 0.50, '3bet wet: merged-small'),
    ('wet',    'flop',  'single_raised', 'OOP'): ('merged',     0.35, 0.50, 'OOP wet: smaller'),
    ('wet',    'flop',  '3bet',          'OOP'): ('merged',     0.30, 0.45, 'OOP 3bet wet: very small'),
    ('wet',    'turn',  'single_raised', 'IP'):  ('merged',     0.50, 0.70, 'Wet turn: still merged, draws present'),
    ('wet',    'turn',  'single_raised', 'OOP'): ('merged',     0.45, 0.60, 'OOP wet turn: merged'),
    ('wet',    'river', 'single_raised', 'IP'):  ('polarized',  0.70, 1.00, 'Wet river: polarized'),
    ('wet',    'river', 'single_raised', 'OOP'): ('polarized',  0.65, 0.90, 'Wet river OOP: polarized'),
    ('paired', 'flop',  'single_raised', 'IP'):  ('merged',     0.30, 0.45, 'Paired board: small merged (narrow value range)'),
    ('paired', 'flop',  'single_raised', 'OOP'): ('merged',     0.25, 0.40, 'Paired board OOP: small'),
    ('paired', 'river', 'single_raised', 'IP'):  ('polarized',  0.65, 0.90, 'Paired river: polarized'),
}

_BET_ACTIONS = {'barrel', 'bet_strong', 'delayed_cbet', 'cbet', 'bet'}


def _get_strategy(board_type: str, street: str, pot_type: str, hero_pos: str) -> Tuple[str, float, float, str]:
    key = (board_type, street, pot_type, hero_pos)
    if key in _SIZING_STRATEGY_TABLE:
        return _SIZING_STRATEGY_TABLE[key]
    # Fallback by street
    if street == 'river':
        return ('polarized', 0.70, 1.00, 'River default: polarized')
    if hero_pos == 'OOP':
        return ('merged', 0.40, 0.55, 'OOP default: merged')
    if board_type == 'dry':
        return ('range_bet', 0.33, 0.33, 'Dry default: range bet')
    return ('merged', 0.45, 0.60, 'Default: merged')


# ── Hand-to-bucket assignment ─────────────────────────────────────────────────

_HAND_CAT_MAP = {
    'air': 'air', 'trash': 'air', 'nothing': 'air', 'bottom_pair': 'air', 'marginal': 'air',
    'middle_pair': 'middle_pair', 'second_pair': 'middle_pair',
    'draw': 'draw', 'flush_draw': 'draw', 'straight_draw': 'draw', 'speculative': 'draw',
    'top_pair': 'top_pair', 'tptk': 'top_pair', 'good_tp': 'top_pair', 'medium': 'top_pair',
    'overpair': 'overpair', 'two_pair': 'overpair', 'strong': 'overpair',
    'set': 'premium', 'straight': 'premium', 'flush': 'premium',
    'premium': 'premium', 'full_house': 'premium', 'nuts': 'premium',
}


def _hand_cat(hc: str) -> str:
    return _HAND_CAT_MAP.get(hc.lower(), 'top_pair')


def _hand_rank(cat: str) -> int:
    return {'air': 1, 'middle_pair': 2, 'draw': 3, 'top_pair': 4, 'overpair': 5, 'premium': 6}.get(cat, 4)


def _assign_bucket(
    cat: str, sizing_strategy: str, street: str, spr: float, board_type: str,
) -> Tuple[str, float, str]:
    """
    Returns (bucket_name, recommended_size_pct, reason).
    bucket: 'large_value', 'merged_value', 'small_value', 'large_bluff', 'check', 'fold'
    """
    rank = _hand_rank(cat)

    # River is always polarized
    if street == 'river':
        if rank >= 5:  # overpair+
            return ('large_value', 0.80, 'River value: bet large to maximize EV')
        if rank >= 4:  # top pair
            return ('merged_value', 0.55, 'River thin value: medium sizing')
        if rank == 3:  # draw (missed)
            return ('large_bluff', 0.85, 'Missed draw: bluff with blocker if any')
        if rank == 2:  # middle pair
            return ('check', 0.0, 'Middle pair river: check (SDV, no value bet)')
        return ('check_fold', 0.0, 'Air river: check-fold')

    # Range bet: everything uses same small size
    if sizing_strategy == 'range_bet':
        if rank >= 3:
            return ('range_bet', 0.33, 'Range bet: all equity hands bet same size')
        return ('check', 0.0, 'Weak hand checks even in range bet spot')

    # Merged: medium hands bet, weak check
    if sizing_strategy == 'merged':
        if rank >= 5:  # overpair+
            return ('merged_value', 0.60, 'Strong hand: merged value, stay balanced')
        if rank == 4:  # top pair
            return ('merged_value', 0.50, 'Top pair: standard merged value')
        if rank == 3:  # draw
            return ('merged_semibluff', 0.50, 'Draw: semi-bluff at merged sizing')
        if rank == 2:  # middle pair
            if board_type == 'dry' and spr < 5:
                return ('small_value', 0.33, 'Middle pair dry: thin value small')
            return ('check', 0.0, 'Middle pair: check for SDV')
        return ('check_fold', 0.0, 'Air: check-fold in merged spot')

    # Polarized: only nuts + bluffs bet, medium hands check
    if rank >= 6:  # premium/nuts
        return ('polar_large_value', 0.90, 'Nuts: polar large sizing')
    if rank == 5:  # overpair
        return ('check_or_merged', 0.0 if spr > 4 else 0.55,
                'Overpair: check (trap) or merged small depending on SPR')
    if rank == 4:  # top pair
        return ('check', 0.0, 'Top pair: CHECK in polarized spot (pot control)')
    if rank == 3:  # draw
        if board_type in ('medium', 'wet'):
            return ('polar_bluff', 0.85, 'Draw: semi-bluff at polarized sizing')
        return ('check', 0.0, 'Draw dry board: check to realize equity')
    if rank <= 2:  # air/middle pair
        return ('polar_bluff_or_check_fold', 0.85,
                'Air: bluff at polar sizing (if blockers) or check-fold')

    return ('check', 0.0, 'Default: check')


def _alpha(bet_pct: float) -> float:
    """MDF breakeven = bet/(pot+bet)."""
    return round(bet_pct / (1 + bet_pct), 3)


def _bluff_ratio(large_size: float) -> str:
    """Required bluff-to-value ratio for this sizing."""
    a = _alpha(large_size)
    bluffs = round(a * 100)
    values = 100 - bluffs
    return f'{bluffs}/{values} bluff/value combos'


# ── EV impact of correct vs wrong sizing ──────────────────────────────────────

def _ev_impact_of_wrong_size(cat: str, strategy: str, pot_bb: float) -> float:
    """Rough EV loss from using wrong sizing (e.g., merged when should polarize)."""
    base = {'premium': 1.5, 'overpair': 1.0, 'top_pair': 0.7, 'draw': 0.5, 'middle_pair': 0.3, 'air': 0.4}.get(cat, 0.5)
    if strategy == 'range_bet' and cat in ('air', 'middle_pair'):
        return round(base * pot_bb * 0.04, 2)  # range betting weak hands
    return round(base * pot_bb * 0.02, 2)  # minor sizing mistake


@dataclass
class BetSizingStrategy:
    """Bet sizing strategy recommendation."""
    board_type: str
    street: str
    hero_pos: str
    hero_hand_class: str
    pot_bb: float
    spr: float
    villain_vpip: float
    villain_wtsd: float
    pot_type: str

    # Strategy
    hand_category: str
    sizing_strategy: str          # 'range_bet', 'merged', 'polarized'
    strategy_notes: str
    small_size_pct: float         # small end of this strategy
    large_size_pct: float         # large end of this strategy

    # For THIS hand's bucket
    hand_bucket: str              # 'large_value', 'merged_value', etc.
    recommended_size_pct: float   # what size this hand uses
    recommended_size_bb: float
    hand_bucket_reasoning: str

    # Balance info
    alpha: float                  # bet/(pot+bet) for large size
    bluff_to_value: str           # required ratio
    should_mix_sizes: bool        # should some combos of this hand use different sizes?

    # Villain adjustment
    villain_adjustment: str       # 'go_bigger', 'go_smaller', 'no_change'
    villain_note: str

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_bet_sizing_strategy(
    board_type: str = 'medium',
    street: str = 'flop',
    hero_pos: str = 'IP',
    hero_hand_class: str = 'top_pair',
    pot_bb: float = 12.0,
    spr: float = 8.0,
    villain_vpip: float = 0.28,
    villain_wtsd: float = 0.25,
    pot_type: str = 'single_raised',
) -> BetSizingStrategy:
    """
    Advise on the optimal bet sizing strategy for this board/situation.

    Args:
        board_type:       'dry', 'medium', 'wet', 'paired'
        street:           'flop', 'turn', 'river'
        hero_pos:         'IP' or 'OOP'
        hero_hand_class:  Hero's hand strength
        pot_bb:           Current pot in BB
        spr:              Effective stack-to-pot ratio
        villain_vpip:     Villain's VPIP (0-1)
        villain_wtsd:     Villain's WTSD (went-to-showdown rate, 0-1)
        pot_type:         'single_raised' or '3bet'

    Returns:
        BetSizingStrategy
    """
    cat = _hand_cat(hero_hand_class)
    rank = _hand_rank(cat)

    bt = board_type if board_type in ('dry', 'medium', 'wet', 'paired') else 'medium'
    strategy, small_size, large_size, strat_notes = _get_strategy(bt, street, pot_type, hero_pos)
    bucket, rec_size_pct, bucket_reason = _assign_bucket(cat, strategy, street, spr, bt)
    rec_size_bb = round(pot_bb * rec_size_pct, 1) if rec_size_pct > 0 else 0.0

    alpha = _alpha(large_size)
    bluff_ratio = _bluff_ratio(large_size)

    # Villain adjustment
    if villain_wtsd > 0.38:  # calling station
        villain_adj = 'go_bigger'
        villain_note = (
            f'Villain WTSD={villain_wtsd:.0%} (calling station): '
            f'go BIGGER with value hands (calling station calls everything). '
            f'Stop bluffing! Increase value bet by +10-15%pot.'
        )
        if rec_size_pct > 0 and bucket not in ('check', 'check_fold', 'polar_bluff', 'polar_bluff_or_check_fold'):
            rec_size_pct = min(rec_size_pct + 0.12, 1.10)
            rec_size_bb = round(pot_bb * rec_size_pct, 1)
    elif villain_vpip < 0.20 and villain_wtsd < 0.20:  # nit
        villain_adj = 'go_smaller'
        villain_note = (
            f'Villain VPIP={villain_vpip:.0%} WTSD={villain_wtsd:.0%} (nit): '
            f'go SMALLER with value (nit folds to large bets). '
            f'Thin value works better. Also bluff less (nit folds early, not to rivers).'
        )
        if rec_size_pct > 0.40:
            rec_size_pct = max(rec_size_pct - 0.12, 0.33)
            rec_size_bb = round(pot_bb * rec_size_pct, 1)
    else:
        villain_adj = 'no_change'
        villain_note = (
            f'Villain profile (VPIP={villain_vpip:.0%} WTSD={villain_wtsd:.0%}): '
            f'standard sizing applies.'
        )

    # Should this hand mix sizes?
    should_mix = (strategy == 'polarized' and rank == 5)  # overpair in polarized = sometimes check/sometimes bet

    reasoning = (
        f'{hero_hand_class}({cat}) on {bt} board, {street}, {hero_pos}, {pot_type} pot. '
        f'Strategy={strategy} ({small_size:.0%}-{large_size:.0%}pot). '
        f'This hand: bucket={bucket}, size={rec_size_pct:.0%}pot ({rec_size_bb:.1f}BB). '
        f'Alpha(large)={alpha:.0%}. Villain adj={villain_adj}.'
    )

    # Tips
    tips = []
    if strategy == 'range_bet':
        tips.append(
            f'RANGE BET spot ({bt} board, {pot_type}): bet your ENTIRE range at {small_size:.0%}pot. '
            f'No hand is weak enough to check here (you have overwhelming range advantage). '
            f'Same size for nuts AND air — opponent cannot exploit your sizing. '
            f'EV: maximizes fold equity while keeping strong hands unexploitable.'
        )
    if strategy == 'polarized' and street in ('turn', 'river'):
        tips.append(
            f'POLARIZED bet ({large_size:.0%}pot on {street}): '
            f'Bet nuts/bluffs at {large_size:.0%}pot, CHECK medium hands (top pair, overpair). '
            f'Required bluff ratio: {bluff_ratio}. '
            f'Villain cannot profitably call OR fold — perfectly balanced.'
        )
    if bucket in ('check', 'check_fold'):
        tips.append(
            f'{hero_hand_class}: CHECK in this spot. '
            f'Strategy is {strategy} — medium hands check to protect checking range '
            f'and to keep villain from knowing your exact strength from sizing. '
            f'Checking medium hands also makes your BETTING range stronger on average.'
        )
    if villain_adj == 'go_bigger':
        tips.append(
            f'CALLING STATION (WTSD={villain_wtsd:.0%}): size up your value hands. '
            f'They will call {large_size:.0%}pot with any pair. '
            f'Do NOT bluff — they call. '
            f'Value bet thinner (one pair is often good enough with large sizing).'
        )
    if spr < 2.5 and rank >= 4:
        tips.append(
            f'LOW SPR ({spr:.1f}): pot committed with {cat}. '
            f'Bet to commit or check-raise all-in. '
            f'Sizing matters less — focus on getting money in.'
        )
    if street == 'river' and bucket in ('polar_bluff', 'polar_bluff_or_check_fold', 'large_bluff'):
        tips.append(
            f'RIVER BLUFF sizing: always use large sizing ({large_size:.0%}pot) for bluffs. '
            f'Small river bets look like blocking bets (villain calls wide). '
            f'Large bets = pressure. Only bluff with blockers to villain\'s strong hands. '
            f'Required fold rate = {alpha:.0%} (villain must fold more than this for +EV).'
        )
    if not tips:
        tips.append(
            f'Standard {strategy} strategy for {bt} board {street} as {hero_pos}. '
            f'Size: {rec_size_pct:.0%}pot ({rec_size_bb:.1f}BB). '
            f'Villain profile is average; no special adjustment needed.'
        )

    return BetSizingStrategy(
        board_type=bt,
        street=street,
        hero_pos=hero_pos,
        hero_hand_class=hero_hand_class,
        pot_bb=round(pot_bb, 1),
        spr=round(spr, 2),
        villain_vpip=round(villain_vpip, 3),
        villain_wtsd=round(villain_wtsd, 3),
        pot_type=pot_type,
        hand_category=cat,
        sizing_strategy=strategy,
        strategy_notes=strat_notes,
        small_size_pct=small_size,
        large_size_pct=large_size,
        hand_bucket=bucket,
        recommended_size_pct=round(rec_size_pct, 3),
        recommended_size_bb=rec_size_bb,
        hand_bucket_reasoning=bucket_reason,
        alpha=alpha,
        bluff_to_value=bluff_ratio,
        should_mix_sizes=should_mix,
        villain_adjustment=villain_adj,
        villain_note=villain_note,
        reasoning=reasoning,
        tips=tips,
    )


def sizing_strategy_one_liner(r: BetSizingStrategy) -> str:
    bet_info = (
        f'{r.recommended_size_pct:.0%}pot({r.recommended_size_bb:.1f}BB)'
        if r.recommended_size_pct > 0 else 'CHECK'
    )
    return (
        f'[SIZE {r.hero_hand_class}@{r.street}|{r.hero_pos}|{r.board_type}] '
        f'{r.sizing_strategy.upper()} | '
        f'bucket={r.hand_bucket} size={bet_info} | '
        f'alpha={r.alpha:.0%} adj={r.villain_adjustment}'
    )
