"""
Isolation vs Overlimper Guide (iso_overlimper_guide.py)

When one or more players have limped ahead of you, deciding whether to ISO
raise, over-limp, or fold. This is DISTINCT from standard open-raise decisions
because the pot already has money and limp-callers change hand equity dynamics.

THEORY:
  ISO RAISE GOALS:
  1. Build pot with strong hands vs weak limper ranges
  2. Force out players behind (especially those who squeeze)
  3. Create HU or 2-way flop vs fish/rec limpers (higher EV)
  4. Isolate the weakest player in the field

  ISO RAISE SIZING:
  Standard rule: 3bb + 1bb per limper
  Example: 1 limper -> 4bb; 2 limpers -> 5bb; 3 limpers -> 6bb
  vs Sticky limpers (won't fold): add +1bb per limper beyond standard
  vs Late position: can go slightly larger (5bb single limp from BTN)
  vs Multiple limpers: if 4+ limpers, re-evaluate whether to ISO

  HAND REQUIREMENTS FOR ISO:
  - HU intent: need strong hand that plays well HU (Ax, KQs, JTs+, pairs)
  - Multiway intent: strong pairs, suited connectors with equity vs field
  - Position matters heavily (IP ISO much more profitable)

  LIMPER COUNT EFFECTS:
  1 limper:  ISO aggressively; near-standard ranges still profitable IP
  2 limpers: Tighten range 15-20%; pot will be multiway vs wider field
  3 limpers: Tighten further; often fold unless strong value or nuts
  4+ limpers: Mostly fold; occasionally over-limp with speculative hands

  LIMPER TYPE EFFECTS:
  Fish limper:   Wide ISO range; want to play HU vs fish
  Rec limper:    Moderate ISO range; profitable but not as wide
  Nit limper:    Narrow ISO range; nit limps strong value; caution
  LAG limper:    Be careful; LAG may have premium trap or squeeze behind

  OVER-LIMP CONDITIONS:
  - Speculative hands in MP with many limpers (22-55, suited connectors)
  - When ISO-raise would be too large (5+ limpers, not worth it)
  - OOP with marginal hands that need multiway equity

  SQUEEZE PRESSURE:
  Players still behind can squeeze; fold equity against hero's ISO reduced.
  Adjust ISO sizing upward when aggressive players remain behind.

DISTINCT FROM:
  iso_raise.py:              General isolation raise
  cold_call_squeeze_protection.py: Cold call squeeze risk
  preflop_open_frequency_guide.py: Open frequency
  THIS MODULE:                OVERLIMPER SPECIFIC; limper count adjustments;
                              sizing formula; hand threshold by limper count;
                              over-limp conditions; vs-fish-specific ISO ranges.
"""

from dataclasses import dataclass, field
from typing import List


ISO_BASE_SIZING_BB: dict = {
    1: 4.0,
    2: 5.0,
    3: 6.0,
    4: 7.5,
    5: 9.0,
}

LIMPER_STICKINESS_ADDON: dict = {
    'fish':   1.0,
    'rec':    0.5,
    'nit':    0.0,
    'lag':    0.5,
    'reg':    0.0,
}

IP_HAND_THRESHOLD_BY_LIMPERS: dict = {
    1: 0.55,
    2: 0.62,
    3: 0.70,
    4: 0.80,
}

OOP_HAND_THRESHOLD_BY_LIMPERS: dict = {
    1: 0.65,
    2: 0.72,
    3: 0.82,
    4: 0.90,
}

HAND_STRENGTH_ESTIMATE: dict = {
    'AA':   0.95,
    'KK':   0.92,
    'QQ':   0.88,
    'JJ':   0.83,
    'TT':   0.78,
    '99':   0.74,
    '88':   0.70,
    '77':   0.66,
    '66':   0.62,
    '55':   0.57,
    '44':   0.53,
    '33':   0.50,
    '22':   0.47,
    'AKs':  0.90,
    'AKo':  0.87,
    'AQs':  0.82,
    'AQo':  0.78,
    'AJs':  0.76,
    'KQs':  0.74,
    'ATs':  0.72,
    'KJs':  0.68,
    'QJs':  0.65,
    'JTs':  0.62,
    'T9s':  0.58,
    '98s':  0.55,
    '87s':  0.53,
    'A5s':  0.60,
    'A4s':  0.58,
    'AXo':  0.55,
    'KQo':  0.65,
}

