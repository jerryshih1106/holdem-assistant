"""
Range vs Board Coverage Analyzer (range_board_coverage.py)

Understanding which player has range advantage on a given board is the
theoretical foundation for c-bet frequency decisions.

The player whose preflop range "covers" the board better (more hands that
pair, make draws, or otherwise connect) has range advantage and should:
  - C-bet more frequently (wider range = more value combinations)
  - Use smaller sizes on dry boards (range advantage without protection need)
  - Pot control less (has more hands that want to build pot)

The player without range advantage should:
  - Check and defend more passively
  - Trap when strong (their strong hands are more credible)
  - Rarely bluff (few board-appropriate bluffs)

Board coverage by board type:
  High boards (A/K/Q-high, dry):
    - PFR has ~28-30% top pair coverage (AK, AQ, KQ, Ax combos)
    - BB caller has ~12-14% (fewer Ax/Kx, more speculative hands)
    - PFR range advantage: HIGH → c-bet wide at 55-70% pot

  Low boards (2-8-high):
    - BB has ~28-30% coverage (55, 66, 76s, 87s, 97s — all BB calling range)
    - PFR has ~10-12% (premium pairs like AA-TT + some suited connectors)
    - Caller range advantage: LOW boards are bad for PFR → check more

  Medium boards (9-J-high):
    - Roughly balanced — both ranges connect similarly
    - PFR still has slight advantage (JJ, TT, 99 in opening range)
    - Neutral to slight PFR advantage

  Wet boards:
    - Draws reduce effective range advantage (both have similar draw frequencies)
    - Value of connected hands equalizes partially
    - CRITICAL: even with range advantage, protection is needed → bet larger

  Paired boards:
    - PFR has pocket pairs in opening range at higher frequency
    - But full houses are rare for both → split advantage

  Monotone boards:
    - Flush draws equalize both ranges (both have ~5-8% suited combos)
    - Range advantage nearly neutral on monotone boards

Usage:
    from poker.range_board_coverage import analyze_range_coverage, RangeBoardCoverage
    result = analyze_range_coverage(
        pfr_pos='BTN', caller_pos='BB',
        board_high='K', board_type='dry',
    )
    print(result.range_advantage, result.pfr_coverage, result.caller_coverage)
    print(coverage_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List, Tuple


def _board_height(board_high: str) -> str:
    """Classify board highest card as 'high', 'medium', or 'low'."""
    high_cards = {'A', 'K', 'Q'}
    medium_cards = {'J', 'T', '9'}
    if board_high.upper() in high_cards:
        return 'high'
    if board_high.upper() in medium_cards:
        return 'medium'
    return 'low'


# Coverage fractions: fraction of each player's range that connects with board
# Format: (pfr_coverage, caller_coverage)
# Based on standard 6-max opening ranges:
#   BTN opens ~40%, CO ~28%, HJ ~20%, UTG ~13%
#   BB defends ~55-65% vs BTN, ~50-60% vs CO
_BASE_COVERAGE: dict = {
    ('high', 'dry'):      (0.30, 0.13),   # K72r: BTN has AKs, KQs, KJs... BB has mostly misses
    ('high', 'medium'):   (0.24, 0.18),   # K87t: BB has more suited connectors
    ('high', 'wet'):      (0.20, 0.22),   # K98s: draws equalize, slight caller edge
    ('medium', 'dry'):    (0.18, 0.22),   # T72r: BB has more 76s, T9s-type hands
    ('medium', 'medium'): (0.16, 0.26),   # T87r: BB mid-connected hands hit well
    ('medium', 'wet'):    (0.13, 0.31),   # JT9s: BB speculative range thrives
    ('low', 'dry'):       (0.12, 0.28),   # 742r: BB has 44, 77, small pairs
    ('low', 'medium'):    (0.10, 0.30),   # 764t: BB suited connectors
    ('low', 'wet'):       (0.09, 0.35),   # 876s: worst board for PFR
    ('paired', 'dry'):    (0.26, 0.16),   # KK2: PFR has more pocket pairs
    ('paired', 'medium'): (0.22, 0.18),
    ('monotone', 'wet'):  (0.15, 0.20),   # monotone: flush draws equalize
    ('monotone', 'dry'):  (0.20, 0.17),   # dry monotone: PFR slight edge
}


def _get_coverage(board_height: str, board_type: str) -> Tuple[float, float]:
    """Get (pfr_coverage, caller_coverage) for board type."""
    key = (board_height, board_type)
    if key in _BASE_COVERAGE:
        return _BASE_COVERAGE[key]
    # Fallback: use medium/medium
    return _BASE_COVERAGE.get(('medium', 'medium'), (0.16, 0.22))


def _pfr_range_pct(pfr_pos: str) -> float:
    """Standard opening range % by position."""
    return {
        'UTG': 0.13, 'UTG1': 0.16, 'HJ': 0.20,
        'CO': 0.27, 'BTN': 0.42, 'SB': 0.40,
    }.get(pfr_pos, 0.25)


def _caller_range_pct(caller_pos: str, pfr_pos: str) -> float:
    """Typical calling range % vs the PFR's position."""
    # BB defends wide vs BTN/CO, tighter vs UTG
    if caller_pos == 'BB':
        return {'BTN': 0.60, 'CO': 0.52, 'HJ': 0.46, 'UTG': 0.40, 'SB': 0.52}.get(pfr_pos, 0.50)
    if caller_pos == 'SB':
        return {'BTN': 0.20, 'CO': 0.18, 'HJ': 0.15, 'UTG': 0.12}.get(pfr_pos, 0.15)
    # IP caller (cold call)
    return {'BTN': 0.12, 'CO': 0.10, 'HJ': 0.08}.get(pfr_pos, 0.10)


