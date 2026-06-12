"""
Protection Betting Guide (protection_betting_guide.py)

Protection betting = betting a made hand to deny free cards to draws.
Distinct from pure value betting (wants calls) and bluffing (wants folds).
Protection bet = BOTH: deny equity AND extract value from worse made hands.

THEORY:
  WHAT IS PROTECTION BETTING?
  When you hold a made hand (TPTK, overpair) on a draw-heavy board, a free
  card is dangerous: villain improves and beats you. A protection bet forces
  villain to pay to chase their draw -- if pot odds are bad, they fold.
  Protection is a REASON to bet, not a separate action category.

  PROTECTION NEED BY HAND:
  - Top pair / overpair on wet board: HIGH protection need
  - Sets / two pair on draw board: LOW (can survive runouts; strong enough)
  - Middle pair: LOW (already lost to many cards; protection not enough)
  - Draws (you): NONE (you ARE the draw; protection is villain's concern)

  PROTECTION SIZING:
  Larger than thin-value sizing; need to charge draws sufficiently.
  Rule: Make drawing mathematically incorrect.
  Flush draw equity = ~35%; need pot odds worse than 35%:
    Required sizing: bet > 0.54x pot (makes pot odds < 35% for flush draw)
  Combo draw equity = ~55%; need bet > 1.22x pot to deny equity.

  PROTECTION VS VALUE:
  Protection sizing is often identical to value sizing -- they overlap.
  The key insight is the REASON to bet: you're protecting AND extracting.
  vs Villain who calls any 2 cards (fish): protection is automatic (they call)
  vs Tight villain: protection adds fold equity (draws fold correctly)

  WHEN NOT TO PROTECT:
  - Very strong hand (set) doesn't need protection; even if draw hits, you win
  - Dry board: few draws to protect against
  - When protection sizing would be an overbet revealing your hand strength
  - Short SPR: commitment is more important than protection

DISTINCT FROM:
  draw_protection.py:         Draw-specific protection calculations
  bet_sizing.py:              General sizing guide
  thin_value_betting.py:      Thin value betting
  THIS MODULE:                PROTECTION BETTING CONCEPT; when protection
                              is the primary motive; sizing to deny equity;
                              hand/board conditions where protection applies.
"""

from dataclasses import dataclass, field
from typing import List


DRAW_DENSITY_BY_TEXTURE: dict = {
    'dry':      0.10,
    'semi_wet': 0.28,
    'wet':      0.45,
    'monotone': 0.60,
    'paired':   0.18,
}

DRAW_EQUITY_ESTIMATES: dict = {
    'flush_draw':   0.35,
    'oesd':         0.32,
    'combo_draw':   0.55,
    'gutshot':      0.17,
    'backdoor_flushdraw': 0.12,
    'none':         0.05,
}

PROTECTION_NEED_BY_HAND: dict = {
    'top_pair_gk':  'high',
    'top_pair_wk':  'medium',
    'overpair':     'high',
    'middle_pair':  'low',
    'bottom_pair':  'none',
    'two_pair':     'medium',
    'set':          'low',
    'strong_value': 'low',
    'nuts':         'none',
    'flush_draw':   'none',
    'oesd':         'none',
    'air':          'none',
}

PROTECTION_SIZING_FLOOR: dict = {
    'high':   0.65,
    'medium': 0.50,
    'low':    0.35,
    'none':   0.00,
}

VILLAIN_PROTECTION_MODIFIER: dict = {
    'fish':            -0.12,
    'calling_station': -0.15,
    'rec':             -0.06,
    'nit':             +0.08,
    'lag':             +0.06,
    'reg':             0.00,
}

TEXTURE_PROTECTION_MULTIPLIER: dict = {
    'dry':      0.60,
    'semi_wet': 0.85,
    'wet':      1.15,
    'monotone': 1.30,
    'paired':   0.75,
}


def _min_sizing_to_deny(draw_equity: float) -> float:
    if draw_equity <= 0.0:
        return 0.0
    # caller needs pot_odds < draw_equity -> call/(pot+call) < draw_equity
    # bet/pot > (draw_equity / (1 - draw_equity))
    ratio = draw_equity / (1.0 - draw_equity)
    return round(ratio, 2)


def _protection_sizing(
    hand_category: str,
    board_texture: str,
    villain_type: str,
    draw_type: str = 'flush_draw',
) -> float:
    need = PROTECTION_NEED_BY_HAND.get(hand_category, 'low')
    floor_size = PROTECTION_SIZING_FLOOR.get(need, 0.35)
    draw_eq = DRAW_EQUITY_ESTIMATES.get(draw_type, 0.30)
    min_deny = _min_sizing_to_deny(draw_eq)
    base = max(floor_size, min_deny)
    vil_mod = VILLAIN_PROTECTION_MODIFIER.get(villain_type, 0.00)
    tex_mult = TEXTURE_PROTECTION_MULTIPLIER.get(board_texture, 1.00)
    final = round(min(1.50, (base + vil_mod) * tex_mult), 2)
    return max(0.25, final)


