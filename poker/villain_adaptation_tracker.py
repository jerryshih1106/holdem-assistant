"""
Villain Adaptation Tracker (villain_adaptation_tracker.py)

Tracks in-session villain tendencies and recommends real-time counter-strategy
adjustments. As you observe a villain's behavior, update their profile and get
specific counter-strategy recommendations.

VILLAIN ADAPTATION THEORY:
  GTO is the optimal strategy against an unknown opponent. Once you identify
  a specific leak or tendency, you can EXPLOIT it for maximum EV.

  Key exploits:
  NITS (tight/passive):
    - Open wider in position (they fold too much preflop)
    - Float dry boards (they give up with marginal hands)
    - Bluff more on turn/river (they fold to aggression)

  FISH/STATIONS (loose/passive):
    - Value-bet thinner (3 streets with TPGK)
    - Never bluff (they call down with anything)
    - Build big pots (they call off with second pair)

  MANIACS (loose/aggressive):
    - Tighten calling range (but check-raise more)
    - Let them bluff into you (trap with strong hands)
    - Don't bluff (they never fold)

  REGS (balanced):
    - Apply GTO-near strategy
    - Look for minor tendencies to exploit at margin
    - Adjust based on their leaks (over-fold/over-call)

ADAPTATION LOOP:
  Session start: treat as balanced player
  Observation 1: slight adjustment
  Observations 3+: confident exploitation

DISTINCT FROM:
  hud_stats_advisor.py:          HUD stat interpretation
  session_leak_prioritizer.py:   Hero's own leaks
  exploitative_adjustment.py:    Specific exploits for specific leaks
  THIS MODULE:                   In-session villain profiling + real-time
                                 counter-strategy recommendation engine

Usage:
    from poker.villain_adaptation_tracker import track_villain, VillainAdaptation, vat_one_liner

    result = track_villain(
        villain_vpip=0.45,
        villain_pfr=0.12,
        villain_af=1.2,
        villain_wtsd=0.38,
        villain_fold_to_cbet=0.30,
        villain_3bet=0.04,
        hands_observed=120,
        hero_position='ip',
        street='flop',
        pot_bb=25.0,
    )
    print(vat_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Villain type thresholds
VPIP_TIGHT = 0.20
VPIP_LOOSE = 0.32
PFR_PASSIVE = 0.12
PFR_AGGRESSIVE = 0.22
AF_PASSIVE = 1.5
AF_AGGRESSIVE = 3.0
WTSD_FOLDER = 0.22
WTSD_STATION = 0.35
FOLD_CBET_DEFENDER = 0.40
FOLD_CBET_NITTER = 0.60


def _classify_villain(
    vpip: float,
    pfr: float,
    af: float,
    wtsd: float,
    fold_to_cbet: float,
) -> str:
    """Classify villain into archetype."""
    tight = vpip <= VPIP_TIGHT
    loose = vpip >= VPIP_LOOSE
    passive = af <= AF_PASSIVE
    aggressive = af >= AF_AGGRESSIVE

    if tight and passive:
        return 'nit'
    elif tight and aggressive:
        return 'tag'   # tight-aggressive (regular)
    elif loose and passive:
        return 'fish'  # calling station
    elif loose and aggressive:
        return 'lag'   # loose-aggressive (maniac)
    elif not tight and not loose and aggressive:
        return 'semi_lag'
    else:
        return 'reg'   # balanced regular


def _confidence_level(hands_observed: int) -> str:
    if hands_observed >= 200:
        return 'high'
    elif hands_observed >= 50:
        return 'medium'
    else:
        return 'low'


def _primary_exploit(
    villain_type: str,
    vpip: float,
    af: float,
    wtsd: float,
    fold_to_cbet: float,
    hero_position: str,
) -> str:
    """Single most important exploit against this villain."""
    if villain_type == 'nit':
        return 'steal_and_cbet_freely'
    elif villain_type == 'fish':
        return 'value_bet_thin_never_bluff'
    elif villain_type == 'lag':
        return 'trap_and_call_down_wider'
    elif villain_type == 'tag':
        if fold_to_cbet >= 0.55:
            return 'cbet_high_frequency'
        else:
            return 'play_balanced_gto'
    elif villain_type == 'semi_lag':
        return 'check_raise_strong_hands'
    else:
        return 'play_balanced_gto'


def _cbet_adjustment(
    villain_type: str,
    fold_to_cbet: float,
    hero_position: str,
) -> float:
    """Recommended c-bet frequency adjustment (delta from GTO 0.58)."""
    base = 0.58
    if fold_to_cbet >= 0.60:
        base += 0.15   # they fold too much; bet more
    elif fold_to_cbet <= 0.35:
        base -= 0.20   # they call too much; check more, bet only value
    if villain_type == 'nit':
        base += 0.10
    elif villain_type in ('fish', 'lag'):
        base -= 0.15
    if hero_position == 'oop':
        base -= 0.05
    return round(min(0.95, max(0.20, base)), 3)


def _bluff_frequency_adjustment(
    villain_type: str,
    wtsd: float,
    hero_position: str,
) -> float:
    """Recommended bluff frequency (0-1)."""
    if villain_type in ('fish',) or wtsd >= 0.38:
        return 0.05   # almost never bluff
    elif villain_type == 'nit' or wtsd <= 0.22:
        return 0.40   # bluff liberally
    elif villain_type == 'lag':
        return 0.10   # don't bluff maniacs
    else:
        return 0.25   # GTO-near bluff frequency


def _value_bet_width(
    villain_type: str,
    wtsd: float,
) -> str:
    """How wide to value bet."""
    if villain_type == 'fish' or wtsd >= 0.38:
        return 'thin_3streets'    # 3 streets with TPGK
    elif villain_type == 'nit':
        return 'top_pair_plus'    # need strong hands to value bet
    elif villain_type == 'lag':
        return 'premium_only'     # maniacs call then raise; only bet monsters
    else:
        return 'standard'         # top pair good kicker+


@dataclass
class VillainAdaptation:
    # Inputs
    villain_vpip: float
    villain_pfr: float
    villain_af: float
    villain_wtsd: float
    villain_fold_to_cbet: float
    villain_3bet: float
    hands_observed: int
    hero_position: str
    street: str
    pot_bb: float

    # Classification
    villain_type: str        # 'nit' / 'fish' / 'lag' / 'tag' / 'reg' / 'semi_lag'
    confidence: str          # 'high' / 'medium' / 'low'

    # Adjustments
    primary_exploit: str
    recommended_cbet_pct: float
    recommended_bluff_pct: float
    value_bet_width: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def track_villain(
    villain_vpip: float = 0.25,
    villain_pfr: float = 0.18,
    villain_af: float = 2.2,
    villain_wtsd: float = 0.28,
    villain_fold_to_cbet: float = 0.50,
    villain_3bet: float = 0.08,
    hands_observed: int = 100,
    hero_position: str = 'ip',
    street: str = 'flop',
    pot_bb: float = 25.0,
) -> VillainAdaptation:
    """
    Track villain tendencies and recommend counter-strategy.

    Args:
        villain_vpip:         VPIP stat
        villain_pfr:          PFR stat
        villain_af:           Aggression Factor
        villain_wtsd:         Went to Showdown
        villain_fold_to_cbet: Fold to c-bet
        villain_3bet:         3-bet frequency
        hands_observed:       Hands in sample
        hero_position:        'ip' / 'oop'
        street:               'preflop' / 'flop' / 'turn' / 'river'
        pot_bb:               Current pot

    Returns:
        VillainAdaptation
    """
    vtype = _classify_villain(villain_vpip, villain_pfr, villain_af,
                               villain_wtsd, villain_fold_to_cbet)
    confidence = _confidence_level(hands_observed)
    exploit = _primary_exploit(vtype, villain_vpip, villain_af,
                                villain_wtsd, villain_fold_to_cbet, hero_position)
    cbet_pct = _cbet_adjustment(vtype, villain_fold_to_cbet, hero_position)
    bluff_pct = _bluff_frequency_adjustment(vtype, villain_wtsd, hero_position)
    vb_width = _value_bet_width(vtype, villain_wtsd)

    verdict = (
        f'[VAT {vtype.upper()}|{confidence}|{hands_observed}h] '
        f'{exploit.upper()} | cbet={cbet_pct:.0%} bluff={bluff_pct:.0%}'
    )

    reasoning = (
        f'Villain classified as {vtype} ({confidence} confidence, {hands_observed} hands). '
        f'VPIP={villain_vpip:.0%} PFR={villain_pfr:.0%} AF={villain_af:.1f} '
        f'WTSD={villain_wtsd:.0%} FoldCbet={villain_fold_to_cbet:.0%}. '
        f'Primary exploit: {exploit}. C-bet={cbet_pct:.0%} Bluff={bluff_pct:.0%} VB={vb_width}.'
    )

    tips = []

    tips.append(
        f'VILLAIN TYPE: {vtype.upper()} ({confidence} confidence from {hands_observed} hands). '
        f'VPIP/PFR gap: {villain_vpip - villain_pfr:.0%} '
        f'({"large gap = passive caller" if villain_vpip - villain_pfr > 0.12 else "normal"}).'
    )

    tips.append(
        f'PRIMARY EXPLOIT: {exploit.upper()}. '
        f'C-bet at {cbet_pct:.0%} (GTO base 58%). '
        f'Bluff at {bluff_pct:.0%} frequency. '
        f'Value-bet width: {vb_width}.'
    )

    if confidence == 'low':
        tips.append(
            f'LOW CONFIDENCE: Only {hands_observed} hands observed. '
            f'Stats may not be reliable. '
            f'Use GTO-near strategy until 50+ hands are observed.'
        )

    if vtype == 'fish':
        tips.append(
            f'FISH EXPLOIT: NEVER bluff this villain. '
            f'Value-bet 3 streets with TPGK or better. '
            f'Build large pots -- they call off with second pair. '
            f'Watch for WTSD={villain_wtsd:.0%} -- they showdown {villain_wtsd:.0%} of hands.'
        )

    elif vtype == 'nit':
        tips.append(
            f'NIT EXPLOIT: Steal freely in position. '
            f'They fold too much preflop (VPIP={villain_vpip:.0%}). '
            f'C-bet at high frequency ({cbet_pct:.0%}) on most boards. '
            f'Float and bluff turn when they show weakness.'
        )

    elif vtype == 'lag':
        tips.append(
            f'MANIAC EXPLOIT: Do NOT bluff. '
            f'Widen calling range (trap with medium strength hands). '
            f'Check-raise strong hands to build pots. '
            f'AF={villain_af:.1f} means they bet {villain_af:.1f}x as often as they call.'
        )

    elif vtype == 'tag':
        tips.append(
            f'REG/TAG: Play close to GTO. '
            f'Look for minor exploits: fold_to_cbet={villain_fold_to_cbet:.0%} '
            f'({"bet more" if villain_fold_to_cbet >= 0.55 else "check more"}). '
            f'3-bet={villain_3bet:.0%} -- {"widen vs 3bet" if villain_3bet <= 0.05 else "respect their range"}.'
        )

    if hero_position == 'ip' and vtype in ('nit', 'fish'):
        tips.append(
            f'IP ADVANTAGE: IP vs {vtype}: open wide, cbet frequently ({cbet_pct:.0%}). '
            f'They will check-fold or call-fold most hands. '
            f'3-bet light if they open wide.'
        )

    return VillainAdaptation(
        villain_vpip=villain_vpip,
        villain_pfr=villain_pfr,
        villain_af=villain_af,
        villain_wtsd=villain_wtsd,
        villain_fold_to_cbet=villain_fold_to_cbet,
        villain_3bet=villain_3bet,
        hands_observed=hands_observed,
        hero_position=hero_position,
        street=street,
        pot_bb=pot_bb,
        villain_type=vtype,
        confidence=confidence,
        primary_exploit=exploit,
        recommended_cbet_pct=cbet_pct,
        recommended_bluff_pct=bluff_pct,
        value_bet_width=vb_width,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def vat_one_liner(r: VillainAdaptation) -> str:
    return (
        f'[VAT {r.villain_type.upper()}|{r.confidence}|{r.hands_observed}h] '
        f'{r.primary_exploit.upper()} | cbet={r.recommended_cbet_pct:.0%} bluff={r.recommended_bluff_pct:.0%}'
    )
