"""
Value Extraction Optimizer (value_extraction_optimizer.py)

Maximizing value from strong hands: when to slow-play (trap), fast-play
(bet immediately), or thin-bet (bet with medium strength expecting worse calls).

THEORY:
  FAST-PLAY vs SLOW-PLAY:
  Fast-play (bet): Extract value NOW; prevent free cards; build pot.
  Slow-play (check): Induce bluffs; disguise hand strength; let draws improve.

  WHEN TO FAST-PLAY:
  1. Board is draw-heavy (villain can outdraw you; give no free cards)
  2. SPR is low (commit stack quickly; no need to slow-play)
  3. Villain is passive (won't bluff; must bet to get value)
  4. Villain has top pair / two pair (they want to pay you off)

  WHEN TO SLOW-PLAY:
  1. Board is dry (villain's equity static; free cards harmless)
  2. SPR is high (need multiple streets; check to induce multi-street action)
  3. Villain is aggressive (will bet/bluff if checked to)
  4. Hand is strong enough that free cards rarely beat you (sets vs one draw)

  THIN VALUE BETTING:
  Bet with hands slightly better than villain's calling range.
  Example: TPTK bets into calling station expecting middle pair to call.
  Risk: occasionally dominated (kicker issue); reward: extract from calling range.

  VALUE SIZING:
  - vs thin value range: smaller sizing (50% pot); don't scare off worse hands
  - vs strong range: larger sizing (75-100% pot); extract maximum
  - vs calling station: any size works; bet as large as they'll call

DISTINCT FROM:
  thin_value_betting.py:      Thin value in specific spots
  flop_thin_value.py:         Flop thin value
  bet_sizing.py:              General sizing guide
  THIS MODULE:                VALUE EXTRACTION holistically; slow/fast/thin decision;
                              board/SPR/villain-based optimization.
"""

from dataclasses import dataclass, field
from typing import List


HAND_STRENGTH_FOR_SLOWPLAY: dict = {
    'nuts':         True,
    'strong_value': True,
    'two_pair':     False,
    'top_pair_gk':  False,
    'overpair':     False,
    'set':          True,
    'straight':     True,
    'flush':        True,
    'full_house':   True,
    'top_pair_wk':  False,
    'middle_pair':  False,
}

BOARD_SLOWPLAY_PENALTY: dict = {
    'dry':      +0.25,
    'semi_wet': +0.05,
    'wet':      -0.25,
    'monotone': -0.35,
    'paired':   +0.10,
}

VILLAIN_SLOWPLAY_MODIFIER: dict = {
    'fish':            -0.15,
    'calling_station': -0.20,
    'rec':             -0.08,
    'nit':             +0.15,
    'lag':             +0.20,
    'reg':              0.00,
}

SPR_SLOWPLAY_MODIFIER: dict = {
    'low':      -0.25,
    'medium':    0.00,
    'high':     +0.20,
    'very_high': +0.30,
}

VALUE_SIZING_BY_CALLER: dict = {
    'fish':            0.85,
    'calling_station': 0.90,
    'rec':             0.70,
    'nit':             0.55,
    'lag':             0.75,
    'reg':             0.65,
}

THIN_VALUE_SDV_THRESHOLD: float = 0.55
SLOWPLAY_SCORE_THRESHOLD: float = 0.55


def _spr_zone(spr: float) -> str:
    if spr < 2:
        return 'low'
    if spr < 6:
        return 'medium'
    if spr < 15:
        return 'high'
    return 'very_high'


def _slowplay_score(
    hand_category: str,
    board_texture: str,
    villain_type: str,
    spr: float,
) -> float:
    base = 0.50 if HAND_STRENGTH_FOR_SLOWPLAY.get(hand_category, False) else 0.20
    board_adj = BOARD_SLOWPLAY_PENALTY.get(board_texture, 0.00)
    vil_adj = VILLAIN_SLOWPLAY_MODIFIER.get(villain_type, 0.00)
    spr_zone = _spr_zone(spr)
    spr_adj = SPR_SLOWPLAY_MODIFIER.get(spr_zone, 0.00)
    score = base + board_adj + vil_adj + spr_adj
    return round(min(1.0, max(0.0, score)), 3)


def _value_decision(slowplay_score: float, hand_sdv: float, villain_type: str) -> str:
    if slowplay_score >= SLOWPLAY_SCORE_THRESHOLD:
        return 'SLOW_PLAY_CHECK'
    if hand_sdv >= 0.80:
        return 'FAST_PLAY_VALUE_BET'
    if hand_sdv >= THIN_VALUE_SDV_THRESHOLD:
        return 'THIN_VALUE_BET'
    return 'CHECK_CALL_MEDIUM'


