"""
Donk Bet Advisor (donk_bet_advisor.py)

Advises when to LEAD (donk bet) into the preflop raiser out-of-position,
rather than check-calling or check-folding.

THEORY:
  A DONK BET is an out-of-position lead into the preflop raiser.
  Commonly viewed as "bad" by novices, but GTO analysis shows specific
  spots where donk betting is the highest-EV line.

  WHEN DONK BETTING IS CORRECT:
  1. OOP RANGE ADVANTAGE: Board connects better with OOP range
     - Low, paired, or connected boards (e.g. 2-3-4, 7-7-J) hit BB/SB
       defending range better than PFR's raising range
     - The more connected/low the board, the more OOP can donk
  2. DRAW PROTECTION: OOP has a strong draw and wants to charge villain
     rather than give a free card or face a large c-bet
  3. VALUE WITH TRAPPING INVERSE: Hero has strong hand but board is
     dry (villain will often check back); lead to build pot
  4. RANGE POLARIZATION: OOP has strong value hands + draws (polarized);
     check-raising range is smaller; donk allows more combos to play

  WHEN NOT TO DONK BET:
  1. Board heavily favors PFR range (A-high, Broadway, over-pair boards)
  2. OOP range is merged/weak-topped (no nut advantage)
  3. Check-raise is better (when villain c-bets very frequently)
  4. OOP is against a very wide c-bet villain (let them bluff, then x/r)

  DONK SIZING:
  - Standard: 25-40% pot (blocking bet / value extraction vs. wide villain)
  - Large: 60-75% pot (strong value; protect draw; build pot)
  - Depends on: board texture, hand strength, range advantage

  BOARD TEXTURE SCORING FOR DONK BETS (0-10):
  - Low board (all cards <= 9): +4 (OOP range connects better)
  - Connected board (2-gap or closer): +3
  - Paired board: +2 (OOP defends suited/connected; hits pair more)
  - Dry board (rainbow, no draw): +1 (check-raise might be better)
  - High board (A/K/Q top cards): -4 (PFR's range smashes this)

DISTINCT FROM:
  range_cbet.py:    C-bet from position
  probe_bet.py:     Turn probe after flop checks through
  check_raise_ev.py: Check-raise analysis
  THIS MODULE:      DONK BET from OOP; range advantage scoring;
                    board texture vs. PFR range; sizing; hand selection.
"""

from dataclasses import dataclass, field
from typing import List


# Board texture donk advantage score
def _board_donk_score(board_texture: str, top_card_rank: int) -> int:
    score = 0
    if top_card_rank <= 9:
        score += 4
    elif top_card_rank <= 11:  # T/J
        score += 1
    else:
        score -= 4  # A/K/Q board: PFR favored

    if board_texture in ('connected', 'two_tone', 'monotone'):
        score += 3
    elif board_texture in ('paired', 'double_paired'):
        score += 2
    elif board_texture == 'dry':
        score += 0

    return max(-5, min(10, score))


def _oop_range_advantage(hero_hand: str, board_texture: str, top_card_rank: int) -> float:
    """Estimate OOP range advantage (0.0-1.0) for donk betting."""
    advantage = 0.5
    if top_card_rank <= 7:
        advantage += 0.25
    elif top_card_rank <= 9:
        advantage += 0.10
    else:
        advantage -= 0.20

    if board_texture in ('connected', 'monotone'):
        advantage += 0.10
    elif board_texture == 'paired':
        advantage += 0.05

    if hero_hand in ('set', 'two_pair', 'combo_draw', 'oesd', 'flush_draw'):
        advantage += 0.05
    elif hero_hand in ('top_pair', 'overpair'):
        advantage -= 0.05

    return round(min(0.90, max(0.10, advantage)), 2)


def _donk_sizing(
    hand_strength: str,
    range_advantage: float,
    board_donk_score: int,
) -> float:
    if hand_strength in ('set', 'two_pair', 'nuts', 'flush', 'straight', 'full_house'):
        if range_advantage >= 0.65:
            return 0.70  # large donk: build pot with value
        return 0.55
    elif hand_strength in ('combo_draw', 'oesd', 'flush_draw'):
        return 0.50  # protect draw
    elif hand_strength in ('top_pair', 'overpair'):
        return 0.35  # thin value / blocking bet
    else:
        return 0.30  # weak/air; small blocking donk in polarized spot


def _donk_verdict(range_advantage: float, donk_score: int, hero_hand: str) -> str:
    if donk_score >= 5 and range_advantage >= 0.65:
        return 'STRONG_DONK'
    elif donk_score >= 3 and range_advantage >= 0.55:
        return 'DONK_BET'
    elif donk_score >= 1 and range_advantage >= 0.50:
        return 'MARGINAL_DONK'
    elif range_advantage < 0.45:
        return 'CHECK_RAISE_OR_CALL'
    else:
        return 'CHECK_FIRST'


