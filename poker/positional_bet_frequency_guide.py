"""
Positional Bet Frequency Guide (positional_bet_frequency_guide.py)

How often to bet/raise by position and street. IP positions (BTN, CO) bet
more frequently; OOP positions (UTG, SB) bet less. Board texture and villain
type further calibrate frequency.

THEORY:
  WHY POSITION DETERMINES BET FREQUENCY:
  - IP (BTN): Sees villain's action first; bets wide (range advantage)
  - OOP (UTG): Narrower range; cannot see future action; bets less
  - BB: Usually defends (wide range), but has position on SB postflop

  BASELINE BET FREQUENCIES BY POSITION + STREET:
  Position   Flop   Turn   River
  BTN        60%    55%    50%    (most aggressive IP)
  CO         55%    50%    45%
  MP         48%    42%    38%
  UTG        42%    38%    35%    (tightest range; bet only strong)
  SB         45%    40%    38%    (OOP; range is wide but position hurts)
  BB         35%    42%    45%    (donk bet rarely; probe more on later streets)

  BOARD TEXTURE ADJUSTMENTS:
  Dry boards: bet more (range bet optimal; few draws to balance)
  Wet boards: bet less (need checking range to protect vs check-raise)
  Monotone: bet less (villain has flush draw equity everywhere)

  VILLAIN TYPE ADJUSTMENTS:
  vs Fish/Station: bet MORE often (exploit calling; value bets profitable)
  vs Nit: bet LESS often (nit folds mediocre; only bet strong)
  vs LAG: bet LESS with medium hands (LAG raises; gets us in trouble)

  MULTIWAY POTS:
  Reduce bet frequency with each extra opponent (each player who calls
  needs to be beaten; need stronger hands to bet for value).

  HOW TO USE:
  1. Look up baseline bet freq for your position + street
  2. Apply texture/villain/multiway adjustments
  3. This is the FRACTION of your range to bet on this street

DISTINCT FROM:
  cbet_frequency_auditor.py:      C-bet frequency audit tool
  multiway_cbet_frequency_guide.py: Multiway c-bet
  bet_sizing.py:                  Bet sizing (not frequency)
  THIS MODULE:                    AGGREGATE BET FREQUENCY by position/street;
                                  includes all hands in range (not just specific hands).
"""

from dataclasses import dataclass, field
from typing import List


BASELINE_BET_FREQ: dict = {
    'btn': {'flop': 0.60, 'turn': 0.55, 'river': 0.50},
    'co':  {'flop': 0.55, 'turn': 0.50, 'river': 0.45},
    'mp':  {'flop': 0.48, 'turn': 0.42, 'river': 0.38},
    'utg': {'flop': 0.42, 'turn': 0.38, 'river': 0.35},
    'hj':  {'flop': 0.50, 'turn': 0.44, 'river': 0.40},
    'sb':  {'flop': 0.45, 'turn': 0.40, 'river': 0.38},
    'bb':  {'flop': 0.35, 'turn': 0.42, 'river': 0.45},
}

BOARD_TEXTURE_FREQ_ADJ: dict = {
    'dry':      +0.08,
    'semi_wet':  0.00,
    'wet':      -0.06,
    'monotone': -0.10,
    'paired':   +0.04,
}

VILLAIN_FREQ_ADJ: dict = {
    'fish':            +0.10,
    'calling_station': +0.12,
    'rec':             +0.05,
    'nit':             -0.08,
    'lag':             -0.06,
    'reg':              0.00,
}

MULTIWAY_FREQ_ADJ: dict = {
    0: 0.00,
    1: -0.10,
    2: -0.18,
    3: -0.24,
    4: -0.28,
}

POSITION_IP_OOP: dict = {
    'btn': 'ip', 'co': 'ip', 'mp': 'ip', 'hj': 'ip', 'utg': 'ip',
    'sb': 'oop', 'bb': 'oop',
}

POSITION_LABELS: dict = {
    'btn': 'Button (most IP)', 'co': 'Cutoff', 'mp': 'Middle Position',
    'hj': 'Hijack', 'utg': 'Under the Gun (tightest)',
    'sb': 'Small Blind (OOP)', 'bb': 'Big Blind',
}


def _bet_frequency(
    position: str,
    street: str,
    board_texture: str,
    villain_type: str,
    extra_opponents: int,
) -> float:
    base_dict = BASELINE_BET_FREQ.get(position, BASELINE_BET_FREQ['mp'])
    base = base_dict.get(street, 0.45)
    tex_adj = BOARD_TEXTURE_FREQ_ADJ.get(board_texture, 0.00)
    vil_adj = VILLAIN_FREQ_ADJ.get(villain_type, 0.00)
    mw_adj = MULTIWAY_FREQ_ADJ.get(min(extra_opponents, 4), 0.00)
    result = base + tex_adj + vil_adj + mw_adj
    return round(min(0.85, max(0.10, result)), 3)


