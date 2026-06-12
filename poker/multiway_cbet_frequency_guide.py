"""
Multiway C-Bet Frequency Guide (multiway_cbet_frequency_guide.py)

C-bet frequency must drop dramatically in multiway pots because:
1. Probability all opponents fold = product of individual fold probabilities
2. Each additional caller reduces bluff profitability significantly
3. Strong hands required to bet into multiple opponents

THEORY:
  FOLD EQUITY vs N opponents:
  Combined fold = fold_1 x fold_2 x ... x fold_N
  Example: 3 opponents each folding 45% -> combined = 0.45^3 = 9%

  C-BET FREQUENCY GUIDELINES:
  Heads-up:    50-70% (standard range)
  3-way:       25-40% (significant drop)
  4-way:       15-25% (only strong hands)
  5-way+:       8-15% (near-nut hands only)

  HAND SELECTION IN MULTIWAY POTS:
  - TOP PAIR GOOD KICKER: C-bet for value and protection
  - OVERPAIR: Always c-bet for value
  - TWO PAIR+: Always c-bet for value
  - DRAWS: C-bet only with nut/strong draws (flush draw, OESD)
  - TOP PAIR WEAK KICKER: Check (often dominated in MW pot)
  - MIDDLE PAIR: Almost always check
  - AIR/BLUFF: Rarely c-bet (combined fold equity too low)

  C-BET SIZING IN MULTIWAY:
  - Smaller sizes DO NOT work as well (multiple callers can have wide ranges)
  - Use standard or slightly larger (65-75% pot) vs multiple opponents
  - One player weak = bet small; multiple weak players = bet larger

  BOARD TEXTURE MULTIWAY:
  - Dry boards: slightly higher frequency (fewer draws to worry about)
  - Wet/connected: lower frequency (more draws in multiple ranges)

DISTINCT FROM:
  multiway.py:                Basic multiway strategy
  multiway_advisor.py:        General multiway guidance
  cbet_continuation_rate.py:  C-bet frequency tracking
  range_cbet.py:              Range-based C-bet construction
  THIS MODULE:                MULTIWAY SPECIFIC; number-of-opponents scaling;
                              combined fold equity calculation; hand selection guide.
"""

from dataclasses import dataclass, field
from typing import List


HU_CBET_FREQ: dict = {
    'dry':      0.70,
    'semi_wet': 0.58,
    'wet':      0.48,
    'monotone': 0.42,
    'paired':   0.55,
}

OPPONENT_MULTIPLIER: dict = {
    2: 0.65,  # 3-way
    3: 0.45,  # 4-way
    4: 0.30,  # 5-way
    5: 0.20,  # 6-way
}

HAND_CBET_MODIFIER: dict = {
    'nuts':            1.30,
    'strong_value':    1.20,
    'overpair':        1.15,
    'top_pair_gk':     1.00,
    'top_pair_wk':     0.55,
    'middle_pair':     0.30,
    'draw_nut':        0.90,
    'draw_standard':   0.55,
    'air':             0.25,
    'missed_draw':     0.20,
}

VILLAIN_FOLD_VS_CBET: dict = {
    'fish':   0.38,
    'rec':    0.43,
    'nit':    0.55,
    'lag':    0.32,
    'reg':    0.40,
}


def _combined_fold_pct(opponent_types: list) -> float:
    """Combined probability all opponents fold."""
    combined = 1.0
    for vt in opponent_types:
        fold = VILLAIN_FOLD_VS_CBET.get(vt, 0.40)
        combined *= fold
    return round(combined, 3)


def _recommended_cbet_freq(
    n_opponents: int,
    board_texture: str,
    hand_strength: str,
) -> float:
    hu_freq = HU_CBET_FREQ.get(board_texture, 0.55)
    mw_mult = OPPONENT_MULTIPLIER.get(n_opponents, 0.20) if n_opponents > 1 else 1.0
    hand_mod = HAND_CBET_MODIFIER.get(hand_strength, 0.70)
    freq = hu_freq * mw_mult * hand_mod
    return round(min(1.0, max(0.05, freq)), 2)


def _cbet_sizing(n_opponents: int, board_texture: str, hand_strength: str) -> float:
    """Recommended C-bet size as fraction of pot."""
    if n_opponents == 1:
        base = 0.55
    elif n_opponents == 2:
        base = 0.60  # slightly larger vs 3-way
    else:
        base = 0.65  # larger needed to actually fold multiple opponents

    if board_texture in ('wet', 'monotone'):
        base = min(0.85, base + 0.10)
    if hand_strength in ('nuts', 'strong_value', 'overpair'):
        base = min(0.85, base + 0.05)

    return round(base, 2)


def _cbet_verdict(cbet_freq: float, combined_fold: float) -> str:
    if cbet_freq >= 0.60:
        return 'BET_STANDARD'
    elif cbet_freq >= 0.40:
        return 'BET_SELECTIVE'
    elif cbet_freq >= 0.20:
        return 'BET_VALUE_ONLY'
    elif combined_fold >= 0.12:
        return 'BET_RARELY'
    return 'CHECK_ALMOST_ALWAYS'