def _range_advantage_label(pfr_cov: float, caller_cov: float) -> Tuple[str, float]:
    """(advantage_holder, magnitude 0-1)"""
    diff = pfr_cov - caller_cov
    magnitude = min(1.0, abs(diff) / 0.20)  # normalize: 20% diff = full advantage
    if diff >= 0.05:
        return ('pfr', round(magnitude, 2))
    if diff <= -0.05:
        return ('caller', round(magnitude, 2))
    return ('neutral', round(magnitude, 2))


def _cbet_freq_adjustment(
    advantage: str,
    magnitude: float,
    board_type: str,
) -> float:
    """
    Multiplier applied to base c-bet frequency (1.0 = no change).
    PFR advantage → bet more; caller advantage → bet less.
    """
    if advantage == 'pfr':
        adj = 1.0 + magnitude * 0.30  # up to +30% more frequent
    elif advantage == 'caller':
        adj = 1.0 - magnitude * 0.40  # up to -40% less frequent
    else:
        adj = 1.0

    # Wet boards: even with range advantage, need protection
    if board_type == 'wet':
        adj = max(adj, 0.85)   # always cbet at least 85% of base on wet boards

    return round(min(1.40, max(0.35, adj)), 2)


def _cbet_size_suggestion(
    advantage: str,
    board_type: str,
    magnitude: float,
) -> str:
    """Recommended c-bet size description."""
    if board_type == 'wet':
        return '65-80% pot (charge draws regardless of range advantage)'
    if board_type == 'monotone':
        return '40-55% pot (balanced — polarize nuts vs air)'
    if board_type == 'paired':
        return '33-45% pot (two pair+ bet; air check)'
    # dry / medium
    if advantage == 'pfr' and magnitude >= 0.60:
        return '40-55% pot (large range advantage: use smaller, bet wider)'
    if advantage == 'pfr' and magnitude >= 0.30:
        return '50-65% pot (moderate range advantage: standard sizing)'
    if advantage == 'caller':
        return '50-65% pot (despite disadvantage: bet for protection only)'
    return '50-60% pot (neutral: standard sizing)'


def _xr_freq_adjustment(advantage: str, magnitude: float) -> float:
    """Multiplier on check-raise frequency for the caller."""
    if advantage == 'caller':
        return round(1.0 + magnitude * 0.35, 2)   # caller has more strong hands to XR with
    if advantage == 'pfr':
        return round(1.0 - magnitude * 0.20, 2)   # caller has fewer good XR combos
    return 1.0