def _recommended_sizing(decision: str, villain_type: str) -> float:
    if decision == 'SLOW_PLAY_CHECK':
        return 0.0
    base = VALUE_SIZING_BY_CALLER.get(villain_type, 0.65)
    if 'THIN' in decision:
        return round(base * 0.75, 2)
    return base


@dataclass
class ValueExtractionResult:
    hand_category: str
    board_texture: str
    villain_type: str
    spr: float
    hand_sdv: float

    slowplay_score: float
    decision: str
    recommended_sizing: float
    spr_zone: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_value_extraction(
    hand_category: str = 'set',
    board_texture: str = 'dry',
    villain_type: str = 'reg',
    spr: float = 8.0,
    hand_sdv: float = 0.90,
) -> ValueExtractionResult:
    """
    Optimize value extraction: slow-play vs fast-play vs thin-bet.

    Args:
        hand_category:  Hero hand category ('nuts','set','top_pair_gk',...)
        board_texture:  Board texture ('dry','semi_wet','wet','monotone','paired')
        villain_type:   Villain type ('fish','rec','nit','lag','reg')
        spr:            Stack-to-pot ratio
        hand_sdv:       Showdown value (0-1)

    Returns:
        ValueExtractionResult
    """
    sp_score = _slowplay_score(hand_category, board_texture, villain_type, spr)
    decision = _value_decision(sp_score, hand_sdv, villain_type)
    sizing = _recommended_sizing(decision, villain_type)
    spr_z = _spr_zone(spr)

    verdict = (
        f'[VEO {hand_category}|{board_texture}|{villain_type}] '
        f'sp_score={sp_score:.2f} decision={decision} size={sizing:.0%}pot'
    )

    reasoning = (
        f'Value extraction: {hand_category} (SDV={hand_sdv:.0%}) on {board_texture}, SPR={spr:.1f}. '
        f'Villain={villain_type}. Slow-play score={sp_score:.2f} (threshold={SLOWPLAY_SCORE_THRESHOLD:.2f}). '
        f'Decision={decision}. Recommended sizing={sizing:.0%}pot.'
    )

    tips = []

    tips.append(
        f'VALUE DECISION: {decision} (slow-play score={sp_score:.2f}). '
        f'{"Check to induce -- villain is aggressive / board is dry / SPR is high." if decision == "SLOW_PLAY_CHECK" else "Bet for full value -- wet board / passive villain / need to protect equity." if "FAST_PLAY" in decision else "Thin value bet -- medium strength hand; bet small to extract from weaker holdings." if "THIN" in decision else "Check-call -- medium strength; pot control."}'
    )

    tips.append(
        f'SIZING: {sizing:.0%} pot (vs {villain_type}). '
        f'{"Do not bet -- check to trap/induce." if sizing == 0 else "Larger sizing vs sticky villain." if sizing >= 0.80 else "Standard value sizing." if sizing >= 0.65 else "Smaller sizing -- thin value or face-up bet concern."}'
    )

    if decision == 'SLOW_PLAY_CHECK':
        bonus = VILLAIN_SLOWPLAY_MODIFIER.get(villain_type, 0.0)
        board_pen = BOARD_SLOWPLAY_PENALTY.get(board_texture, 0.0)
        tips.append(
            f'SLOW-PLAY JUSTIFIED: SPR={spr:.1f} ({spr_z}), board={board_texture} ({board_pen:+.0%}), '
            f'villain={villain_type} ({bonus:+.0%} for slowplay). '
            f'{"High SPR: check and induce multiple streets." if spr_z in ("high","very_high") else "Check to exploit villain aggression." if villain_type in ("lag","rec") else "Dry board: free card mostly harmless."}'
        )

    if villain_type in ('fish', 'calling_station'):
        tips.append(
            f'VS {villain_type.upper()}: Bet {VALUE_SIZING_BY_CALLER[villain_type]:.0%} pot -- {villain_type} calls wide. '
            f'Never slow-play vs {villain_type} -- they need to be bet into to pay off. '
            f'Value bet every street; do not give free cards to {villain_type}.'
        )

    return ValueExtractionResult(
        hand_category=hand_category,
        board_texture=board_texture,
        villain_type=villain_type,
        spr=spr,
        hand_sdv=hand_sdv,
        slowplay_score=sp_score,
        decision=decision,
        recommended_sizing=sizing,
        spr_zone=spr_z,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def veo_one_liner(r: ValueExtractionResult) -> str:
    return (
        f'[VEO {r.hand_category}|{r.board_texture}|{r.villain_type}] '
        f'sp={r.slowplay_score:.2f} {r.decision}'
    )
