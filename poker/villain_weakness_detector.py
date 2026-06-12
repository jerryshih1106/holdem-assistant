"""
Villain Weakness Detector (villain_weakness_detector.py)

Detects weakness signals in villain's in-hand behavior and recommends
exploitative bluff/semi-bluff opportunities.

THEORY:
  Weak players telegraph weakness with specific in-hand behaviors:
  1. Check-check: villain missed or is weak; high probability of fold to bet
  2. Under-size bet: bet < 33% pot often indicates a blocking bet (weak)
  3. Immediate call without tank: often top pair or draws, rarely nuts
  4. Long tank then call: often borderline hand; may fold to second barrel
  5. Bet-fold pattern (previously showed): scared of raises; probe raises work
  6. Timing tells: quick check = weakness; quick bet = strength or autobetting

  Exploitability depends on:
  - Stack depth (SPR affects fold equity)
  - Position (IP can bluff more efficiently)
  - Board texture (dry boards: more fold equity; wet boards: less)
  - Hand history at table (have they shown big hand recently?)
  - Number of streets of weakness signaled

WEAKNESS SIGNALS (in priority order):
  1. bet_fold_history:      Bet then folded to raise earlier; respect raises
  2. check_check_multiway:  Checked multiple times = air or weak
  3. tiny_bet_sizing:       Bet < 33% pot = blocking bet; rarely strong
  4. long_tank_call:        Called after long tank = borderline; may fold to pressure
  5. immediate_call:        Quick call = draw or top pair; possible second barrel
  6. single_check:          Checked once; moderate weakness

BLUFF RECOMMENDATION:
  Based on weakness score (0-10):
  - Score 8+: high-confidence bluff (0.7 pot or larger)
  - Score 5-7: moderate bluff (0.5 pot)
  - Score 3-4: small probe bet (0.33 pot)
  - Score < 3: no bluff

DISTINCT FROM:
  session_exploit_tracker.py:  Session-level pattern detection (multi-hand)
  bayesian_villain_model.py:   Bayesian range estimation
  bluff_advisor.py:            General bluff frequency advice
  THIS MODULE:                 IN-HAND, REAL-TIME weakness detection;
                               specific behavior signals THIS hand;
                               immediate bluff recommendation with sizing.
"""

from dataclasses import dataclass, field
from typing import List, Dict


# Weakness signals and their base scores (higher = more exploitable)
WEAKNESS_SIGNALS: Dict[str, int] = {
    'bet_fold_history':       9,
    'check_check_multiway':   8,
    'tiny_bet_sizing':        7,
    'long_tank_call':         6,
    'double_check':           7,
    'single_check':           4,
    'immediate_call':         3,
    'min_bet':                8,
    'limp_call_preflop':      5,
    'passive_call_station':   4,
}

# Board texture fold equity modifier
BOARD_FOLD_EQUITY: Dict[str, float] = {
    'dry':      1.20,   # dry = high fold equity for bluffs
    'medium':   1.00,
    'wet':      0.75,   # wet = draws justify calling
    'paired':   1.10,
    'monotone': 0.85,
}

# Position modifier for bluff EV
POSITION_BLUFF_MODIFIER: Dict[str, float] = {
    'ip':  1.15,
    'oop': 0.85,
}

# Optimal bluff sizing by weakness score
BLUFF_SIZE_BY_SCORE: Dict[str, float] = {
    'high':   0.75,   # score >= 8
    'medium': 0.50,   # score 5-7
    'probe':  0.33,   # score 3-4
    'none':   0.00,   # score < 3
}


def _weakness_score(signals: list) -> int:
    """Compute composite weakness score from observed signals."""
    if not signals:
        return 0
    scores = [WEAKNESS_SIGNALS.get(s, 0) for s in signals]
    base = max(scores)  # primary signal
    bonus = sum(sorted(scores)[:-1]) // 4  # diminishing returns for additional signals
    return min(10, base + bonus)


def _bluff_tier(score: int) -> str:
    if score >= 8:
        return 'high'
    elif score >= 5:
        return 'medium'
    elif score >= 3:
        return 'probe'
    else:
        return 'none'


def _adjusted_fold_equity(
    base_score: int,
    board_texture: str,
    hero_position: str,
    villain_af: float,
) -> float:
    board_mod = BOARD_FOLD_EQUITY.get(board_texture, 1.0)
    pos_mod = POSITION_BLUFF_MODIFIER.get(hero_position, 1.0)
    # Aggressive villains fold less; passive villains may call down
    if villain_af >= 3.0:
        af_mod = 0.80  # aggressive: may raise/call bluffs more
    elif villain_af < 1.5:
        af_mod = 1.10  # passive: may just fold; but also call with anything
    else:
        af_mod = 1.00
    raw_fold_eq = (base_score / 10.0) * board_mod * pos_mod * af_mod
    return round(min(0.90, max(0.05, raw_fold_eq)), 3)


def _bluff_ev(
    pot_bb: float,
    bet_size_frac: float,
    fold_equity: float,
    hero_equity_if_called: float,
) -> float:
    bet_bb = pot_bb * bet_size_frac
    ev_fold = fold_equity * pot_bb
    ev_called = (1.0 - fold_equity) * (hero_equity_if_called * (pot_bb + 2 * bet_bb) - bet_bb)
    return round(ev_fold + ev_called, 2)


