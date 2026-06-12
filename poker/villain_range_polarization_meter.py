"""
Villain Range Polarization Meter (villain_range_polarization_meter.py)

Measures how polarized (strong hands + bluffs) vs condensed (medium
strength hands) a villain's range appears, based on their betting actions.

POLARIZED range:  Villain bets/raises with very strong hands AND bluffs.
                  No medium-strength hands. Hard to bluff-catch efficiently.
                  Example: large river bets with nutted hands and missed draws.

CONDENSED range:  Villain has mostly medium-strength hands.
                  Few nuts; few complete air. Call-heavy range on river.
                  Example: villain called flop, called turn, now checks river.

LINEAR range:     Villain bets in a linear value fashion (top down).
                  Fewer bluffs. Easier to read — fold when raised; call small.
                  Example: low AF villain who only bets top pair+.

POLARIZATION SCORE (0-1):
  0.0 = completely condensed (medium hands only)
  0.5 = balanced (some value, some bluffs, some mediums)
  1.0 = completely polarized (nuts + air, no middle)

INPUTS USED:
  - Number of streets bet/raised (all 3 = polarized; partial = condensed)
  - Bet sizing pattern (large bets = polar; small = linear/condensed)
  - Villain's AF (high = polar; low = linear)
  - Villain's WTSD (high = condensed/medium; low = polar bluffs or value)
  - Action sequence (bet-check-bet = more polar than bet-bet-bet)

EXPLOITATION:
  vs polarized: bluff-catch optimally (use blocking bets); thin value = bad
  vs condensed: thin value is good; folding to bets = exploitable
  vs linear: raise/fold; villain has a range, not a polarized distribution

DISTINCT FROM OTHER MODULES:
  range_assess.py:  Estimates villain's absolute hand range (what cards)
  range_heatmap.py: Visual range display
  THIS MODULE:      Measures the SHAPE of villain's range distribution;
                    informs betting/calling/raising strategy

Usage:
    from poker.villain_range_polarization_meter import measure_polarization, PolarizationResult, pol_one_liner

    result = measure_polarization(
        villain_af=3.2,
        villain_wtsd=0.22,
        villain_vpip=0.28,
        streets_bet=3,
        avg_bet_size_pct=1.20,  # 120% pot overbet
        action_sequence='bet-raise-bet',
        n_players=2,
        pot_bb=45.0,
    )
    print(pol_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


def _af_component(villain_af: float) -> float:
    """High AF → high polarization component (0-0.3)."""
    if villain_af >= 4.0:
        return 0.30
    elif villain_af >= 3.0:
        return 0.22
    elif villain_af >= 2.0:
        return 0.15
    elif villain_af >= 1.0:
        return 0.08
    else:
        return 0.02


def _wtsd_component(villain_wtsd: float) -> float:
    """Low WTSD → higher polarization (bluffs miss the river; value takes it down early)."""
    if villain_wtsd <= 0.22:
        return 0.15   # doesn't go to SD → polar (either folds or wins early)
    elif villain_wtsd <= 0.28:
        return 0.10
    elif villain_wtsd <= 0.35:
        return 0.05
    else:
        return 0.00   # high WTSD → condensed/medium


def _sizing_component(avg_bet_size_pct: float) -> float:
    """Large bet sizes → polarized range."""
    if avg_bet_size_pct >= 1.5:
        return 0.25   # overbet → very polar
    elif avg_bet_size_pct >= 1.0:
        return 0.18   # pot bet → polar
    elif avg_bet_size_pct >= 0.75:
        return 0.12   # 75% → moderate
    elif avg_bet_size_pct >= 0.50:
        return 0.06   # small bet → more linear
    else:
        return 0.02   # tiny bet → condensed or blocking


def _streets_component(streets_bet: int) -> float:
    """Betting all 3 streets is polarized; checking streets = condensed."""
    return {0: 0.02, 1: 0.06, 2: 0.12, 3: 0.20}.get(min(streets_bet, 3), 0.20)


def _action_sequence_component(action_sequence: str) -> float:
    """Certain action patterns signal polarization."""
    seq = action_sequence.lower().replace(' ', '')
    # Raise on later streets = strong polarization signal
    if 'raise' in seq:
        return 0.15
    elif 'bet-check-bet' in seq:
        return 0.10  # skip street = range is polarized (block turned to value on river)
    elif 'check-raise' in seq or 'checkraise' in seq:
        return 0.12
    elif seq.count('bet') >= 2:
        return 0.05
    else:
        return 0.02


def _range_type(score: float) -> str:
    if score >= 0.75:
        return 'highly_polarized'
    elif score >= 0.55:
        return 'polarized'
    elif score >= 0.40:
        return 'semi_polarized'
    elif score >= 0.25:
        return 'condensed'
    else:
        return 'linear'


def _exploitation_advice(range_type: str, pot_bb: float, n_players: int) -> str:
    if range_type == 'highly_polarized':
        return (
            f'HIGHLY POLARIZED ({pot_bb:.0f}BB pot): Villain has nuts or air. '
            f'Call with bluff catchers that block value hands; fold medium hands. '
            f'Do NOT bluff into polarized range (value hands snap-call). '
            f'Block bet small on river OOP to define range; do not raise without nuts.'
        )
    elif range_type == 'polarized':
        return (
            f'POLARIZED: Villain bets with strong hands AND bluffs. '
            f'Thin value is a trap (you beat only bluffs; lose to all value). '
            f'Best play: bluff-catch with good blockers; give up without blockers. '
            f'Raise is profitable only with nuts (villain bluffs fold, value doesn\'t).'
        )
    elif range_type == 'semi_polarized':
        return (
            f'SEMI-POLARIZED: Mix of value/bluffs/medium hands. '
            f'Some thin value is fine. Calls are profitable if you beat medium hands. '
            f'Moderate raises can extract value and fold out some bluffs.'
        )
    elif range_type == 'condensed':
        return (
            f'CONDENSED (medium hands): Villain has value bets with medium strength. '
            f'Thin value bets extract max EV — villain calls with worse. '
            f'Bluffing is risky (villain calls); over-folds rarely happen. '
            f'Raise with strong hands; fold to raises yourself (condensed ranges rarely bluff-raise).'
        )
    else:  # linear
        return (
            f'LINEAR: Villain bets top-down value (TP+, QQ+, etc.). Rarely bluffs. '
            f'Calling for showdown value is excellent. '
            f'Fold only when facing very large bets or river raises. '
            f'Bluff rarely — villain calls down with any pair. '
            f'Raise is excellent with strong hands (value vs condensed linear range).'
        )


def _nut_advantage_modifier(range_type: str, villain_vpip: float) -> float:
    """How much nut advantage to assume hero has vs this range."""
    if range_type in ('highly_polarized', 'polarized'):
        return 0.5   # villain has lots of nuts; hero may be ahead or way behind
    elif range_type == 'condensed':
        return 0.7   # hero likely has nut advantage (villain capped at medium)
    else:
        return 0.6


@dataclass
class PolarizationResult:
    # Inputs
    villain_af: float
    villain_wtsd: float
    villain_vpip: float
    streets_bet: int
    avg_bet_size_pct: float
    action_sequence: str
    n_players: int
    pot_bb: float

    # Score breakdown
    af_component: float
    wtsd_component: float
    sizing_component: float
    streets_component: float
    sequence_component: float
    polarization_score: float   # 0-1

    # Classification
    range_type: str   # 'linear' / 'condensed' / 'semi_polarized' / 'polarized' / 'highly_polarized'
    nut_advantage_hero: float  # estimated fraction of nuts hero holds

    # Exploitation
    exploitation_advice: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def measure_polarization(
    villain_af: float = 2.5,
    villain_wtsd: float = 0.28,
    villain_vpip: float = 0.28,
    streets_bet: int = 2,
    avg_bet_size_pct: float = 0.80,
    action_sequence: str = 'bet-bet',
    n_players: int = 2,
    pot_bb: float = 30.0,
) -> PolarizationResult:
    """
    Measure how polarized villain's range is and advise on exploitation.

    Args:
        villain_af:          Villain's aggression factor
        villain_wtsd:        Villain's went-to-showdown %
        villain_vpip:        Villain's VPIP
        streets_bet:         Number of streets villain bet/raised this hand
        avg_bet_size_pct:    Average bet size as fraction of pot
        action_sequence:     Villain's action pattern (e.g. 'bet-bet', 'check-raise', 'bet-check-bet')
        n_players:           Players in hand
        pot_bb:              Current pot in BBs

    Returns:
        PolarizationResult
    """
    afc = _af_component(villain_af)
    wtsc = _wtsd_component(villain_wtsd)
    szc = _sizing_component(avg_bet_size_pct)
    stc = _streets_component(streets_bet)
    seqc = _action_sequence_component(action_sequence)

    # Weighted sum: sizing and streets are most diagnostic
    raw = afc + wtsc + szc * 1.2 + stc * 1.1 + seqc
    # Normalize to 0-1 (max theoretical score ~1.0)
    score = round(min(1.0, raw / (0.30 + 0.15 + 0.25*1.2 + 0.20*1.1 + 0.15)), 3)

    rtype = _range_type(score)
    nut_adv = _nut_advantage_modifier(rtype, villain_vpip)
    exploit = _exploitation_advice(rtype, pot_bb, n_players)

    reasoning = (
        f'Polarization score={score:.2f} [{rtype}]. '
        f'Components: AF={afc:.2f} WTSD={wtsc:.2f} sizing={szc:.2f}x1.2 streets={stc:.2f}x1.1 seq={seqc:.2f}. '
        f'Villain AF={villain_af} WTSD={villain_wtsd:.0%} bet_size={avg_bet_size_pct:.0%}pot. '
        f'Streets bet={streets_bet} action_seq="{action_sequence}". '
        f'Hero nut advantage estimate={nut_adv:.0%}.'
    )

    verdict = (
        f'[POL {rtype.upper()}|score={score:.2f}] {exploit[:60]} | '
        f'af_c={afc:.2f} sz_c={szc:.2f} seq_c={seqc:.2f}'
    )

    tips = [exploit]

    if rtype in ('highly_polarized', 'polarized') and streets_bet == 3:
        tips.append(
            f'3-STREET AGGRESSION: Villain bet all 3 streets with {avg_bet_size_pct:.0%} pot sizes. '
            f'This is a strong polarization signal. '
            f'Either villain has the nuts (value) or is committed to a bluff. '
            f'Use pot odds + your blocking cards to decide — do you block their value hands?'
        )
    if rtype == 'condensed' or rtype == 'linear':
        tips.append(
            f'CONDENSED/LINEAR RANGE: Villain is capped. '
            f'You can raise for thin value — villain rarely has the nuts. '
            f'Bluff the river with sizing that targets villain\'s fold-to-cbet stat. '
            f'If villain never raises, you can call thin hands and bluff rivers profitably.'
        )
    if villain_af <= 1.2 and rtype != 'polarized':
        tips.append(
            f'LOW AF ({villain_af:.1f}): Passive villain — bets are mostly value. '
            f'Their range is linear. Give up bluffs; raise with value only. '
            f'Villain checks drawing hands; bets made hands. '
            f'Bet size is small? Likely thin value or protection bet — can call or raise.'
        )

    return PolarizationResult(
        villain_af=villain_af,
        villain_wtsd=villain_wtsd,
        villain_vpip=villain_vpip,
        streets_bet=streets_bet,
        avg_bet_size_pct=avg_bet_size_pct,
        action_sequence=action_sequence,
        n_players=n_players,
        pot_bb=pot_bb,
        af_component=afc,
        wtsd_component=wtsc,
        sizing_component=szc,
        streets_component=stc,
        sequence_component=seqc,
        polarization_score=score,
        range_type=rtype,
        nut_advantage_hero=nut_adv,
        exploitation_advice=exploit,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pol_one_liner(r: PolarizationResult) -> str:
    return (
        f'[POL {r.range_type.upper()}|score={r.polarization_score:.2f}] '
        f'af={r.villain_af:.1f} wtsd={r.villain_wtsd:.0%} '
        f'size={r.avg_bet_size_pct:.0%}pot streets={r.streets_bet} | '
        f'nut_adv={r.nut_advantage_hero:.0%}'
    )