@dataclass
class DonkBetResult:
    hero_hand: str
    board_texture: str
    top_card_rank: int
    donk_score: int
    range_advantage: float
    optimal_size_frac: float
    optimal_bet_bb: float
    recommendation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_donk_bet(
    hero_hand: str = 'top_pair',
    board_texture: str = 'connected',
    top_card_rank: int = 7,
    pot_bb: float = 12.0,
    position_vs_pfr: str = 'oop',
    pfr_cbet_pct: float = 0.65,
    street: str = 'flop',
) -> DonkBetResult:
    """
    Advise on donk betting from OOP.

    Args:
        hero_hand:        Hero's hand category
        board_texture:    Board texture ('dry','connected','two_tone','monotone','paired')
        top_card_rank:    Highest card rank on board (2-14)
        pot_bb:           Pot size in BB
        position_vs_pfr:  Should be 'oop' (donk is always OOP)
        pfr_cbet_pct:     Villain's c-bet frequency
        street:           Street ('flop' / 'turn')

    Returns:
        DonkBetResult
    """
    donk_score = _board_donk_score(board_texture, top_card_rank)
    range_adv = _oop_range_advantage(hero_hand, board_texture, top_card_rank)
    size = _donk_sizing(hero_hand, range_adv, donk_score)
    bet_bb = round(pot_bb * size, 1)
    rec = _donk_verdict(range_adv, donk_score, hero_hand)

    rank_str = {14: 'A', 13: 'K', 12: 'Q', 11: 'J', 10: 'T'}.get(top_card_rank, str(top_card_rank))

    verdict = (
        f'[DNK {hero_hand}|{board_texture}|top={rank_str}] '
        f'{rec} | size={size:.0%}pot={bet_bb:.1f}BB | '
        f'range_adv={range_adv:.0%} score={donk_score}'
    )

    reasoning = (
        f'Donk bet analysis: OOP with {hero_hand}. '
        f'Board: {board_texture}, top card {rank_str} (rank={top_card_rank}). '
        f'Donk score: {donk_score}/10. OOP range advantage: {range_adv:.0%}. '
        f'PFR c-bet%: {pfr_cbet_pct:.0%}. '
        f'Recommendation: {rec}. Optimal size: {size:.0%}pot = {bet_bb:.1f}BB.'
    )

    tips = []

    if rec in ('STRONG_DONK', 'DONK_BET'):
        tips.append(
            f'DONK BET: {size:.0%}pot = {bet_bb:.1f}BB. '
            f'OOP range advantage={range_adv:.0%} on this {board_texture} board. '
            f'Donk score={donk_score}: low/connected boards favor BB/SB defending ranges.'
        )
    elif rec == 'MARGINAL_DONK':
        tips.append(
            f'MARGINAL DONK: Consider donk only with strong value ({hero_hand}). '
            f'Check-raise may be better if villain c-bets {pfr_cbet_pct:.0%}+ of flops.'
        )
    else:
        tips.append(
            f'NO DONK: Range advantage only {range_adv:.0%} (below threshold). '
            f'Check-call or check-raise is better vs. villain c-bet {pfr_cbet_pct:.0%}.'
        )

    if top_card_rank >= 12:
        tips.append(
            f'HIGH BOARD (top={rank_str}): PFR range connects strongly with A/K/Q boards. '
            f'Donk betting here gives up range advantage. '
            f'Check-call with your made hands; check-raise with nutted holdings.'
        )
    elif top_card_rank <= 7:
        tips.append(
            f'LOW BOARD (top={rank_str}): BB/SB calling ranges include many low-card hands. '
            f'OOP has range advantage here -- donk is a strong play with value/draws.'
        )

    if pfr_cbet_pct >= 0.70:
        tips.append(
            f'VILLAIN C-BETS {pfr_cbet_pct:.0%}: High c-bet villain. '
            f'Consider check-raising to counter their frequency. '
            f'Donk still good with strong value to prevent "free" c-bet at your range.'
        )

    if hero_hand in ('combo_draw', 'oesd', 'flush_draw'):
        tips.append(
            f'DRAW PROTECTION: Donk {size:.0%}pot charges villain to see turn. '
            f'Avoids facing large c-bet with semi-bluff that has reverse implied odds. '
            f'Also builds pot when hero is favorite to hit.'
        )

    return DonkBetResult(
        hero_hand=hero_hand,
        board_texture=board_texture,
        top_card_rank=top_card_rank,
        donk_score=donk_score,
        range_advantage=range_adv,
        optimal_size_frac=size,
        optimal_bet_bb=bet_bb,
        recommendation=rec,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def dnk_one_liner(r: DonkBetResult) -> str:
    return (
        f'[DNK {r.hero_hand}|top={r.top_card_rank}] '
        f'{r.recommendation} {r.optimal_size_frac:.0%}pot={r.optimal_bet_bb:.1f}BB '
        f'range_adv={r.range_advantage:.0%}'
    )
