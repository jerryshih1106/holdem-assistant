"""
Board Pairing Advantage Analyzer (board_pairing_advantage.py)

Analyzes the range advantage shift when the BOARD PAIRS on the turn or river.
A paired board changes who benefits from the new card and how aggressively
each player should bet.

THEORY:
  BOARD PAIRING = a card on the turn/river matches a flop card.
  Example: Flop A-7-3; Turn 7 = board pairs the 7.

  WHO BENEFITS FROM BOARD PAIRING:

  1. PAIRING A HIGH CARD (A, K, Q):
     - PFR's range contains more top-pair/two-pair/trips combos
     - Defender's range is weakened (their top pair becomes two pair if they called)
     - NET: PFR (in-position) gains range advantage
     - Example: A-K-Q flop, turn A: PFR has more AA, AK hands; BB rarely has A in range

  2. PAIRING A LOW CARD (2-7):
     - BB/SB calling range contains many low-card combos (22/33/72/63 type hands)
     - PFR's pre-flop raising range has fewer low-card combos
     - NET: Defender (OOP) gains range advantage on low paired boards
     - Example: 7-5-3 flop, turn 3: BB has 33/43/63 more than BTN opener

  3. PAIRING A MIDDLE CARD (8-J):
     - Neutral; both ranges can have pairs
     - Slight PFR advantage if c-betting range was strong

  STRATEGIC IMPLICATIONS:
  1. OOP player: When board pairs a low card they called with, LEAD more often
     (range advantage justifies donk bet or lead)
  2. IP player: When high card pairs, continue aggression; PFR's range is ahead
  3. DRAW DEVALUATION: All flush draws now have reverse implied odds on paired boards
     (sets full up; straight draws also weaker)
  4. PAIR-BLOCKING: Hands that block the paired card are more valuable as bluffs
     (if holding the J when J pairs, villain has fewer trips)

  ADVANTAGE SCORE (0-10):
  0-3: Defender gains (OOP range advantage on paired low card)
  4-6: Neutral (middle card pairs; balanced)
  7-10: PFR gains (high card pairs; IP/PFR range ahead)

DISTINCT FROM:
  turn_runout_analysis.py:  General turn card classification
  range_board_texture.py:   Board texture vs. range analysis
  THIS MODULE:              BOARD PAIRING SPECIFIC; paired-card rank effects;
                            who gains range advantage; strategic adjustments needed.
"""

from dataclasses import dataclass, field
from typing import List


# Advantage score adjustment by paired card rank and role
def _pairing_advantage_score(
    paired_rank: int,
    hero_is_pfr: bool,
    position: str,
) -> float:
    """
    Return hero's advantage score (0-10) from board pairing.
    5.0 = neutral. >5 = hero benefits. <5 = villain benefits.
    """
    # PFR benefit: high cards pair well with PFR range
    if paired_rank >= 12:  # Q, K, A
        pfr_advantage = 7.5
        defender_advantage = 2.5
    elif paired_rank >= 10:  # T, J
        pfr_advantage = 6.0
        defender_advantage = 4.0
    elif paired_rank >= 8:  # 8, 9
        pfr_advantage = 5.5
        defender_advantage = 4.5
    elif paired_rank >= 5:  # 5, 6, 7
        pfr_advantage = 3.5
        defender_advantage = 6.5
    else:  # 2, 3, 4
        pfr_advantage = 2.5
        defender_advantage = 7.5

    if hero_is_pfr:
        base = pfr_advantage
    else:
        base = defender_advantage

    # Position modifier
    if position == 'ip':
        base = min(10.0, base + 0.5)
    else:
        base = max(0.0, base - 0.5)

    return round(base, 1)


def _draw_devaluation(board_texture: str, paired_rank: int) -> float:
    """How much flush/straight draws are devalued by the board pairing (0-1)."""
    if board_texture in ('two_tone', 'monotone'):
        return 0.30  # draws devalued significantly when board pairs
    elif board_texture == 'dry':
        return 0.10
    return 0.20


def _strategic_adjustment(
    hero_is_pfr: bool,
    advantage_score: float,
    paired_rank: int,
    hero_hand: str,
) -> str:
    if advantage_score >= 7.0:
        if hero_is_pfr:
            return 'CONTINUE_AGGRESSION_STRONG_ADVANTAGE'
        else:
            return 'CHECK_CALL_RANGE_VULNERABLE'
    elif advantage_score >= 5.5:
        if hero_hand in ('trips', 'full_house', 'two_pair'):
            return 'BET_VALUE_NORMAL'
        return 'CHECK_OR_BET_NORMAL'
    elif advantage_score >= 4.0:
        return 'PROCEED_CAUTIOUSLY'
    else:
        if not hero_is_pfr:
            return 'LEAD_OR_DONK_RANGE_ADVANTAGE'
        return 'CHECK_OFTEN_RANGE_WEAK'