LIMPER_ISO_EV_MULTIPLIER: dict = {
    'fish':   1.40,
    'rec':    1.15,
    'nit':    0.85,
    'lag':    0.90,
    'reg':    1.00,
}


def _iso_sizing(n_limpers: int, limper_type: str) -> float:
    base = ISO_BASE_SIZING_BB.get(min(n_limpers, 5), 9.0)
    addon = LIMPER_STICKINESS_ADDON.get(limper_type, 0.0) * min(n_limpers, 3)
    return round(base + addon, 1)


def _hand_score(hand: str) -> float:
    return HAND_STRENGTH_ESTIMATE.get(hand, 0.60)


def _iso_threshold(n_limpers: int, position: str) -> float:
    if position == 'ip':
        return IP_HAND_THRESHOLD_BY_LIMPERS.get(min(n_limpers, 4), 0.80)
    return OOP_HAND_THRESHOLD_BY_LIMPERS.get(min(n_limpers, 4), 0.90)


def _squeeze_risk(players_behind: int, aggressive_behind: bool) -> float:
    base = 0.07 * players_behind
    if aggressive_behind:
        base += 0.12
    return round(min(0.50, base), 3)


def _iso_ev(
    pot_before: float,
    iso_bb: float,
    hand_score: float,
    limper_type: str,
    squeeze_risk: float,
) -> float:
    multiplier = LIMPER_ISO_EV_MULTIPLIER.get(limper_type, 1.00)
    postflop_share = hand_score * (pot_before + iso_bb) * multiplier
    cost = iso_bb
    fold_equity_gain = (1.0 - hand_score) * pot_before * 0.45
    ev = ((1.0 - squeeze_risk) * (postflop_share + fold_equity_gain - cost)
          - squeeze_risk * iso_bb)
    return round(ev, 2)


def _iso_action(
    hand_score: float,
    threshold: float,
    n_limpers: int,
    squeeze_risk: float,
    iso_ev: float,
) -> str:
    if n_limpers >= 5:
        if hand_score >= 0.82:
            return 'ISO_RAISE_LARGE'
        return 'OVER_LIMP'
    if squeeze_risk >= 0.30 and hand_score < 0.80:
        return 'FOLD_SQUEEZE_RISK'
    if hand_score >= threshold + 0.10:
        return 'ISO_RAISE'
    if hand_score >= threshold:
        return 'ISO_RAISE_BORDERLINE'
    if hand_score >= threshold - 0.15 and n_limpers == 1:
        return 'OVER_LIMP'
    return 'FOLD'


