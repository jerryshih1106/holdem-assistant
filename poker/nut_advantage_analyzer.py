"""
Nut Advantage Analyzer (nut_advantage_analyzer.py)

Nut advantage is the key driver for overbet decisions at poker. The player
whose range contains more "nut" combinations (top 5-10% of all hands) on a
given board can profitably overbet, while the player without nut advantage
should use smaller sizes to maintain bet/fold protection.

Why nut advantage matters:
  If you overbet and villain has no nut hands to raise with, they face an
  impossible calling problem — they need 40%+ equity but can't have it with
  medium-strength hands. Overbetting WITHOUT nut advantage is dangerous:
  villain can raise you off your medium-strength hands.

Who has nut advantage on which boards:

  High boards (A/K/Q-high):
    - PFR nut hands: AK (top two pair → full house), KK/AA (sets), QQ (on Q-high)
    - Caller nut hands: fewer — mostly small sets (77, 22 on K72)
    - PFR has significant nut advantage → can overbet more safely

  Low boards (2-8-high, dry):
    - Caller nut hands: small pairs → sets (55, 44, 33, 22), suited connectors for straights
    - PFR nut hands: high pocket pairs (AA, KK) don't connect as well
    - Slight caller nut advantage on low boards

  Flush boards (monotone or two-flush):
    - PFR has more big suited combos (AKs, AQs, KQs) → more top flushes
    - Caller has more medium flushes (87s, 76s) → many second-best flushes
    - PFR has TOP flush advantage; caller has more FLUSH combos but lower quality

  Paired boards:
    - PFR has pocket pairs → trips/full house more frequently
    - BB caller less often has specific pair that pairs board

  Straight boards (connected like 9-8-7):
    - BB's calling range is full of 65s, T9s, JTs → hits many straights
    - PFR has TT, JJ in range but fewer small suited connectors
    - Caller has nut straight advantage on low straight boards

  High straight boards (AKQ, KQJ):
    - PFR has AK, KQ, QJ in range → hits nut straights
    - Caller has AJs, QTs → also hits but PFR's range hits better

Key metric:
  nut_advantage_pct = (pfr_nut_combos - caller_nut_combos) / total_nut_combos

When nut_advantage >= 0.15: clear overbet candidate for advantage holder
When nut_advantage < 0.05: avoid overbets; use standard sizing

Usage:
    from poker.nut_advantage_analyzer import analyze_nut_advantage, NutAdvantageResult
    from poker.nut_advantage_analyzer import nut_advantage_one_liner
    result = analyze_nut_advantage(
        pfr_pos='BTN', caller_pos='BB',
        board_high='K', board_type='dry', board_paired=False,
        flush_possible=False, straight_possible=False,
    )
    print(result.nut_advantage, result.should_overbet)
"""

from dataclasses import dataclass, field
from typing import List


def _pfr_range_width(pfr_pos: str) -> float:
    """Fraction of all hands in PFR's opening range."""
    return {
        'UTG': 0.13, 'UTG1': 0.16, 'HJ': 0.20,
        'CO': 0.27, 'BTN': 0.42, 'SB': 0.40,
    }.get(pfr_pos, 0.25)


def _pfr_nut_pct(
    pfr_pos: str,
    board_high: str,
    board_type: str,
    board_paired: bool,
    flush_possible: bool,
    straight_possible: bool,
    board_height: str,
) -> float:
    """
    Estimate fraction of PFR's range that constitutes nut-level holdings.
    Nut = top 5-10%: sets, top two pair, top flush, nut straight.
    """
    pfr_width = _pfr_range_width(pfr_pos)

    # Base by board height — PFR's range connects with high boards
    base = {
        'high':   0.12,   # Many AK, KK, AA combos → sets/two-pair
        'medium': 0.09,   # JJ-99, some broadway combos
        'low':    0.06,   # AA, KK still there but rarely sets; fewer nut straights
    }.get(board_height, 0.09)

    # Wider opening range (BTN) = more speculative hands = slight dilution
    if pfr_width > 0.35:
        base -= 0.01   # BTN includes 87s, 76s which aren't nuts on high boards
    elif pfr_width < 0.18:
        base += 0.02   # UTG range is concentrated in premium hands

    # Flush board: PFR has high-card suited combos → top flush
    if flush_possible:
        base += 0.04   # AXs, KXs in range → often top flush

    # Straight board: depends on board height
    if straight_possible:
        if board_height == 'high':
            base += 0.03   # PFR has KQ, QJ for nut straights
        else:
            base -= 0.01   # Low straight boards: PFR lacks small connectors

    # Paired board: PFR has pocket pairs → trips/boat
    if board_paired:
        base += 0.03   # All pocket pairs pair up (only one board card pairs)

    return round(min(0.35, max(0.02, base)), 3)


