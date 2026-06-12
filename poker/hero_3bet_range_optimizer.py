"""
Hero 3-Bet Range Optimizer (hero_3bet_range_optimizer.py)

Determines OPTIMAL 3-bet range construction: which hands to 3-bet for value,
which to use as bluffs, sizing, and alpha (break-even fold%) calculation.

THEORY:
  3-BET RANGE = VALUE + BLUFFS (polarized) or MERGED (no bluffs, only value/strong)

  POLARIZED 3-BET:
  - Value hands: AA/KK/QQ/AKs (+ position-dependent extras)
  - Bluff hands: Suited Ax (blockers), suited connectors (equity + can fold to 4-bet)
  - Medium hands: JJ/TT/AQs COLD CALLED (not 3-bet thin)

  MERGED 3-BET (vs fish/calling stations):
  - Wider value range (JJ+, AQ+ 3-bet instead of cold call)
  - Remove bluffs (fish calls too much for bluffs to work)

  ALPHA (break-even fold%) for 3-bet:
  alpha = 3bet_size / (pot_before_3bet + 3bet_size)
  Villain must fold more than alpha for 3-bet bluff to be profitable immediately.

  OPTIMAL BLUFF TO VALUE RATIO:
  For balanced 3-bet range: bluff_combos / value_combos = alpha / (1 - alpha)

  3-BET SIZING:
  IP:  2.5x-3.0x opener  (e.g. 3x 2.5BB = 7.5BB)
  OOP: 3.0x-3.5x opener  (OOP needs larger to discourage postflop calls)

  POSITION-ADJUSTED VALUE THRESHOLD:
  BTN/CO: Can 3-bet wider (JJ+, AQs+ for value)
  EP/MP:  Tighter (QQ+, AKs for value)

DISTINCT FROM:
  threbet_bluff.py:          3-bet bluff analysis
  threebet_sizing.py:        3-bet sizing advice
  threbet_sizing.py:         Duplicate sizing module
  four_bet_range_builder.py: 4-bet range construction
  squeeze_play_advisor.py:   Squeeze 3-bets
  THIS MODULE:               3-BET RANGE CONSTRUCTION; alpha; value vs bluff ratio;
                             position-adjusted value threshold; merged vs polarized choice.
"""

from dataclasses import dataclass, field
from typing import List


VALUE_3BET_HANDS: dict = {
    'btn': frozenset(['AA','KK','QQ','AKs','AKo','JJ','AQs']),
    'co':  frozenset(['AA','KK','QQ','AKs','AKo','JJ','AQs']),
    'mp':  frozenset(['AA','KK','QQ','AKs','AKo','JJ']),
    'utg': frozenset(['AA','KK','QQ','AKs']),
    'sb':  frozenset(['AA','KK','QQ','AKs','AKo','JJ','AQs','TT']),
    'bb':  frozenset(['AA','KK','QQ','AKs','AKo','JJ','AQs']),
}

BLUFF_3BET_HANDS: frozenset = frozenset([
    'A5s','A4s','A3s','A2s',   # Ax blockers + nut flush draws
    'K5s','K4s','K3s',          # Kx blockers
    'JTs','T9s','98s','87s',    # suited connectors (can fold to 4-bet; has equity)
    'QJs',                       # connected blockers
])

VILLAIN_FOLD_VS_3BET: dict = {
    'fish':   0.30,
    'rec':    0.48,
    'nit':    0.65,
    'lag':    0.38,
    'reg':    0.52,
}

VALUE_COMBO_COUNTS: dict = {
    'AA': 6, 'KK': 6, 'QQ': 6, 'JJ': 6, 'TT': 6,
    'AKs': 4, 'AQs': 4, 'AKo': 12, 'AQo': 12,
    'AJs': 4, 'KQs': 4, 'QJs': 4, 'JTs': 4,
    'A5s': 4, 'A4s': 4, 'A3s': 4, 'A2s': 4,
    'K5s': 4, 'K4s': 4, 'K3s': 4,
    'T9s': 4, '98s': 4, '87s': 4,
}


