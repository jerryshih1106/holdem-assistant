"""
Range Betting Guide (range_betting_guide.py)

Range bet = betting your ENTIRE range (or near-entire range) on a board,
as opposed to a mixed strategy where some hands bet and others check.
Optimal when your range has a significant equity advantage on the board.

THEORY:
  WHEN TO RANGE BET:
  Range betting is profitable when:
  1. You have a large range advantage (your range hits the board much harder)
  2. Board is dry (no flush/straight draws to balance with checks)
  3. You're IP (easier to realize your range advantage)
  4. Villain's range is capped (they can't have strong hands)
  5. Villain's range is wide (BB defense has many weak hands)

  RANGE ADVANTAGE DEFINITION:
  Range advantage = how much of your range connects with the board vs villain's.
  Example: BTN opens, BB defends. On A-7-2 rainbow:
  - BTN (opener) hits A-x heavily (Ax in range); BB has lots of air
  - BTN has ~65% range equity on this board
  - BTN should range bet small (33% pot) to exploit

  WHEN NOT TO RANGE BET:
  - Wet boards: your draws need to sometimes check for balance (prevent over-folding when you check)
  - Even range equity (50/50): should mix bet/check
  - OOP: position loss hurts; checking back more often protects
  - Villain has strong range (3-bet pot, ep vs ep): villain can have strong hands too

  RANGE BET SIZING:
  - Dry board range bet: 25-33% pot (villain can't continue; extract thin value)
  - Semi-wet range bet: 33-40% pot
  - Wet board (if range betting): 45-55% pot

  POLARIZED vs RANGE BET:
  Range bet = often small sizing (merge value and bluffs together)
  Polarized = large sizing (differentiate strong/weak; bluffs at top of range)
  Use range bet when you have a density advantage; polarized when you have nut advantage.

DISTINCT FROM:
  bet_sizing.py:              General bet sizing
  cbet_frequency_auditor.py:  Checking c-bet frequency
  multiway_cbet_frequency_guide.py: Multiway c-bet guide
  THIS MODULE:                RANGE BET CONCEPT specifically; when entire range
                              should bet; range advantage threshold; sizing by texture.
"""

from dataclasses import dataclass, field
from typing import List


RANGE_ADVANTAGE_BASELINE: dict = {
    'btn_vs_bb': {'dry': 0.67, 'semi_wet': 0.57, 'wet': 0.47, 'monotone': 0.42, 'paired': 0.62},
    'co_vs_bb':  {'dry': 0.62, 'semi_wet': 0.54, 'wet': 0.44, 'monotone': 0.40, 'paired': 0.57},
    'mp_vs_bb':  {'dry': 0.58, 'semi_wet': 0.52, 'wet': 0.43, 'monotone': 0.41, 'paired': 0.54},
    'utg_vs_bb': {'dry': 0.55, 'semi_wet': 0.50, 'wet': 0.42, 'monotone': 0.40, 'paired': 0.52},
    'sb_vs_bb':  {'dry': 0.53, 'semi_wet': 0.50, 'wet': 0.45, 'monotone': 0.43, 'paired': 0.51},
    'default':   {'dry': 0.55, 'semi_wet': 0.52, 'wet': 0.46, 'monotone': 0.44, 'paired': 0.53},
}

RANGE_BET_THRESHOLD: float = 0.58

RANGE_BET_SIZING: dict = {
    'dry':      0.28,
    'semi_wet': 0.37,
    'wet':      0.50,
    'monotone': 0.45,
    'paired':   0.30,
}

MIXED_SIZING: dict = {
    'dry':      0.50,
    'semi_wet': 0.55,
    'wet':      0.65,
    'monotone': 0.60,
    'paired':   0.55,
}

VILLAIN_RANGE_MODIFIER: dict = {
    'fish':            +0.05,
    'calling_station': +0.03,
    'rec':             +0.03,
    'nit':             -0.05,
    'lag':             -0.03,
    'reg':             0.00,
}

POSITION_RANGE_MODIFIER: dict = {
    'ip':  +0.03,
    'oop': -0.06,
}


def _range_advantage(
    scenario: str,
    board_texture: str,
    villain_type: str,
    position: str,
) -> float:
    baseline = RANGE_ADVANTAGE_BASELINE.get(scenario, RANGE_ADVANTAGE_BASELINE['default'])
    base = baseline.get(board_texture, 0.52)
    vil_mod = VILLAIN_RANGE_MODIFIER.get(villain_type, 0.00)
    pos_mod = POSITION_MODIFIER.get(position, 0.00)
    return round(min(0.85, max(0.30, base + vil_mod + pos_mod)), 3)


POSITION_MODIFIER = POSITION_RANGE_MODIFIER