def _caller_nut_pct(
    caller_pos: str,
    board_high: str,
    board_type: str,
    board_paired: bool,
    flush_possible: bool,
    straight_possible: bool,
    board_height: str,
) -> float:
    """
    Estimate fraction of caller's range that constitutes nut-level holdings.
    """
    # BB caller has wide range: ~50-65% of hands
    # More speculative = more coverage of medium boards, worse coverage of high boards

    base = {
        'high':   0.05,   # BB misses high boards mostly (few AK, KK in flat range)
        'medium': 0.10,   # BB has J9s, T8s → connects with medium boards
        'low':    0.13,   # BB has 55, 44, 87s, 76s → many sets/straights on low boards
    }.get(board_height, 0.08)

    # SB caller is tighter; IP cold-caller is tighter
    if caller_pos != 'BB':
        base -= 0.02   # less speculative calling range

    # Flush board: caller's medium suited connectors give flushes
    if flush_possible:
        base += 0.03   # 76s, 87s suited combos → lower flushes but many

    # Straight board: caller has suited connectors → many straights on low boards
    if straight_possible:
        if board_height == 'low':
            base += 0.05   # 65s, 87s, T9s → lots of straights
        elif board_height == 'medium':
            base += 0.03
        else:
            base += 0.01   # fewer high straight combos

    # Paired board: caller has specific pairs → trips (e.g., 77 when 7 on board)
    if board_paired:
        base += 0.02   # some specific small pairs in calling range

    return round(min(0.35, max(0.02, base)), 3)


def _nut_advantage(pfr_nut: float, caller_nut: float) -> tuple:
    """Returns (advantage_holder, magnitude 0-1)."""
    diff = pfr_nut - caller_nut
    # Threshold: 3% absolute difference = meaningful nut advantage
    if diff >= 0.03:
        magnitude = min(1.0, diff / 0.12)  # normalize: 12% = full advantage
        return ('pfr', round(magnitude, 2))
    if diff <= -0.03:
        magnitude = min(1.0, abs(diff) / 0.12)
        return ('caller', round(magnitude, 2))
    return ('neutral', round(abs(diff) / 0.06, 2))


def _overbet_recommendation(
    advantage: str, magnitude: float, board_type: str, board_height: str
) -> tuple:
    """(should_overbet_who, suggested_size_desc)"""
    if advantage == 'neutral' or magnitude < 0.20:
        return ('neither', 'avoid overbets; use 60-80% pot standard sizing')

    holder = advantage
    if board_type == 'wet' and magnitude < 0.50:
        # Wet boards: even with nut advantage, draws complicate overbetting
        size = '100-120% pot (moderate overbet; draws prevent going larger)'
    elif magnitude >= 0.70:
        size = '120-150% pot (large overbet safe: clear nut advantage)'
    else:
        size = '100-120% pot (moderate overbet: good but not overwhelming advantage)'

    return (holder, size)


def _defender_strategy(advantage: str, magnitude: float, board_type: str) -> str:
    """Strategy for the player WITHOUT nut advantage."""
    if advantage == 'neutral':
        return 'Standard defense: call with MDF-appropriate range, raise with nut hands only.'
    if advantage == 'pfr':
        # Caller is the defender
        if magnitude >= 0.60:
            return (
                'Defender (caller): call only strong hands (two pair+) vs overbets. '
                'Fold marginal holdings. Raising is dangerous — you have fewer nuts to raise with.'
            )
        return (
            'Defender (caller): standard MDF defense. Check-raise moderately '
            'since you have some nut combinations but fewer than PFR.'
        )
    else:
        # PFR is the defender
        return (
            'Defender (PFR): check more on this board — you have fewer nut combos. '
            'Avoid large bets; use small size (33-45% pot) when betting. '
            'Call down with medium hands; fold marginal to large bets.'
        )


