"""
Range Advantage Quantifier (range_advantage_quantifier.py)

Quantifies which player has a range advantage on a given board and how large
that advantage is. Range advantage drives many GTO decisions:
  - Player with range advantage should bet more often
  - Player with range disadvantage should check more, defend less

RANGE ADVANTAGE THEORY:
  Range advantage has two components:
  1. NUT ADVANTAGE: Who has more combos of the strongest hands (sets, flushes)?
  2. DENSITY ADVANTAGE: Who has more hands that interact well with the board?

  PREFLOP RANGES AND BOARD INTERACTION:
  BTN RFI vs BB Defend:
    BTN range: ~48% of hands (all suited aces, broadway, pairs, connectors)
    BB range: ~40% of hands (wide defense: pairs, suited, some offsuit)
    On A-K-J: BTN has more AK, AJ, AA, KK -> nut advantage
    On 7-2-2: BB has more 77, 22, 72s (defended vs BTN steal) -> BB has nut adv

  KEY INSIGHT: Position of the PREFLOP AGGRESSOR matters.
    Aggressor's range: top-heavy (big pairs, big aces)
    Defender's range: wider, more speculative (pairs, suited connectors)
    On HIGH boards (A,K,Q high): aggressor has range advantage
    On LOW boards (2-3-7): defender has range advantage (called with low pairs)

  BOARD TEXTURE AND RANGE INTERACTION:
    Ace-high: aggressor has strong range adv (AK, AA, AQs common in open range)
    King-high: moderate aggressor advantage
    Connected low (J-9-7): defender's range has more connectors and pairs
    Paired (8-8-3): aggressor holds more overpairs; mixed advantage
    Monotone: aggressor's suited high cards connect better

  QUANTIFICATION SCALE (1-10):
    10: Massive aggressor advantage (A-K-Q board vs BTN-BB)
    7-9: Significant advantage
    5-6: Slight advantage or neutral
    3-4: Slight defender advantage
    1-2: Strong defender advantage (low connected board)

DISTINCT FROM:
  range_equity.py:        Range vs range equity calculation
  ip_range_protector.py:  How to protect your range
  board_texture.py:       Board texture classification
  THIS MODULE:            Who has RANGE ADVANTAGE; score 1-10;
                          which player has more strong hands relative
                          to their range; how it affects strategy.

Usage:
    from poker.range_advantage_quantifier import quantify_range_advantage, RangeAdvantage, raq_one_liner

    result = quantify_range_advantage(
        aggressor_position='btn',
        defender_position='bb',
        board_high_card=14,   # Ace
        board_mid_card=10,
        board_low_card=7,
        board_texture='dry',
        is_paired_board=False,
        is_monotone=False,
    )
    print(raq_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Board high card ranges: high = aggressor advantage; low = defender advantage
HIGH_CARD_ADVANTAGE_SCORE = {
    14: +4,   # Ace: very strong aggressor advantage
    13: +3,   # King
    12: +2,   # Queen
    11: +1,   # Jack: slight advantage
    10:  0,   # Ten: neutral
    9:  -1,   # Nine
    8:  -2,   # Eight: slight defender advantage
    7:  -2,
    6:  -3,
    5:  -3,
    4:  -3,
    3:  -4,   # Low boards: defender's calling range has more pairs
    2:  -4,
}

# Connectivity score: connected boards favor defender (more connectors in range)
CONNECTIVITY_SCORE = {
    'monotone': +1,     # high cards = slight aggressor advantage on flush boards
    'semi_wet': -1,     # some connectivity; defender's connectors interact
    'wet':      -2,     # connected board; defender's range strong
    'dry':      +1,     # disconnected; aggressor's top pairs dominate
    'paired':    0,     # aggressor has overpairs; neutral
}

# Position pair advantage adjustments
BTN_RANGE_STRENGTH = 0.48   # BTN opens ~48% of hands (wide)
BB_DEFENSE_WIDTH = 0.40     # BB defends ~40% (wide but weaker)
UTG_RANGE_STRENGTH = 0.13   # UTG opens tight (top 13%)


def _high_card_score(board_high_card: int, board_mid_card: int) -> int:
    """Score based on board high and mid cards."""
    high_score = HIGH_CARD_ADVANTAGE_SCORE.get(min(board_high_card, 14), 0)
    mid_score = HIGH_CARD_ADVANTAGE_SCORE.get(min(board_mid_card, 14), 0)
    return high_score + mid_score // 2


def _range_advantage_score(
    aggressor_position: str,
    defender_position: str,
    board_high_card: int,
    board_mid_card: int,
    board_low_card: int,
    board_texture: str,
    is_paired_board: bool,
    is_monotone: bool,
) -> int:
    """Raw score: positive = aggressor advantage; negative = defender advantage."""
    score = 0

    # High card impact
    score += _high_card_score(board_high_card, board_mid_card)

    # Texture impact
    texture = 'monotone' if is_monotone else board_texture
    score += CONNECTIVITY_SCORE.get(texture, 0)

    # Position adjustment: tight positions have tighter ranges = more high card hands
    if aggressor_position in ('utg', 'utg1', 'utg2'):
        if board_high_card >= 12:
            score += 1   # UTG range even more biased to high cards
        else:
            score -= 1   # UTG range has fewer low pairs that defend

    # Paired board: overpairs (aggressor) vs trips (defender's wider range)
    if is_paired_board:
        if board_low_card <= 7:
            score -= 1   # defender defends more low pairs; easier to hit trips
        else:
            score += 1   # high pair: aggressor's overpairs stay ahead

    # BB vs BTN: BB defense is wide (lots of 2x range)
    if defender_position == 'bb' and aggressor_position == 'btn':
        if board_high_card <= 8:
            score -= 2   # BB defends many low pairs; massive defender advantage on low boards

    return score


def _normalize_score(raw: int) -> int:
    """Convert raw score to 1-10 scale (5 = neutral; 10 = max aggressor; 1 = max defender)."""
    normalized = 5 + raw
    return max(1, min(10, normalized))


def _range_advantage_label(score_1_10: int) -> str:
    if score_1_10 >= 8:
        return 'massive_aggressor_advantage'
    elif score_1_10 >= 6:
        return 'moderate_aggressor_advantage'
    elif score_1_10 == 5:
        return 'neutral'
    elif score_1_10 >= 3:
        return 'moderate_defender_advantage'
    else:
        return 'massive_defender_advantage'


def _who_has_advantage(score_1_10: int, aggressor_position: str, defender_position: str) -> str:
    if score_1_10 >= 6:
        return aggressor_position
    elif score_1_10 <= 4:
        return defender_position
    return 'neutral'


def _betting_frequency_recommendation(
    score_1_10: int,
    is_aggressor: bool,
) -> float:
    """Recommended betting frequency (0.0-1.0) given range advantage."""
    if is_aggressor:
        base = 0.55
        adjustment = (score_1_10 - 5) * 0.05
    else:
        base = 0.35
        adjustment = (5 - score_1_10) * 0.05   # defender bets more when they have advantage
    return round(min(0.85, max(0.15, base + adjustment)), 2)


@dataclass
class RangeAdvantage:
    # Inputs
    aggressor_position: str
    defender_position: str
    board_high_card: int
    board_mid_card: int
    board_low_card: int
    board_texture: str
    is_paired_board: bool
    is_monotone: bool

    # Analysis
    raw_score: int            # negative = defender adv; positive = aggressor adv
    score_1_to_10: int        # 1=max defender, 10=max aggressor, 5=neutral
    advantage_label: str
    who_has_advantage: str    # position name or 'neutral'
    aggressor_bet_freq: float # recommended aggressor bet frequency
    defender_bet_freq: float  # recommended defender bet/donk frequency

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def quantify_range_advantage(
    aggressor_position: str = 'btn',
    defender_position: str = 'bb',
    board_high_card: int = 14,
    board_mid_card: int = 10,
    board_low_card: int = 7,
    board_texture: str = 'dry',
    is_paired_board: bool = False,
    is_monotone: bool = False,
) -> RangeAdvantage:
    """
    Quantify range advantage on a given board.

    Args:
        aggressor_position: Preflop aggressor position
        defender_position:  Preflop caller/defender position
        board_high_card:    Value of highest card (2-14; Ace=14)
        board_mid_card:     Value of middle card
        board_low_card:     Value of lowest card
        board_texture:      'dry' / 'wet' / 'semi_wet' / 'monotone'
        is_paired_board:    Whether board has a pair
        is_monotone:        Whether all three cards same suit

    Returns:
        RangeAdvantage
    """
    raw = _range_advantage_score(
        aggressor_position, defender_position,
        board_high_card, board_mid_card, board_low_card,
        board_texture, is_paired_board, is_monotone
    )
    score = _normalize_score(raw)
    label = _range_advantage_label(score)
    who = _who_has_advantage(score, aggressor_position, defender_position)
    agg_freq = _betting_frequency_recommendation(score, True)
    def_freq = _betting_frequency_recommendation(score, False)

    card_str = f'{board_high_card}/{board_mid_card}/{board_low_card}'
    verdict = (
        f'[RAQ {aggressor_position}vs{defender_position}|{card_str}] '
        f'score={score}/10 {label} | '
        f'advantage={who} agg_bet={agg_freq:.0%}'
    )

    reasoning = (
        f'Range advantage: {aggressor_position} (aggressor) vs {defender_position} (defender) '
        f'on {card_str} board ({board_texture}). '
        f'Raw score: {raw:+d}. Normalized: {score}/10. '
        f'Label: {label}. '
        f'Who has advantage: {who}. '
        f'Recommended bet freq: aggressor={agg_freq:.0%}, defender={def_freq:.0%}.'
    )

    tips = []

    tips.append(
        f'RANGE ADVANTAGE SCORE: {score}/10 ({label}). '
        f'Board {card_str}: high cards favor aggressor ({aggressor_position}); '
        f'low boards favor defender ({defender_position}) who called with wider range. '
        f'Score > 5: {aggressor_position} should bet more. '
        f'Score < 5: {defender_position} can donk/check-raise more.'
    )

    tips.append(
        f'BETTING FREQUENCY ADJUSTMENT: '
        f'{aggressor_position} (aggressor): bet {agg_freq:.0%} (GTO base=55%). '
        f'{defender_position} (defender): lead/donk {def_freq:.0%} (GTO base=35%). '
        f'Key insight: {"Bet wide as aggressor -- range advantage justifies it." if score >= 7 else ""}' +
        f'{"Check-raise or donk more as defender -- you have range advantage." if score <= 3 else ""}'
    )

    if board_high_card == 14:  # Ace-high board
        tips.append(
            f'ACE-HIGH BOARD: Aggressor ({aggressor_position}) has strong range advantage. '
            f'Aggressor\'s RFI range is top-heavy (AK, AQ, AJ, AA, KK). '
            f'Defender\'s range has some Ax but fewer combos. '
            f'Result: aggressor can cbet at high frequency ({agg_freq:.0%}) on ace-high boards.'
        )
    elif board_high_card <= 7:
        tips.append(
            f'LOW BOARD ({card_str}): Defender ({defender_position}) has range advantage. '
            f'Defender\'s wide calling range includes many low pairs and connectors. '
            f'Aggressor\'s tight range missed more often. '
            f'Result: defender can check-raise/donk frequently; aggressor should cbet less.'
        )

    if is_monotone:
        tips.append(
            f'MONOTONE BOARD: Mixed range effects. '
            f'Both players have suited hands, but aggressor\'s suited aces/kings interact better. '
            f'Defender has more off-suit hands = more missed boards. '
            f'Aggressor retains moderate advantage on monotone boards.'
        )

    return RangeAdvantage(
        aggressor_position=aggressor_position,
        defender_position=defender_position,
        board_high_card=board_high_card,
        board_mid_card=board_mid_card,
        board_low_card=board_low_card,
        board_texture=board_texture,
        is_paired_board=is_paired_board,
        is_monotone=is_monotone,
        raw_score=raw,
        score_1_to_10=score,
        advantage_label=label,
        who_has_advantage=who,
        aggressor_bet_freq=agg_freq,
        defender_bet_freq=def_freq,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def raq_one_liner(r: RangeAdvantage) -> str:
    cards = f'{r.board_high_card}/{r.board_mid_card}/{r.board_low_card}'
    return (
        f'[RAQ {r.aggressor_position}vs{r.defender_position}|{cards}] '
        f'score={r.score_1_to_10}/10 {r.advantage_label} | '
        f'agg_bet={r.aggressor_bet_freq:.0%}'
    )