@dataclass
class IsoOverlimperResult:
    hand: str
    n_limpers: int
    limper_type: str
    position: str

    hand_score: float
    iso_threshold: float
    iso_sizing_bb: float
    squeeze_risk: float
    iso_ev: float

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_iso_overlimper(
    hand: str = 'AJs',
    n_limpers: int = 1,
    limper_type: str = 'rec',
    position: str = 'ip',
    pot_bb: float = 3.5,
    players_behind: int = 2,
    aggressive_behind: bool = False,
) -> IsoOverlimperResult:
    """
    Analyze whether to ISO raise over a limper or over-limp/fold.

    Args:
        hand:             Hero hand string (e.g., 'AJs', 'KQo', 'TT')
        n_limpers:        Number of limpers before hero
        limper_type:      Dominant limper type ('fish','rec','nit','lag','reg')
        position:         Hero position ('ip'/'oop')
        pot_bb:           Current pot in BB (SB+BB + limpers; typically 1.5 + n_limpers)
        players_behind:   Players yet to act (for squeeze risk)
        aggressive_behind: True if at least one LAG/aggressive player is still behind

    Returns:
        IsoOverlimperResult
    """
    hs = _hand_score(hand)
    threshold = _iso_threshold(n_limpers, position)
    iso_bb = _iso_sizing(n_limpers, limper_type)
    sq_risk = _squeeze_risk(players_behind, aggressive_behind)
    ev = _iso_ev(pot_bb, iso_bb, hs, limper_type, sq_risk)

    action = _iso_action(hs, threshold, n_limpers, sq_risk, ev)

    verdict = (
        f'[ISO {hand}|{n_limpers}L|{limper_type}|{position}] '
        f'{action} size={iso_bb:.1f}BB EV={ev:+.1f}BB '
        f'score={hs:.2f}/threshold={threshold:.2f} sqz={sq_risk:.0%}'
    )

    reasoning = (
        f'ISO vs {n_limpers} limper(s) [{limper_type}] from {position}. '
        f'Hand={hand} score={hs:.2f} vs threshold={threshold:.2f}. '
        f'ISO size={iso_bb:.1f}BB. '
        f'Squeeze risk={sq_risk:.0%} (behind={players_behind}, agg={aggressive_behind}). '
        f'EV={ev:+.1f}BB. Action: {action}.'
    )

    tips = []

    tips.append(
        f'ISO DECISION: {hand} (score={hs:.2f}) vs threshold={threshold:.2f} with '
        f'{n_limpers} limper(s) from {position}. '
        f'{"ISO -- hand above threshold." if hs >= threshold else "BELOW threshold -- fold or over-limp."}'
    )

    tips.append(
        f'ISO SIZING: {iso_bb:.1f}BB = base({ISO_BASE_SIZING_BB.get(min(n_limpers,5),9.0):.1f}) '
        f'+ sticky addon vs {limper_type}. '
        f'Standard rule: 3bb + 1bb per limper; adjust up vs sticky callers.'
    )

    if sq_risk >= 0.20:
        tips.append(
            f'SQUEEZE RISK: {sq_risk:.0%} chance of a squeeze from {players_behind} player(s) behind. '
            f'{"Aggressive player behind -- high squeeze risk; tighten ISO range." if aggressive_behind else "Moderate squeeze risk; factor into hand selection."}'
        )
    else:
        tips.append(
            f'SQUEEZE RISK: {sq_risk:.0%} -- low squeeze risk. '
            f'Safe to ISO with standard range; few players remaining with aggression.'
        )

    if limper_type == 'fish':
        tips.append(
            f'FISH LIMPER: Widen ISO range. ISO to get HU vs fish. '
            f'Fish calling range is wide -- any top pair + or decent equity is profitable. '
            f'EV multiplier = {LIMPER_ISO_EV_MULTIPLIER["fish"]:.2f}x (40%% above baseline).'
        )
    elif limper_type == 'nit':
        tips.append(
            f'NIT LIMPER: Narrow ISO range. Nit limps AA/KK/QQ sometimes. '
            f'Only ISO with hands that dominate or have equity vs strong pairs. '
            f'EV multiplier = {LIMPER_ISO_EV_MULTIPLIER["nit"]:.2f}x (below baseline).'
        )

    if n_limpers >= 3 and action in ('OVER_LIMP', 'FOLD'):
        tips.append(
            f'MANY LIMPERS ({n_limpers}): Pot will be multiway. '
            f'Speculative hands (22-55, suited connectors) gain implied odds. '
            f'Consider over-limp with {hand} if in position for set-mining/flush draws.'
        )

    return IsoOverlimperResult(
        hand=hand,
        n_limpers=n_limpers,
        limper_type=limper_type,
        position=position,
        hand_score=hs,
        iso_threshold=threshold,
        iso_sizing_bb=iso_bb,
        squeeze_risk=sq_risk,
        iso_ev=ev,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def iso_one_liner(r: IsoOverlimperResult) -> str:
    return (
        f'[ISO {r.hand}|{r.n_limpers}L|{r.limper_type}] '
        f'{r.recommended_action} {r.iso_sizing_bb:.1f}BB '
        f'EV={r.iso_ev:+.1f}BB sqz={r.squeeze_risk:.0%}'
    )