def _3bet_size(open_bb: float, position: str) -> float:
    multiplier = 2.7 if position in ('btn', 'co') else 3.2
    return round(open_bb * multiplier, 1)


def _alpha(threebet_bb: float, pot_before_3bet: float) -> float:
    return round(threebet_bb / (pot_before_3bet + threebet_bb), 3)


def _optimal_bluff_ratio(alpha: float) -> float:
    """Fraction of 3-bet range that should be bluffs for balance."""
    return round(alpha / (1.0 - alpha + 1e-9), 3)


def _is_value_3bet(hero_hand: str, position: str) -> bool:
    value_hands = VALUE_3BET_HANDS.get(position, VALUE_3BET_HANDS['co'])
    return hero_hand in value_hands


def _is_bluff_3bet(hero_hand: str) -> bool:
    return hero_hand in BLUFF_3BET_HANDS


def _3bet_strategy_type(villain_type: str) -> str:
    if villain_type in ('fish', 'calling_station'):
        return 'merged'
    return 'polarized'


def _bluff_3bet_ev(
    threebet_bb: float,
    pot_before: float,
    villain_fold: float,
    hero_equity: float,
    total_pot_if_called: float,
) -> float:
    fold_ev = villain_fold * pot_before
    call_ev = (1.0 - villain_fold) * (hero_equity * total_pot_if_called - threebet_bb)
    return round(fold_ev + call_ev, 2)