def _range_bet_decision(
    range_adv: float,
    board_texture: str,
    position: str,
) -> str:
    if position == 'oop' and board_texture in ('wet', 'monotone'):
        return 'CHECK_RANGE_OOP_WET'
    if range_adv >= RANGE_BET_THRESHOLD + 0.08:
        return 'RANGE_BET_STRONG'
    if range_adv >= RANGE_BET_THRESHOLD:
        return 'RANGE_BET_RECOMMENDED'
    if range_adv >= 0.52:
        return 'MIXED_STRATEGY_LEAN_BET'
    if range_adv >= 0.48:
        return 'MIXED_STRATEGY_BALANCED'
    return 'CHECK_RANGE_DISADVANTAGE'


def _recommended_sizing(decision: str, board_texture: str) -> float:
    if 'RANGE_BET' in decision:
        return RANGE_BET_SIZING.get(board_texture, 0.35)
    elif 'MIXED' in decision:
        return MIXED_SIZING.get(board_texture, 0.55)
    return 0.0


@dataclass
class RangeBettingResult:
    scenario: str
    board_texture: str
    villain_type: str
    position: str

    range_advantage: float
    threshold: float
    decision: str
    recommended_sizing: float
    should_range_bet: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_range_betting(
    scenario: str = 'btn_vs_bb',
    board_texture: str = 'dry',
    villain_type: str = 'reg',
    position: str = 'ip',
) -> RangeBettingResult:
    """
    Determine whether to range bet or use mixed strategy.

    Args:
        scenario:       Position matchup ('btn_vs_bb','co_vs_bb','utg_vs_bb',...)
        board_texture:  Board texture ('dry','semi_wet','wet','monotone','paired')
        villain_type:   Villain type ('fish','rec','nit','lag','reg')
        position:       Hero position ('ip','oop')

    Returns:
        RangeBettingResult
    """
    range_adv = _range_advantage(scenario, board_texture, villain_type, position)
    decision = _range_bet_decision(range_adv, board_texture, position)
    sizing = _recommended_sizing(decision, board_texture)
    should_rb = 'RANGE_BET' in decision

    verdict = (
        f'[RBG {scenario}|{board_texture}|{position}] '
        f'adv={range_adv:.0%} decision={decision} size={sizing:.0%}pot'
    )

    reasoning = (
        f'Range betting analysis: {scenario} on {board_texture} board ({position}). '
        f'Villain={villain_type}. '
        f'Range advantage={range_adv:.0%} (threshold={RANGE_BET_THRESHOLD:.0%}). '
        f'Decision={decision}. '
        f'Recommended sizing={sizing:.0%}pot.'
    )

    tips = []

    tips.append(
        f'RANGE ADVANTAGE: {range_adv:.0%} (threshold={RANGE_BET_THRESHOLD:.0%}). '
        f'Decision: {decision}. '
        f'{"Range bet your ENTIRE range at {:.0%} pot -- density advantage forces villain to fold weak hands.".format(sizing) if should_rb else "Mixed strategy -- some hands bet, some check to protect checking range." if "MIXED" in decision else "Check your range -- no density advantage; protect your checking range."}'
    )

    tips.append(
        f'SIZING: {"Range bet" if should_rb else "Mixed"} at {sizing:.0%} pot. '
        f'{"Small sizing (range bet): all hands have enough equity to bet thin." if sizing <= 0.35 else "Medium sizing: extract value from draws + medium hands." if sizing <= 0.55 else "Larger sizing: wet board needs to charge draws even in range bet."}'
        f' Board={board_texture} ({position.upper()}).'
    )

    if board_texture in ('wet', 'monotone') and position == 'oop':
        tips.append(
            f'OOP WET BOARD WARNING: Range betting OOP on {board_texture} is rarely optimal. '
            f'Check a significant portion to protect your checking range. '
            f'Without a checking range, villain exploits by raising your bets aggressively.'
        )
    elif board_texture == 'dry' and should_rb:
        tips.append(
            f'DRY BOARD RANGE BET: Optimal scenario -- {range_adv:.0%} range advantage. '
            f'Bet {sizing:.0%} pot with your entire range. '
            f'Villain has many air hands vs your Ax/Kx heavy range; small bet forces tough folds.'
        )

    if villain_type == 'nit' and range_adv < RANGE_BET_THRESHOLD:
        tips.append(
            f'VS NIT: Nit has stronger-than-average range (folds weak hands pre). '
            f'Range advantage reduced to {range_adv:.0%}. '
            f'Consider mixed strategy -- nit continues with strong hands regardless of sizing.'
        )

    return RangeBettingResult(
        scenario=scenario,
        board_texture=board_texture,
        villain_type=villain_type,
        position=position,
        range_advantage=range_adv,
        threshold=RANGE_BET_THRESHOLD,
        decision=decision,
        recommended_sizing=sizing,
        should_range_bet=should_rb,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rbg_one_liner(r: RangeBettingResult) -> str:
    return (
        f'[RBG {r.scenario}|{r.board_texture}|{r.position}] '
        f'adv={r.range_advantage:.0%} size={r.recommended_sizing:.0%}pot'
    )