@dataclass
class WeaknessDetectionResult:
    weakness_signals: list
    weakness_score: int
    bluff_tier: str
    board_texture: str
    hero_position: str
    villain_af: float

    adjusted_fold_equity: float
    recommended_bluff_size: float
    bluff_bet_bb: float
    bluff_ev_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def detect_villain_weakness(
    weakness_signals: list = None,
    board_texture: str = 'dry',
    hero_position: str = 'ip',
    villain_af: float = 2.0,
    pot_bb: float = 20.0,
    hero_equity_if_called: float = 0.30,
    hero_hand_category: str = 'air',
) -> WeaknessDetectionResult:
    """
    Detect villain weakness and compute bluff recommendation.

    Args:
        weakness_signals:       List of weakness signal keys observed
        board_texture:          Board texture
        hero_position:          'ip' / 'oop'
        villain_af:             Villain's aggression factor
        pot_bb:                 Current pot in BB
        hero_equity_if_called:  Hero's equity if bluff is called
        hero_hand_category:     Hero's hand category (affects semi-bluff logic)

    Returns:
        WeaknessDetectionResult
    """
    if weakness_signals is None:
        weakness_signals = []

    score = _weakness_score(weakness_signals)
    tier = _bluff_tier(score)
    fold_eq = _adjusted_fold_equity(score, board_texture, hero_position, villain_af)
    bluff_size_frac = BLUFF_SIZE_BY_SCORE.get(tier, 0.0)
    bluff_bb = round(pot_bb * bluff_size_frac, 1)
    bev = _bluff_ev(pot_bb, bluff_size_frac, fold_eq, hero_equity_if_called) if tier != 'none' else 0.0

    is_semi_bluff = hero_hand_category in ('flush_draw', 'oesd', 'gutshot', 'combo_draw')
    bluff_label = 'SEMI_BLUFF' if is_semi_bluff else ('BLUFF' if tier != 'none' else 'NO_BLUFF')

    verdict = (
        f'[VWD {"|".join(weakness_signals[:2]) if weakness_signals else "none"}|{board_texture}|{hero_position}] '
        f'{bluff_label} | score={score}/10 fold_eq={fold_eq:.0%} | ev={bev:+.1f}BB'
    )

    reasoning = (
        f'Weakness signals: {weakness_signals}. Score: {score}/10. '
        f'Tier: {tier}. Board: {board_texture}. Position: {hero_position}. '
        f'Villain AF: {villain_af:.1f}. '
        f'Fold equity: {fold_eq:.0%}. '
        f'Recommended bluff: {bluff_size_frac:.0%} pot = {bluff_bb:.1f}BB. '
        f'EV: {bev:+.1f}BB.'
    )

    tips = []

    if not weakness_signals:
        tips.append(
            f'NO WEAKNESS SIGNALS: No exploitable tells detected. '
            f'Bluff only with strong draw or range advantage on {board_texture} board.'
        )
    else:
        primary = weakness_signals[0]
        tips.append(
            f'PRIMARY SIGNAL: {primary} (score contribution: {WEAKNESS_SIGNALS.get(primary, 0)}/10). '
            f'Total weakness score: {score}/10. Tier: {tier.upper()}. '
            f'{"HIGH-CONFIDENCE BLUFF: villain very likely to fold." if tier == "high" else "MODERATE BLUFF: villain may call; need equity backup." if tier == "medium" else "SMALL PROBE: test villain; easy to fold if raised." if tier == "probe" else "NO BLUFF RECOMMENDED."}'
        )

    tips.append(
        f'FOLD EQUITY: {fold_eq:.0%} on {board_texture} board {hero_position.upper()}. '
        f'{"High fold equity -- bluff profitably." if fold_eq >= 0.55 else "Moderate fold equity -- semi-bluff preferred." if fold_eq >= 0.40 else "Low fold equity -- prefer check/value bet."} '
        f'Villain AF={villain_af:.1f}: {"fights back vs bluffs." if villain_af >= 3.0 else "may call passively." if villain_af < 1.5 else "standard response."}'
    )

    if tier != 'none':
        tips.append(
            f'BLUFF RECOMMENDATION: Bet {bluff_size_frac:.0%} pot = {bluff_bb:.1f}BB. '
            f'EV = {bev:+.1f}BB (fold_eq={fold_eq:.0%}, eq_if_called={hero_equity_if_called:.0%}). '
            f'{"Positive EV bluff -- execute." if bev > 0 else "Negative EV bluff -- consider checking."}'
        )
        if is_semi_bluff:
            tips.append(
                f'SEMI-BLUFF ({hero_hand_category}): Extra equity if called. '
                f'Combining {fold_eq:.0%} fold equity + draw equity = profitable. '
                f'If raised: call pot-sized raises; fold to 3x overbet.'
            )

    return WeaknessDetectionResult(
        weakness_signals=weakness_signals,
        weakness_score=score,
        bluff_tier=tier,
        board_texture=board_texture,
        hero_position=hero_position,
        villain_af=villain_af,
        adjusted_fold_equity=fold_eq,
        recommended_bluff_size=bluff_size_frac,
        bluff_bet_bb=bluff_bb,
        bluff_ev_bb=bev,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def vwd_one_liner(r: WeaknessDetectionResult) -> str:
    return (
        f'[VWD score={r.weakness_score}/10|{r.bluff_tier}] '
        f'fold_eq={r.adjusted_fold_equity:.0%} | '
        f'bet={r.bluff_bet_bb:.1f}BB | ev={r.bluff_ev_bb:+.1f}BB'
    )