@dataclass
class ThreeBetRangeResult:
    hero_hand: str
    position: str
    villain_type: str

    is_value_3bet: bool
    is_bluff_3bet: bool

    threebet_size_bb: float
    alpha_breakeven: float
    bluff_ratio: float
    strategy_type: str

    bluff_3bet_ev_bb: float
    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_3bet_range(
    hero_hand: str = 'A5s',
    position: str = 'btn',
    villain_type: str = 'reg',
    open_bb: float = 2.5,
    pot_before_3bet: float = 3.5,
    villain_fold_to_3bet: float = None,
    hero_equity_if_called: float = 0.40,
) -> ThreeBetRangeResult:
    """
    Analyze 3-bet range construction for a given hand and situation.

    Args:
        hero_hand:              Hero hole cards / hand category
        position:               Hero position ('btn','co','mp','utg','sb','bb')
        villain_type:           Opener's player type ('fish','rec','nit','lag','reg')
        open_bb:                Villain's open size in BB
        pot_before_3bet:        Pot size before hero 3-bets
        villain_fold_to_3bet:   Override villain fold% (None = use table default)
        hero_equity_if_called:  Hero equity when 3-bet is called

    Returns:
        ThreeBetRangeResult
    """
    t3size = _3bet_size(open_bb, position)
    alpha = _alpha(t3size, pot_before_3bet)
    bluff_ratio = _optimal_bluff_ratio(alpha)

    val = _is_value_3bet(hero_hand, position)
    bluff = _is_bluff_3bet(hero_hand)

    fold_pct = villain_fold_to_3bet if villain_fold_to_3bet is not None \
               else VILLAIN_FOLD_VS_3BET.get(villain_type, 0.50)

    total_pot = pot_before_3bet + 2.0 * t3size
    ev = _bluff_3bet_ev(t3size, pot_before_3bet, fold_pct, hero_equity_if_called, total_pot)

    strategy_type = _3bet_strategy_type(villain_type)

    if val:
        action = '3BET_VALUE'
    elif bluff and fold_pct > alpha:
        if strategy_type == 'merged':
            action = 'COLD_CALL_OR_FOLD'
        else:
            action = '3BET_BLUFF'
    elif strategy_type == 'merged' and val:
        action = '3BET_VALUE'
    else:
        action = 'COLD_CALL_OR_FOLD'

    # Count value combos to suggest bluff combos needed
    value_hands = VALUE_3BET_HANDS.get(position, VALUE_3BET_HANDS['co'])
    total_value_combos = sum(VALUE_COMBO_COUNTS.get(h, 6) for h in value_hands)
    recommended_bluff_combos = round(total_value_combos * bluff_ratio)

    verdict = (
        f'[3BR {hero_hand}|{position}|{villain_type}] '
        f'{action} size={t3size:.0f}BB alpha={alpha:.0%} '
        f'fold={fold_pct:.0%} EV={ev:+.1f}BB'
    )

    reasoning = (
        f'3-bet range: {hero_hand} from {position.upper()} vs {villain_type}. '
        f'3-bet to {t3size:.0f}BB. Alpha={alpha:.0%}. '
        f'Villain folds {fold_pct:.0%}. '
        f'Strategy type: {strategy_type}. '
        f'Action: {action}. EV={ev:+.1f}BB.'
    )

    tips = []

    tips.append(
        f'3-BET SIZING: {position.upper()} 3-bet to {t3size:.0f}BB ({t3size/open_bb:.1f}x). '
        f'Break-even fold%={alpha:.0%}. '
        f'Villain folds {fold_pct:.0%} -> '
        f'{"profitable immediate fold equity." if fold_pct > alpha else "fold equity insufficient for pure bluff."}'
    )

    tips.append(
        f'RANGE CONSTRUCTION ({strategy_type.upper()}): '
        f'~{total_value_combos} value combos from {position.upper()}. '
        f'Balanced range needs ~{recommended_bluff_combos} bluff combos '
        f'(bluff_ratio={bluff_ratio:.2f}). '
        f'Best bluffs: A2s-A5s (blocker + equity), suited connectors (fold to 4-bet).'
    )

    if val:
        tips.append(
            f'VALUE 3-BET: {hero_hand} is in value 3-bet range from {position.upper()}. '
            f'3-bet for max value; do not flat with premium hands. '
            f'Build pot and deny equity to drawing hands.'
        )
    elif bluff and fold_pct > alpha:
        tips.append(
            f'BLUFF 3-BET: {hero_hand} has blockers + equity. '
            f'Villain folds {fold_pct:.0%} > alpha {alpha:.0%} = profitable. '
            f'EV={ev:+.1f}BB. Can fold to 4-bet; not committed.'
        )
    else:
        tips.append(
            f'COLD CALL OR FOLD: {hero_hand} from {position.upper()}. '
            f'Not in value range; not a strong bluff spot vs {villain_type}. '
            f'{"Cold call if hand plays well postflop; fold if OOP." if hero_equity_if_called >= 0.35 else "Fold -- insufficient equity and fold equity to 3-bet."}'
        )

    if strategy_type == 'merged':
        tips.append(
            f'MERGED RANGE vs {villain_type.upper()}: Remove bluffs from 3-bet range. '
            f'Fish/calling stations fold too rarely; 3-bet only strong value. '
            f'Widen value range to include JJ/TT/AQs instead of bluffing.'
        )

    return ThreeBetRangeResult(
        hero_hand=hero_hand,
        position=position,
        villain_type=villain_type,
        is_value_3bet=val,
        is_bluff_3bet=bluff,
        threebet_size_bb=t3size,
        alpha_breakeven=alpha,
        bluff_ratio=bluff_ratio,
        strategy_type=strategy_type,
        bluff_3bet_ev_bb=ev,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tbr_one_liner(r: ThreeBetRangeResult) -> str:
    return (
        f'[3BR {r.hero_hand}|{r.position}] '
        f'{r.recommended_action} size={r.threebet_size_bb:.0f}BB '
        f'alpha={r.alpha_breakeven:.0%} EV={r.bluff_3bet_ev_bb:+.1f}BB'
    )