def _bet_frequency_label(freq: float) -> str:
    if freq >= 0.70:
        return 'HIGH (range bet territory)'
    if freq >= 0.55:
        return 'MODERATE-HIGH'
    if freq >= 0.42:
        return 'MODERATE'
    if freq >= 0.30:
        return 'LOW-MODERATE'
    return 'LOW (bet only strong hands)'


@dataclass
class PositionalBetFrequencyResult:
    position: str
    street: str
    board_texture: str
    villain_type: str
    extra_opponents: int

    baseline_freq: float
    adjusted_freq: float
    freq_label: str
    ip_oop: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_positional_bet_frequency(
    position: str = 'btn',
    street: str = 'flop',
    board_texture: str = 'semi_wet',
    villain_type: str = 'reg',
    extra_opponents: int = 0,
) -> PositionalBetFrequencyResult:
    """
    Recommend bet frequency for a given position, street, and conditions.

    Args:
        position:         Hero position ('utg','mp','hj','co','btn','sb','bb')
        street:           Current street ('flop','turn','river')
        board_texture:    Board texture ('dry','semi_wet','wet','monotone','paired')
        villain_type:     Primary villain type ('fish','rec','nit','lag','reg')
        extra_opponents:  Number of opponents beyond the primary (0=HU, 1=3-way, ...)

    Returns:
        PositionalBetFrequencyResult
    """
    base_dict = BASELINE_BET_FREQ.get(position, BASELINE_BET_FREQ['mp'])
    baseline = base_dict.get(street, 0.45)
    adjusted = _bet_frequency(position, street, board_texture, villain_type, extra_opponents)
    label = _bet_frequency_label(adjusted)
    ip_oop = POSITION_IP_OOP.get(position, 'ip')

    verdict = (
        f'[PBF {position.upper()}|{street}|{board_texture}] '
        f'base={baseline:.0%} adj={adjusted:.0%} ({label})'
    )

    reasoning = (
        f'Positional bet frequency: {position.upper()} ({ip_oop}) on {street}, {board_texture} board. '
        f'Villain={villain_type}. Extra opponents={extra_opponents}. '
        f'Baseline={baseline:.0%}, adjustments: '
        f'texture={BOARD_TEXTURE_FREQ_ADJ.get(board_texture, 0):+.0%}, '
        f'villain={VILLAIN_FREQ_ADJ.get(villain_type, 0):+.0%}, '
        f'multiway={MULTIWAY_FREQ_ADJ.get(min(extra_opponents, 4), 0):+.0%}. '
        f'Adjusted={adjusted:.0%} ({label}).'
    )

    tips = []

    tips.append(
        f'BET FREQUENCY: {position.upper()} on {street}: bet {adjusted:.0%} of range ({label}). '
        f'Baseline={baseline:.0%} for {POSITION_LABELS.get(position, position)}. '
        f'{"IP position gives range/nut advantage -- bet wide on this board." if ip_oop == "ip" else "OOP reduces frequency -- protect your checking range."}'
    )

    tips.append(
        f'ADJUSTMENTS: Texture={board_texture} ({BOARD_TEXTURE_FREQ_ADJ.get(board_texture, 0):+.0%}), '
        f'villain={villain_type} ({VILLAIN_FREQ_ADJ.get(villain_type, 0):+.0%}), '
        f'multiway={extra_opponents} extra ({MULTIWAY_FREQ_ADJ.get(min(extra_opponents,4), 0):+.0%}). '
        f'Net adj={adjusted-baseline:+.0%}.'
    )

    if extra_opponents >= 2:
        tips.append(
            f'MULTIWAY ({extra_opponents + 1} players): Reduce bet frequency significantly. '
            f'Each extra opponent needs to be beaten; bluffs have low fold equity multiway. '
            f'Bet only strong value hands; check bluffs and medium hands.'
        )

    if villain_type in ('fish', 'calling_station'):
        tips.append(
            f'VS {villain_type.upper()}: Increase bet freq +{VILLAIN_FREQ_ADJ[villain_type]:.0%}. '
            f'Value bet thin; bet more streets for value. '
            f'Reduce bluffing (fish call too often for bluffs to be profitable).'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT: Reduce bet freq {VILLAIN_FREQ_ADJ["nit"]:.0%}. '
            f'Nit folds too many mediocre hands -- only bet when you have real strength. '
            f'Check medium hands and draws; save bets for your value hands.'
        )

    return PositionalBetFrequencyResult(
        position=position,
        street=street,
        board_texture=board_texture,
        villain_type=villain_type,
        extra_opponents=extra_opponents,
        baseline_freq=baseline,
        adjusted_freq=adjusted,
        freq_label=label,
        ip_oop=ip_oop,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pbf_one_liner(r: PositionalBetFrequencyResult) -> str:
    return (
        f'[PBF {r.position.upper()}|{r.street}|{r.board_texture}] '
        f'bet={r.adjusted_freq:.0%} ({r.freq_label[:12]})'
    )
