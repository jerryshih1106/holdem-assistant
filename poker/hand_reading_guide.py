"""
Hand Reading Guide (hand_reading_guide.py)

Systematic framework for reading villain's hand street-by-street based on their
action sequence. Hand reading is the single most valuable skill in poker: knowing
what villain likely holds shapes every decision you make.

HAND READING THEORY:
  Start with villain's preflop action, which defines an initial range.
  Each subsequent action further narrows that range.
  Actions are Bayesian updates: P(hand | action) propto P(action | hand) * P(hand).

  PREFLOP RANGES:
    Open RFI:  ~25% (BTN) to ~10% (UTG); includes many marginal hands
    3-bet:     ~7-10%; value + bluffs polarized
    Cold call: ~15-20%; mostly connectors, pairs, suited broadway
    Limp:      ~35-50% (live); wide and weak

  FLOP ACTIONS:
    Bet-small (<35%):  polarized or merged (strong OR air); draws or strong made hands
    Bet-medium (35-65%): merged range; top pair and above + semi-bluffs
    Bet-large (>65%):  polarized; strong value or pure bluff
    Check:              wide range; can trap or give up; draws check-calling

  TURN ACTIONS AFTER FLOP BET:
    Turn-bet after bet: strong (triple barrel rare with air); usually strong value
    Turn-check after bet: gave up OR has showdown value (trap occasionally)

  TURN ACTIONS AFTER FLOP CHECK:
    Delayed cbet: picked up equity (draw hit) OR trapping strong hand OR probe
    Check-check: usually weak; marginal pairs, showdown value

  RIVER ACTIONS:
    Bet-large on river: strongly polarized (value or bluff); rarely medium
    Check-call: bluff-catcher; medium strength (won't fold, won't raise)
    Check-raise: very strong or stone cold bluff; rarely medium strength

  BETTING LINE PATTERNS:
    Bet-bet-bet: strong value (triple barrel value or bluff; rare bluff for most)
    Bet-check-bet: probe/block; often medium value or draw that missed
    Check-bet-bet: floated on flop; strong on later streets or semi-bluff
    Check-check-bet: often medium value (didn't like flop/turn; values river)
    Check-raise flop: strong (sets, two-pair) or semi-bluff draw
    Donk bet flop: (OOP) strong on connected board; often weak for most players

DISTINCT FROM:
  range_narrower.py:     Range equity narrowing tool
  villain_reads.py:      HUD-based villain read
  villain_patterns.py:   Villain tendency patterns
  THIS MODULE:           PROCESS guide for hand reading; action sequence ->
                         hand bucket mapping; confidence levels; tips for
                         reading specific patterns correctly.

Usage:
    from poker.hand_reading_guide import read_villain_hand, HandReadingGuide, hrg_one_liner

    result = read_villain_hand(
        preflop_action='open',
        villain_position='btn',
        flop_action='bet_medium',
        turn_action='bet',
        river_action='bet_large',
        board_texture='dry',
        villain_vpip=0.28,
        villain_af=2.5,
    )
    print(hrg_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List, Tuple


# Hand buckets from most to least likely for given line patterns
# Format: (bet_line, board_type) -> [likely_hand_buckets]
LINE_TO_HAND_MAP = {
    # Triple barrel
    ('bet_bet_bet', 'dry'):       ['top_pair', 'overpair', 'set', 'air_polarized'],
    ('bet_bet_bet', 'wet'):       ['set', 'two_pair', 'overpair', 'flush_draw_completed'],
    ('bet_bet_bet', 'monotone'): ['flush', 'overpair', 'air_polarized'],

    # Bet-check-bet (probe)
    ('bet_check_bet', 'dry'):     ['top_pair_medium', 'gutshot', 'air_polarized'],
    ('bet_check_bet', 'wet'):     ['missed_draw', 'top_pair', 'air_polarized'],

    # Check-bet-bet (delayed cbet)
    ('check_bet_bet', 'dry'):     ['set', 'two_pair', 'strong_top_pair', 'air_polarized'],
    ('check_bet_bet', 'wet'):     ['flush', 'straight', 'set', 'two_pair'],

    # Check-check-bet
    ('check_check_bet', 'dry'):   ['middle_pair', 'weak_top_pair', 'backdoor_made'],
    ('check_check_bet', 'wet'):   ['missed_draw', 'second_pair', 'weak_top_pair'],

    # Single bet only (flop)
    ('bet_check_check', 'dry'):   ['top_pair', 'overpair', 'air'],
    ('bet_check_check', 'wet'):   ['top_pair', 'missed_draw', 'semi_bluff_gave_up'],

    # Check entire way (showdown)
    ('check_check_check', 'dry'): ['weak_showdown', 'middle_pair', 'bottom_pair'],
    ('check_check_check', 'wet'): ['busted_draw', 'weak_pair', 'overcards'],

    # Bet-bet (two streets)
    ('bet_bet_check', 'dry'):     ['top_pair', 'overpair', 'gave_up_bluff'],
    ('bet_bet_check', 'wet'):     ['top_pair', 'missed_draw', 'strong_top_pair'],
}

# Preflop action -> range width (approximate % of hands)
PREFLOP_RANGE_WIDTH = {
    'open_utg':   0.12,
    'open_hj':    0.18,
    'open_co':    0.28,
    'open_btn':   0.45,
    'open_sb':    0.40,
    'three_bet':  0.08,
    'cold_call':  0.18,
    'limp':       0.45,
    'bb_check':   0.60,
    'open':       0.28,   # generic open
}

# River action to hand category mappings
RIVER_ACTION_BUCKETS = {
    'bet_large':    ['nuts', 'near_nuts', 'air_bluff'],
    'bet_medium':   ['strong_top_pair', 'overpair', 'semi_bluff'],
    'bet_small':    ['top_pair', 'middle_pair', 'block_bet'],
    'check_call':   ['top_pair', 'bluff_catcher', 'overpair'],
    'check_raise':  ['nuts', 'near_nuts', 'stone_cold_bluff'],
    'check_fold':   ['air', 'missed_draw', 'weak_pair'],
    'check':        ['showdown_value', 'weak_top_pair', 'air'],
}

# Confidence modifiers
AF_CONFIDENCE_BOOST = 0.10   # high AF villain => more reliable read
VPIP_CONFIDENCE_PENALTY = 0.05   # loose VPIP => wider range => less certain


def _build_line(flop_action: str, turn_action: str, river_action: str) -> str:
    """Compress three street actions into a line signature."""
    def _compress(action: str) -> str:
        a = action.lower()
        if 'bet' in a:
            return 'bet'
        elif 'raise' in a:
            return 'bet'  # treat raise as aggressive (bet)
        elif 'check' in a:
            return 'check'
        return 'check'

    f = _compress(flop_action)
    t = _compress(turn_action)
    r = _compress(river_action)
    return f'{f}_{t}_{r}'


def _normalize_texture(board_texture: str) -> str:
    t = board_texture.lower()
    if t in ('wet', 'monotone'):
        return 'wet'
    if t in ('dry', 'paired'):
        return 'dry'
    return 'dry'


def _lookup_hand_buckets(line: str, texture_norm: str) -> List[str]:
    key = (line, texture_norm)
    if key in LINE_TO_HAND_MAP:
        return LINE_TO_HAND_MAP[key]
    # fallback: texture-agnostic lookup
    for (l, _t), buckets in LINE_TO_HAND_MAP.items():
        if l == line:
            return buckets
    return ['unknown']


def _river_specific_bucket(river_action: str) -> List[str]:
    return RIVER_ACTION_BUCKETS.get(river_action.lower(), ['unknown'])


def _most_likely(buckets: List[str]) -> str:
    return buckets[0] if buckets else 'unknown'


def _confidence(
    buckets: List[str],
    villain_vpip: float,
    villain_af: float,
    preflop_action: str,
) -> float:
    base = 0.55
    if len(buckets) <= 2:
        base = 0.70
    elif len(buckets) >= 4:
        base = 0.45
    if villain_af >= 2.5:
        base += AF_CONFIDENCE_BOOST
    if villain_vpip >= 0.35:
        base -= VPIP_CONFIDENCE_PENALTY
    if preflop_action in ('three_bet', 'open_utg'):
        base += 0.05   # tighter preflop = more defined range
    return round(min(0.90, max(0.25, base)), 2)


def _preflop_range_description(preflop_action: str, villain_position: str) -> str:
    pos_key = f'open_{villain_position.lower()}'
    if preflop_action in ('open', 'rfi'):
        width = PREFLOP_RANGE_WIDTH.get(pos_key, 0.28)
        return f'Open-raise from {villain_position} (~{width:.0%} of hands)'
    elif preflop_action == 'three_bet':
        return 'Three-bet range (~8%): value (QQ+/AK) + bluffs (A5s/KQs)'
    elif preflop_action == 'cold_call':
        return 'Cold-call range (~18%): pairs, suited connectors, broadway'
    elif preflop_action == 'limp':
        return 'Limp range (~40-50%): wide and weak; any pair, any suited'
    return 'Unknown preflop action'


def _check_raise_warning(flop_action: str) -> bool:
    return 'raise' in flop_action.lower()


def _donk_warning(flop_action: str, villain_position: str) -> bool:
    return 'donk' in flop_action.lower() or (
        'bet' in flop_action.lower() and villain_position in ('bb', 'sb')
    )


@dataclass
class HandReadingGuide:
    # Inputs
    preflop_action: str
    villain_position: str
    flop_action: str
    turn_action: str
    river_action: str
    board_texture: str
    villain_vpip: float
    villain_af: float

    # Analysis
    line_signature: str           # e.g. 'bet_bet_bet'
    likely_hand_buckets: List[str]
    river_buckets: List[str]
    most_likely_hand: str
    confidence: float             # 0.0-0.90
    preflop_range_desc: str
    is_check_raise: bool
    is_donk_bet: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def read_villain_hand(
    preflop_action: str = 'open',
    villain_position: str = 'btn',
    flop_action: str = 'bet_medium',
    turn_action: str = 'bet',
    river_action: str = 'bet_large',
    board_texture: str = 'dry',
    villain_vpip: float = 0.28,
    villain_af: float = 2.5,
) -> HandReadingGuide:
    """
    Read villain's likely hand from their action sequence.

    Args:
        preflop_action:   'open' / 'three_bet' / 'cold_call' / 'limp'
        villain_position: Villain's position at table
        flop_action:      Action on flop (e.g. 'bet_medium', 'check', 'check_raise')
        turn_action:      Action on turn ('bet', 'check', 'raise')
        river_action:     Action on river ('bet_large', 'check_call', 'check_raise')
        board_texture:    'dry' / 'wet' / 'semi_wet' / 'monotone'
        villain_vpip:     Villain VPIP stat
        villain_af:       Villain AF stat

    Returns:
        HandReadingGuide
    """
    line = _build_line(flop_action, turn_action, river_action)
    texture_norm = _normalize_texture(board_texture)
    line_buckets = _lookup_hand_buckets(line, texture_norm)
    river_buckets = _river_specific_bucket(river_action)

    # Intersect line buckets with river buckets for refined read
    combined = [h for h in line_buckets if h in river_buckets]
    if not combined:
        combined = line_buckets  # fallback to line analysis

    most_likely = _most_likely(combined)
    conf = _confidence(combined, villain_vpip, villain_af, preflop_action)
    preflop_desc = _preflop_range_description(preflop_action, villain_position)
    is_cr = _check_raise_warning(flop_action)
    is_donk = _donk_warning(flop_action, villain_position)

    verdict = (
        f'[HRG {most_likely}|{line}|conf={conf:.0%}] '
        f'preflop={preflop_action} | '
        f'likely={"/".join(combined[:3])}'
    )

    reasoning = (
        f'Hand reading: villain {villain_position} ({preflop_action}). '
        f'Line: {line} on {board_texture} board. '
        f'Line analysis: {line_buckets}. '
        f'River action ({river_action}): {river_buckets}. '
        f'Combined most likely: {combined[:3]}. '
        f'Confidence: {conf:.0%} (VPIP={villain_vpip:.0%} AF={villain_af:.1f}).'
    )

    tips = []

    tips.append(
        f'PREFLOP RANGE: {preflop_desc}. '
        f'This gives villain a starting range. '
        f'Each postflop action narrows further. '
        f'VPIP={villain_vpip:.0%}: {"loose = wide range; reads less reliable" if villain_vpip >= 0.35 else "tight = narrow range; reads more reliable"}.'
    )

    tips.append(
        f'LINE ANALYSIS ({line}): Most likely holdings = {", ".join(line_buckets[:3])}. '
        f'River action ({river_action}) further suggests: {", ".join(river_buckets[:2])}. '
        f'Refined read: {most_likely} with {conf:.0%} confidence.'
    )

    if is_cr:
        tips.append(
            f'CHECK-RAISE ALERT: Flop check-raise is a STRONG signal. '
            f'For most recreational players: usually sets, two-pair, or strong draw. '
            f'Vs low AF (<1.5): almost always strong (not balanced). '
            f'Adjust: fold top pair, consider fold overpair unless spr is low.'
        )

    if is_donk:
        tips.append(
            f'DONK BET DETECTED: OOP bet into preflop aggressor. '
            f'Most recreational players donk with: weak pairs afraid of more bets, '
            f'strong hands (sets/two-pair) wanting action, or missed preflop draw. '
            f'Vs tight villain: usually strong. Vs loose villain: wide including bluffs.'
        )

    if river_action == 'check_raise':
        tips.append(
            f'RIVER CHECK-RAISE: Very strong signal. '
            f'99% of players check-raise river with: nuts, near-nuts, or stone cold bluff. '
            f'Almost never medium strength. '
            f'If villain is not an aggro LAG, fold to river CR with anything but nuts.'
        )
    elif river_action in ('bet_large', 'overbet'):
        tips.append(
            f'LARGE RIVER BET (or overbet): Polarized range -- very strong or bluff. '
            f'Key question: does villain balance? Low AF (<2.0) = usually value, not bluffs. '
            f'High AF (>3.0) = can have many bluffs. '
            f'Calling frequency: use MDF = pot/(pot+bet).'
        )
    elif river_action == 'check_call':
        tips.append(
            f'RIVER CHECK-CALL: Bluff-catching range -- medium strength. '
            f'Villain rules out: strong hands (would bet), air (would fold). '
            f'Most likely: top pair, overpair, or strong middle pair. '
            f'Do not bluff rivers when villain check-calls frequently.'
        )

    return HandReadingGuide(
        preflop_action=preflop_action,
        villain_position=villain_position,
        flop_action=flop_action,
        turn_action=turn_action,
        river_action=river_action,
        board_texture=board_texture,
        villain_vpip=villain_vpip,
        villain_af=villain_af,
        line_signature=line,
        likely_hand_buckets=line_buckets,
        river_buckets=river_buckets,
        most_likely_hand=most_likely,
        confidence=conf,
        preflop_range_desc=preflop_desc,
        is_check_raise=is_cr,
        is_donk_bet=is_donk,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hrg_one_liner(r: HandReadingGuide) -> str:
    return (
        f'[HRG {r.most_likely_hand}|{r.line_signature}] '
        f'conf={r.confidence:.0%} | '
        f'buckets={"/".join(r.likely_hand_buckets[:3])}'
    )