@dataclass
class RangeBoardCoverage:
    """Range vs board coverage analysis: who has range advantage?"""
    pfr_pos: str
    caller_pos: str
    board_high: str
    board_height: str     # 'high', 'medium', 'low'
    board_type: str       # 'dry', 'medium', 'wet', 'paired', 'monotone'

    # Range sizes
    pfr_range_pct: float
    caller_range_pct: float

    # Board coverage (fraction of range connecting with board)
    pfr_coverage: float
    caller_coverage: float
    coverage_diff: float   # pfr - caller (positive = PFR advantage)

    # Range advantage
    range_advantage: str   # 'pfr', 'caller', or 'neutral'
    advantage_magnitude: float   # 0-1

    # Strategic adjustments
    pfr_cbet_freq_adj: float   # multiplier on base cbet frequency
    pfr_cbet_size: str         # recommended size description
    caller_xr_freq_adj: float  # multiplier on caller's check-raise frequency

    # Reasoning
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_range_coverage(
    pfr_pos: str = 'BTN',
    caller_pos: str = 'BB',
    board_high: str = 'K',
    board_type: str = 'dry',
) -> RangeBoardCoverage:
    """
    Analyze range vs board coverage to determine strategic adjustments.

    Args:
        pfr_pos:    Preflop raiser's position ('UTG','HJ','CO','BTN','SB')
        caller_pos: Caller's position ('BB','SB','CO', etc.)
        board_high: Highest board card: 'A','K','Q','J','T','9','8','7','6','5','4','3','2'
        board_type: Board texture: 'dry', 'medium', 'wet', 'paired', 'monotone'

    Returns:
        RangeBoardCoverage
    """
    height = _board_height(board_high)
    pfr_range = _pfr_range_pct(pfr_pos)
    caller_range = _caller_range_pct(caller_pos, pfr_pos)

    # Coverage lookup (adjusted for monotone/paired)
    if board_type in ('paired', 'monotone'):
        pfr_cov, caller_cov = _get_coverage(board_type, board_type)
    else:
        pfr_cov, caller_cov = _get_coverage(height, board_type)

    # Adjust for range width: wider PFR range = more speculative hands = slightly less coverage
    # BTN opens 42% including many speculative hands that miss high boards
    if pfr_range > 0.35 and height == 'high':
        pfr_cov -= 0.02  # BTN range diluted with 76s, 87s etc.
    # Narrower PFR range = more concentrated high-card hands = more coverage
    elif pfr_range < 0.18 and height == 'high':
        pfr_cov += 0.04  # UTG opens AK, AQ, KQ much more often

    pfr_cov = round(max(0.05, min(0.50, pfr_cov)), 3)
    caller_cov = round(max(0.05, min(0.50, caller_cov)), 3)
    diff = round(pfr_cov - caller_cov, 3)

    advantage, magnitude = _range_advantage_label(pfr_cov, caller_cov)
    freq_adj = _cbet_freq_adjustment(advantage, magnitude, board_type)
    size_desc = _cbet_size_suggestion(advantage, board_type, magnitude)
    xr_adj = _xr_freq_adjustment(advantage, magnitude)

    # Build reasoning
    if advantage == 'pfr':
        reason = (
            f'{pfr_pos} has range advantage on {board_high}-high {board_type} board. '
            f'{pfr_pos} coverage={pfr_cov:.0%} vs {caller_pos} coverage={caller_cov:.0%} '
            f'(+{diff:.0%} edge). C-bet wider and smaller to exploit.'
        )
    elif advantage == 'caller':
        reason = (
            f'{caller_pos} has range advantage on {board_high}-high {board_type} board. '
            f'{caller_pos} coverage={caller_cov:.0%} vs {pfr_pos} coverage={pfr_cov:.0%} '
            f'({diff:.0%} deficit). C-bet only with strong hands or for protection.'
        )
    else:
        reason = (
            f'Neutral range advantage on {board_high}-high {board_type} board. '
            f'{pfr_pos} coverage={pfr_cov:.0%} vs {caller_pos} coverage={caller_cov:.0%}. '
            f'Mixed strategy: c-bet strong hands, check marginal.'
        )

    # Tips
    tips = []
    if advantage == 'caller' and board_type == 'dry':
        tips.append(
            f'{board_high}-high dry board: {caller_pos} has more connected hands '
            f'(small pairs, suited connectors). C-bet only top pair or better. '
            f'Check-fold or check-call middle part of range.'
        )
    if advantage == 'pfr' and magnitude >= 0.60:
        tips.append(
            f'Large range advantage: bet {pfr_pos}\'s full top-pair range for value. '
            f'Include some air bets (35-45% of air hands) since villain\'s range is also capped. '
            f'Use small sizing ({size_desc}) to keep bluffing range credible.'
        )
    if board_type == 'wet':
        tips.append(
            f'Wet board: range advantage matters less — draws equalize both ranges. '
            f'Focus on protection betting rather than range-advantage exploitation. '
            f'Bet for value AND protection with top pair+ and strong draws.'
        )
    if board_type == 'low':
        tips.append(
            f'Low board ({board_high}-high): {caller_pos} range is full of small pairs and '
            f'suited connectors that hit here. Consider check-folding medium-strength hands '
            f'and check-raising with your top 10-15% of hands for balance.'
        )
    tips.append(
        f'C-bet frequency adjustment: {freq_adj:.0%}x base. '
        f'Standard base: ~60% dry / ~45% medium / ~35% wet. '
        f'Example: BTN vs BB, dry board → base 60% × {freq_adj:.1f} = {60*freq_adj:.0f}%.'
    )

    return RangeBoardCoverage(
        pfr_pos=pfr_pos,
        caller_pos=caller_pos,
        board_high=board_high.upper(),
        board_height=height,
        board_type=board_type,
        pfr_range_pct=round(pfr_range, 2),
        caller_range_pct=round(caller_range, 2),
        pfr_coverage=pfr_cov,
        caller_coverage=caller_cov,
        coverage_diff=diff,
        range_advantage=advantage,
        advantage_magnitude=magnitude,
        pfr_cbet_freq_adj=freq_adj,
        pfr_cbet_size=size_desc,
        caller_xr_freq_adj=xr_adj,
        reasoning=reason,
        tips=tips,
    )


def coverage_one_liner(result: RangeBoardCoverage) -> str:
    adv = result.range_advantage.upper()
    return (
        f'[RBC {result.pfr_pos}v{result.caller_pos}|{result.board_high}-{result.board_type}] '
        f'adv={adv}({result.advantage_magnitude:.0%}) | '
        f'pfr={result.pfr_coverage:.0%} caller={result.caller_coverage:.0%} | '
        f'cbet_adj={result.pfr_cbet_freq_adj:.0%}x'
    )