@dataclass
class NutAdvantageResult:
    """Analysis of nut-hand advantage on a given board."""
    pfr_pos: str
    caller_pos: str
    board_high: str
    board_height: str
    board_type: str
    board_paired: bool
    flush_possible: bool
    straight_possible: bool

    # Nut coverage estimates
    pfr_nut_pct: float     # fraction of PFR's range that holds nuts
    caller_nut_pct: float  # fraction of caller's range that holds nuts
    nut_diff: float        # pfr_nut_pct - caller_nut_pct

    # Advantage
    nut_advantage: str         # 'pfr', 'caller', 'neutral'
    advantage_magnitude: float  # 0-1

    # Recommendations
    should_overbet: str        # 'pfr', 'caller', 'neither'
    overbet_size: str          # size description if overbetting
    defender_strategy: str     # strategy for the player WITHOUT nut advantage

    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_nut_advantage(
    pfr_pos: str = 'BTN',
    caller_pos: str = 'BB',
    board_high: str = 'K',
    board_type: str = 'dry',
    board_paired: bool = False,
    flush_possible: bool = False,
    straight_possible: bool = False,
) -> NutAdvantageResult:
    """
    Analyze who holds nut advantage on a given board.

    Args:
        pfr_pos:          Preflop raiser's position
        caller_pos:       Caller's position
        board_high:       Highest board card ('A','K','Q','J','T','9','8','7','6','5','4','3','2')
        board_type:       'dry', 'medium', 'wet', 'paired', 'monotone'
        board_paired:     True if the board has a pair (e.g., K-K-7 or 8-8-3)
        flush_possible:   True if two or more cards of same suit on board
        straight_possible: True if three connected cards on board

    Returns:
        NutAdvantageResult
    """
    high_cards = {'A', 'K', 'Q'}
    medium_cards = {'J', 'T', '9'}
    board_h = board_high.upper()
    height = 'high' if board_h in high_cards else ('medium' if board_h in medium_cards else 'low')

    pfr_nut = _pfr_nut_pct(pfr_pos, board_high, board_type, board_paired,
                            flush_possible, straight_possible, height)
    caller_nut = _caller_nut_pct(caller_pos, board_high, board_type, board_paired,
                                  flush_possible, straight_possible, height)
    diff = round(pfr_nut - caller_nut, 3)

    advantage, magnitude = _nut_advantage(pfr_nut, caller_nut)
    should_ob, ob_size = _overbet_recommendation(advantage, magnitude, board_type, height)
    defender = _defender_strategy(advantage, magnitude, board_type)

    # Build reasoning
    if advantage == 'pfr':
        reason = (
            f'{pfr_pos} has nut advantage on {board_h}-high {board_type} board. '
            f'PFR nut%={pfr_nut:.0%} vs caller nut%={caller_nut:.0%} (+{diff:.0%}). '
            f'{pfr_pos} can overbet with nutted hands safely.'
        )
    elif advantage == 'caller':
        reason = (
            f'{caller_pos} has nut advantage on {board_h}-high {board_type} board. '
            f'Caller nut%={caller_nut:.0%} vs PFR nut%={pfr_nut:.0%} ({diff:.0%}). '
            f'{pfr_pos} should avoid overbets — caller can re-raise with their nuts.'
        )
    else:
        reason = (
            f'Neutral nut advantage on {board_h}-high {board_type} board. '
            f'PFR nut%={pfr_nut:.0%} vs caller nut%={caller_nut:.0%}. '
            f'Avoid large overbets; neither side dominates the nut range.'
        )

    # Tips
    tips = []
    if flush_possible and advantage == 'pfr' and height != 'low':
        tips.append(
            f'Flush board with PFR nut advantage: {pfr_pos} has AXs, KXs → top flushes. '
            f'Caller has medium flushes. PFR can overbet-jam flush-completing rivers '
            f'since caller is dominated by top flush and can\'t call off.'
        )
    if straight_possible and advantage == 'caller' and height == 'low':
        tips.append(
            f'Low straight board: {caller_pos} has many suited connectors that complete. '
            f'PFR should check-call rather than bet into caller\'s superior straight range. '
            f'Avoid building large pots as PFR without strong holdings.'
        )
    if board_paired and advantage == 'pfr':
        tips.append(
            f'Paired board: {pfr_pos} has pocket pairs → full houses. '
            f'On {board_h}-paired boards, PFR should bet small to keep caller in '
            f'with second-best hands, then escalate on later streets.'
        )
    if advantage != 'neutral' and magnitude >= 0.60:
        holder_name = pfr_pos if advantage == 'pfr' else caller_pos
        tips.append(
            f'Strong nut advantage ({magnitude:.0%}) for {holder_name}: '
            f'exploit with river overbets ({ob_size}). '
            f'Balance with some bluffs at the same sizing for maximum EV.'
        )
    if advantage == 'neutral':
        tips.append(
            'No clear nut advantage: use standard sizing (60-75% pot). '
            'Overbets from either side are risky — villain can call or raise with nuts.'
        )

    return NutAdvantageResult(
        pfr_pos=pfr_pos,
        caller_pos=caller_pos,
        board_high=board_h,
        board_height=height,
        board_type=board_type,
        board_paired=board_paired,
        flush_possible=flush_possible,
        straight_possible=straight_possible,
        pfr_nut_pct=pfr_nut,
        caller_nut_pct=caller_nut,
        nut_diff=diff,
        nut_advantage=advantage,
        advantage_magnitude=magnitude,
        should_overbet=should_ob,
        overbet_size=ob_size,
        defender_strategy=defender,
        reasoning=reason,
        tips=tips,
    )


def nut_advantage_one_liner(result: NutAdvantageResult) -> str:
    adv = result.nut_advantage.upper()
    ob = result.should_overbet.upper()
    return (
        f'[NUT {result.pfr_pos}v{result.caller_pos}|{result.board_high}-{result.board_type}] '
        f'adv={adv}({result.advantage_magnitude:.0%}) | '
        f'pfr_nut={result.pfr_nut_pct:.0%} caller_nut={result.caller_nut_pct:.0%} | '
        f'overbet={ob}'
    )