@dataclass
class BoardPairingResult:
    paired_card: str
    paired_rank: int
    hero_is_pfr: bool
    position: str
    board_texture: str
    hero_hand: str

    advantage_score: float
    hero_benefits: bool
    draw_devaluation: float
    strategic_adjustment: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_board_pairing(
    paired_card: str = '7',
    hero_is_pfr: bool = True,
    position: str = 'ip',
    board_texture: str = 'dry',
    hero_hand: str = 'top_pair',
    pot_bb: float = 20.0,
    street: str = 'turn',
) -> BoardPairingResult:
    """
    Analyze range advantage when the board pairs.

    Args:
        paired_card:    The card that paired (e.g. '7', 'A', 'K', 'T')
        hero_is_pfr:    True if hero was the preflop raiser
        position:       Hero's position ('ip' / 'oop')
        board_texture:  Original board texture before pairing
        hero_hand:      Hero's hand category
        pot_bb:         Current pot in BB
        street:         Street when pairing occurs ('turn' / 'river')

    Returns:
        BoardPairingResult
    """
    rank_map = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
                'T':10,'J':11,'Q':12,'K':13,'A':14}
    paired_rank = rank_map.get(paired_card.upper(), rank_map.get(paired_card, 7))

    adv_score = _pairing_advantage_score(paired_rank, hero_is_pfr, position)
    hero_benefits = adv_score >= 5.0
    draw_deval = _draw_devaluation(board_texture, paired_rank)
    s_adj = _strategic_adjustment(hero_is_pfr, adv_score, paired_rank, hero_hand)

    rank_name = {14:'A',13:'K',12:'Q',11:'J',10:'T'}.get(paired_rank, str(paired_rank))

    verdict = (
        f'[BPA {rank_name}{rank_name}|{position}|{"PFR" if hero_is_pfr else "DEF"}] '
        f'adv={adv_score:.0f}/10 {"HERO+" if hero_benefits else "VILLAIN+"} | '
        f'{s_adj}'
    )

    reasoning = (
        f'Board pairing: {rank_name} pairs on {street}. '
        f'Hero is {"PFR" if hero_is_pfr else "defender"} in {position.upper()}. '
        f'Advantage score: {adv_score:.0f}/10 (higher = hero benefits). '
        f'Board texture: {board_texture}. Draw devaluation: {draw_deval:.0%}. '
        f'Strategic adjustment: {s_adj}.'
    )

    tips = []

    if hero_benefits:
        tips.append(
            f'HERO BENEFITS from {rank_name}{rank_name} pairing (score={adv_score:.0f}/10). '
            f'{"PFR range has more " + rank_name + " combos." if hero_is_pfr else "Defender range has more low-card combinations."} '
            f'{"Continue with aggression." if hero_is_pfr else "Lead or donk; range advantage justifies leading."}'
        )
    else:
        tips.append(
            f'VILLAIN BENEFITS from {rank_name}{rank_name} pairing (score={adv_score:.0f}/10). '
            f'{"Defender range hits paired low cards more." if hero_is_pfr else "PFR range improved."} '
            f'Slow down; check more often; avoid bloating pot without equity.'
        )

    tips.append(
        f'STRATEGY: {s_adj.replace("_", " ")}. '
        f'Advantage score={adv_score:.0f}/10; '
        f'{"hero gains from this runout" if hero_benefits else "hero loses relative equity on this paired board"}.'
    )

    if paired_rank >= 12:
        tips.append(
            f'HIGH CARD PAIRS ({rank_name}): PFR range contains more {rank_name}-high hands. '
            f'{"Bet aggressively; villain is out of trips combos." if hero_is_pfr else "Pot-control; PFR likely has trips advantage."}'
        )
    elif paired_rank <= 6:
        tips.append(
            f'LOW CARD PAIRS ({rank_name}): BB/SB defending range hits this card more. '
            f'{"Check often; villain has pairs of {0}." if hero_is_pfr else "Consider leading; you have range advantage."}'.format(rank_name)
        )

    if draw_deval >= 0.25:
        tips.append(
            f'DRAW DEVALUATION: Flush/straight draws reduced in value by {draw_deval:.0%}. '
            f'Paired board means opponent may now have two pair or better. '
            f'Semi-bluffs with draws less attractive; value bet or check/fold more.'
        )

    if hero_hand in ('trips', 'full_house'):
        tips.append(
            f'STRONG HAND ON PAIRED BOARD: {hero_hand} is very strong. '
            f'Board pairing creates action; villain may have two pair or trips. '
            f'Value bet aggressively; villain may not be able to fold their pair.'
        )
    elif hero_hand in ('air', 'missed_draw') and hero_benefits:
        tips.append(
            f'BLUFFING OPPORTUNITY: Hero has range advantage (score={adv_score:.0f}/10). '
            f'Even with air ({hero_hand}), board pairing means villain\'s medium hands are weaker. '
            f'Represent trips; villain with one pair may fold.'
        )

    return BoardPairingResult(
        paired_card=rank_name,
        paired_rank=paired_rank,
        hero_is_pfr=hero_is_pfr,
        position=position,
        board_texture=board_texture,
        hero_hand=hero_hand,
        advantage_score=adv_score,
        hero_benefits=hero_benefits,
        draw_devaluation=draw_deval,
        strategic_adjustment=s_adj,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bpa_one_liner(r: BoardPairingResult) -> str:
    return (
        f'[BPA {r.paired_card}|{"PFR" if r.hero_is_pfr else "DEF"}|{r.position}] '
        f'adv={r.advantage_score:.0f}/10 {"HERO+" if r.hero_benefits else "VILLAIN+"} '
        f'{r.strategic_adjustment}'
    )