def _protection_verdict(
    hand_category: str,
    board_texture: str,
    villain_type: str,
    spr: float,
    sizing: float,
    need: str,
) -> str:
    if need == 'none':
        return 'NO_PROTECTION_NEEDED'
    if spr < 1.5:
        return 'BET_COMMIT_SPR_LOW'
    if villain_type in ('fish', 'calling_station') and need == 'low':
        return 'BET_VALUE_PROTECTION_AUTOMATIC'
    if need == 'high' and board_texture in ('wet', 'monotone'):
        return 'BET_PROTECTION_MANDATORY'
    if need == 'medium':
        return 'BET_PROTECTION_RECOMMENDED'
    return 'BET_PROTECTION_OPTIONAL'


@dataclass
class ProtectionBettingResult:
    hand_category: str
    board_texture: str
    villain_type: str
    spr: float
    draw_type: str

    protection_need: str
    recommended_sizing: float
    min_deny_sizing: float
    draw_equity: float
    draw_density: float
    verdict: str

    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_protection_betting(
    hand_category: str = 'top_pair_gk',
    board_texture: str = 'wet',
    villain_type: str = 'reg',
    spr: float = 5.0,
    draw_type: str = 'flush_draw',
) -> ProtectionBettingResult:
    """
    Determine protection betting need, sizing, and urgency.

    Args:
        hand_category:  Hero hand category
        board_texture:  Board texture ('dry','semi_wet','wet','monotone','paired')
        villain_type:   Villain type ('fish','rec','nit','lag','reg')
        spr:            Stack-to-pot ratio
        draw_type:      Primary draw type on board ('flush_draw','oesd','combo_draw','gutshot','none')

    Returns:
        ProtectionBettingResult
    """
    need = PROTECTION_NEED_BY_HAND.get(hand_category, 'low')
    sizing = _protection_sizing(hand_category, board_texture, villain_type, draw_type)
    draw_eq = DRAW_EQUITY_ESTIMATES.get(draw_type, 0.30)
    min_deny = _min_sizing_to_deny(draw_eq)
    density = DRAW_DENSITY_BY_TEXTURE.get(board_texture, 0.25)
    verdict = _protection_verdict(hand_category, board_texture, villain_type, spr, sizing, need)

    reasoning = (
        f'Protection betting: {hand_category} on {board_texture} board. '
        f'Draw type={draw_type} (equity={draw_eq:.0%}; min deny sizing={min_deny:.0%}pot). '
        f'Draw density={density:.0%}. '
        f'Protection need={need}. '
        f'Villain={villain_type} (modifier={VILLAIN_PROTECTION_MODIFIER.get(villain_type, 0.0):+.0%}). '
        f'Recommended sizing={sizing:.0%}pot. '
        f'Verdict: {verdict}.'
    )

    tips = []

    tips.append(
        f'PROTECTION NEED ({need.upper()}): {hand_category} on {board_texture} board vs {draw_type}. '
        f'Draw equity={draw_eq:.0%}; density={density:.0%}. '
        f'{"Protection is critical -- bet to deny free cards." if need == "high" else "Some protection value -- consider sizing up." if need == "medium" else "Protection not primary concern -- other factors dominate." if need == "low" else "No protection needed -- check or bet for other reasons."}'
    )

    tips.append(
        f'SIZING: Recommend {sizing:.0%} pot ({verdict}). '
        f'Min to deny {draw_type} ({draw_eq:.0%} equity): {min_deny:.0%} pot. '
        f'{"Your sizing correctly denies draw odds." if sizing >= min_deny else "WARNING: sizing does NOT deny draw equity -- villain has correct pot odds to call."}'
    )

    if villain_type in ('fish', 'calling_station'):
        tips.append(
            f'VS {villain_type.upper()}: Protection is automatic -- {villain_type} calls regardless. '
            f'Reduce protection sizing slightly ({VILLAIN_PROTECTION_MODIFIER[villain_type]:+.0%}); focus on VALUE extraction. '
            f'Bet for value first; protection is a bonus vs sticky players.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT: Nit folds draws correctly to good sizing. '
            f'Protection works well (+{VILLAIN_PROTECTION_MODIFIER["nit"]:.0%} to sizing). '
            f'Larger sizing extracts from nit value hands AND folds their draws.'
        )

    if board_texture == 'monotone':
        tips.append(
            f'MONOTONE BOARD: {density:.0%} draw density -- all unpaired hands have flush draws. '
            f'Protection is URGENT: size at {sizing:.0%} pot minimum. '
            f'Check only with strong hands that can survive a flush completing.'
        )

    return ProtectionBettingResult(
        hand_category=hand_category,
        board_texture=board_texture,
        villain_type=villain_type,
        spr=spr,
        draw_type=draw_type,
        protection_need=need,
        recommended_sizing=sizing,
        min_deny_sizing=min_deny,
        draw_equity=draw_eq,
        draw_density=density,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pbg_one_liner(r: ProtectionBettingResult) -> str:
    return (
        f'[PBG {r.hand_category}|{r.board_texture}|{r.draw_type}] '
        f'need={r.protection_need} size={r.recommended_sizing:.0%}pot deny={r.min_deny_sizing:.0%}pot'
    )