@dataclass
class MultiwayCbetResult:
    n_opponents: int
    opponent_types: list
    board_texture: str
    hand_strength: str

    combined_fold_pct: float
    recommended_cbet_freq: float
    cbet_size_frac: float

    cbet_verdict: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_multiway_cbet(
    n_opponents: int = 2,
    opponent_types: list = None,
    board_texture: str = 'semi_wet',
    hand_strength: str = 'top_pair_gk',
    pot_bb: float = 18.0,
    position: str = 'ip',
) -> MultiwayCbetResult:
    """
    Analyze C-bet frequency and sizing in a multiway pot.

    Args:
        n_opponents:        Number of opponents in the pot (1 = heads up, 2+ = multiway)
        opponent_types:     List of opponent types (['rec','fish',...])
        board_texture:      Flop texture ('dry','semi_wet','wet','monotone','paired')
        hand_strength:      Hero hand ('nuts','strong_value','overpair','top_pair_gk',
                            'top_pair_wk','middle_pair','draw_nut','draw_standard','air')
        pot_bb:             Current pot in BB
        position:           Hero position ('ip' or 'oop')

    Returns:
        MultiwayCbetResult
    """
    if opponent_types is None:
        opponent_types = ['rec'] * max(1, n_opponents)

    n_opp = max(1, n_opponents)
    freq = _recommended_cbet_freq(n_opp, board_texture, hand_strength)
    size = _cbet_sizing(n_opp, board_texture, hand_strength)
    size_bb = round(pot_bb * size, 1)
    combined_fold = _combined_fold_pct(opponent_types)
    cv = _cbet_verdict(freq, combined_fold)

    if position == 'oop':
        freq = round(max(0.05, freq * 0.88), 2)

    verdict = (
        f'[MCB {n_opp}opp|{board_texture}|{hand_strength}] '
        f'{cv} freq={freq:.0%} size={size:.0%}pot={size_bb:.1f}BB '
        f'all_fold={combined_fold:.0%}'
    )

    reasoning = (
        f'Multiway C-bet: {n_opp} opponents ({"+".join(opponent_types[:3])}). '
        f'Board: {board_texture}. Hand: {hand_strength}. '
        f'Recommended C-bet frequency: {freq:.0%}. '
        f'C-bet size: {size:.0%}pot = {size_bb:.1f}BB. '
        f'Combined fold probability: {combined_fold:.0%}. '
        f'Verdict: {cv}.'
    )

    tips = []

    tips.append(
        f'MULTIWAY FOLD EQUITY: Combined fold={combined_fold:.0%} with {n_opp} opponents. '
        f'{"Low fold equity -- bet only strong value hands." if combined_fold < 0.20 else "Reasonable fold equity -- selective C-bets profitable."} '
        f'Each added opponent multiplies fold% down significantly.'
    )

    tips.append(
        f'CBET FREQUENCY: {freq:.0%} (vs heads-up: {HU_CBET_FREQ.get(board_texture, 0.55):.0%}). '
        f'{"Standard C-bet range applies." if n_opp == 1 else "Significant reduction for multiway pot -- be more selective."}'
    )

    if n_opp >= 3:
        tips.append(
            f'VERY MULTIWAY ({n_opp} opponents): C-bet only {freq:.0%} of hands. '
            f'Stick to strong value ({hand_strength}), nut draws, overpairs. '
            f'Check medium pairs, weak top pairs, bluffs -- combined fold equity too low.'
        )
    elif n_opp == 2:
        tips.append(
            f'3-WAY POT: Drop C-bet frequency to {freq:.0%}. '
            f'Premium hands and nut draws fine to bet. '
            f'Avoid thin value and bluffs -- second opponent often calls.'
        )

    if hand_strength in ('air', 'missed_draw'):
        tips.append(
            f'BLUFF WARNING: C-betting {hand_strength} in a {n_opp}-way pot is rarely profitable. '
            f'Combined fold={combined_fold:.0%} means ~{1.0-combined_fold:.0%} chance '
            f'at least one opponent calls. Check and reevaluate.'
        )
    elif hand_strength in ('nuts', 'strong_value', 'overpair'):
        tips.append(
            f'VALUE BET: {hand_strength} -- C-bet for value even multiway. '
            f'Use {size:.0%}pot ({size_bb:.1f}BB) for protection and value. '
            f'Checking risks free cards to drawing hands.'
        )

    return MultiwayCbetResult(
        n_opponents=n_opp,
        opponent_types=opponent_types,
        board_texture=board_texture,
        hand_strength=hand_strength,
        combined_fold_pct=combined_fold,
        recommended_cbet_freq=freq,
        cbet_size_frac=size,
        cbet_verdict=cv,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def mcb_one_liner(r: MultiwayCbetResult) -> str:
    return (
        f'[MCB {r.n_opponents}opp|{r.board_texture}|{r.hand_strength}] '
        f'{r.cbet_verdict} freq={r.recommended_cbet_freq:.0%} '
        f'size={r.cbet_size_frac:.0%}pot all_fold={r.combined_fold_pct:.0%}'
    )
