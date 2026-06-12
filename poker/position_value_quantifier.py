"""
Position Value Quantifier (position_value_quantifier.py)

Quantifies the MONETARY VALUE of being in position (IP) vs out of position (OOP),
expressed in BB/100 hands and per-hand EV terms. Helps players understand how
much each positional edge is worth and whether they are exploiting it fully.

THEORY:
  POSITION ADVANTAGE SOURCES:
  1. INFORMATION: IP acts last; sees villain's action before deciding
  2. RANGE PROTECTION: OOP reveals more info by betting into IP player
  3. FREE CARD: IP can check back; control pot size without bloating
  4. BLUFF EFFICIENCY: IP bluffs work more (villain checks more OOP without info)
  5. THIN VALUE: IP extracts thin value (3 streets) OOP cannot match

  POSITION VALUE (BB/100) BENCHMARKS:
  - BTN vs BB:     ~5-10 BB/100 advantage
  - CO vs SB:      ~4-8 BB/100
  - MP vs BTN:     IP player has ~3-6 BB/100 edge
  - EP vs all:     EP gives up ~5-8 BB/100 vs later positions

  FACTORS AFFECTING POSITION VALUE:
  1. VILLAIN AGGRESSIVENESS: Aggressive villains make OOP harder (more EV lost OOP)
  2. HAND TYPE: Drawing hands benefit more from position (free card play)
  3. SPR: High SPR = more streets = position worth more
  4. BOARD TEXTURE: Wet boards = position worth more (draw management)
  5. STACK DEPTH: Deeper stacks = position worth more

  REALIZABLE EQUITY:
  IP player can realize ~95% of their raw equity
  OOP player can realize ~75-85% of their raw equity
  EV gap = equity_gap x total_pot

DISTINCT FROM:
  position_awareness_guide.py:   General positional guidelines
  mdf.py:                        MDF calculation
  range_equity.py:               Range equity calculation
  THIS MODULE:                   QUANTIFIED IP EV ADVANTAGE; BB/100 benchmarks;
                                 hand-type adjustment; exploitation measurement.
"""

from dataclasses import dataclass, field
from typing import List


BASE_POSITION_VALUE_BB100: dict = {
    ('btn', 'bb'):   8.0,
    ('btn', 'sb'):   7.0,
    ('co',  'bb'):   5.5,
    ('co',  'sb'):   4.5,
    ('mp',  'bb'):   3.5,
    ('mp',  'sb'):   3.0,
    ('utg', 'bb'):   1.5,
    ('btn', 'utg'):  6.5,
    ('co',  'utg'):  5.0,
}

VILLAIN_AGGRESSION_MULTIPLIER: dict = {
    'fish':   0.80,
    'rec':    0.90,
    'nit':    0.75,
    'lag':    1.40,
    'reg':    1.10,
}

HAND_TYPE_MODIFIER: dict = {
    'suited_connector':  1.30,
    'pocket_pair_low':   1.25,
    'pocket_pair_mid':   1.15,
    'suited_one_gapper': 1.20,
    'big_pair':          0.85,
    'ace_rag':           0.90,
    'broadways':         1.05,
    'air':               1.40,
}

SPR_VALUE_MOD: dict = {
    (0, 3):   0.70,
    (3, 7):   1.00,
    (7, 15):  1.20,
    (15, 50): 1.35,
}

EQUITY_REALIZATION: dict = {
    'ip':  0.94,
    'oop': 0.78,
}


def _base_position_value(hero_pos: str, villain_pos: str) -> float:
    """Base IP advantage in BB/100."""
    key = (hero_pos.lower(), villain_pos.lower())
    if key in BASE_POSITION_VALUE_BB100:
        return BASE_POSITION_VALUE_BB100[key]
    # reverse lookup: OOP player vs IP player
    rev = (villain_pos.lower(), hero_pos.lower())
    if rev in BASE_POSITION_VALUE_BB100:
        return -BASE_POSITION_VALUE_BB100[rev]
    return 3.0  # default


def _spr_modifier(spr: float) -> float:
    for (lo, hi), mod in SPR_VALUE_MOD.items():
        if lo <= spr < hi:
            return mod
    return 1.35  # deep


def _equity_realization_gap(spr: float) -> float:
    """EV gap from equity realization difference IP vs OOP."""
    ip_real = EQUITY_REALIZATION['ip']
    oop_real = EQUITY_REALIZATION['oop']
    return round(ip_real - oop_real, 3)


def _per_hand_ev_edge(
    base_bb100: float,
    villain_type: str,
    hand_type: str,
    spr: float,
    board_texture: str,
) -> float:
    """Return per-hand EV edge in BB (not per 100)."""
    vill_mod = VILLAIN_AGGRESSION_MULTIPLIER.get(villain_type, 1.0)
    hand_mod = HAND_TYPE_MODIFIER.get(hand_type, 1.0)
    spr_mod  = _spr_modifier(spr)
    texture_mod = 1.15 if board_texture in ('wet', 'monotone') else 1.0
    return round(base_bb100 * vill_mod * hand_mod * spr_mod * texture_mod / 100.0, 3)


def _exploitation_score(hero_pos: str, hero_steal_pct: float, hero_3bet_pct: float) -> int:
    """Score 1-10: how well hero is exploiting positional advantage."""
    score = 5
    if hero_pos in ('btn', 'co'):
        if hero_steal_pct >= 0.40:
            score += 2
        elif hero_steal_pct >= 0.30:
            score += 1
        elif hero_steal_pct < 0.20:
            score -= 2
        if hero_3bet_pct >= 0.08:
            score += 1
        elif hero_3bet_pct < 0.03:
            score -= 1
    return max(1, min(10, score))


@dataclass
class PositionValueResult:
    hero_pos: str
    villain_pos: str
    villain_type: str
    hand_type: str

    base_value_bb100: float
    per_hand_ev_edge_bb: float
    equity_realization_gap: float
    exploitation_score: int

    hero_is_ip: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_position_value(
    hero_pos: str = 'btn',
    villain_pos: str = 'bb',
    villain_type: str = 'rec',
    hand_type: str = 'suited_connector',
    spr: float = 6.0,
    board_texture: str = 'semi_wet',
    hero_steal_pct: float = 0.35,
    hero_3bet_pct: float = 0.06,
) -> PositionValueResult:
    """
    Quantify positional value and exploitation score.

    Args:
        hero_pos:           Hero position ('btn','co','mp','utg','sb','bb')
        villain_pos:        Villain position
        villain_type:       Villain type ('fish','rec','nit','lag','reg')
        hand_type:          Hero hand type ('suited_connector','pocket_pair_low',
                            'big_pair','ace_rag','broadways','air', etc.)
        spr:                Stack-to-pot ratio
        board_texture:      Board texture ('dry','semi_wet','wet','monotone')
        hero_steal_pct:     Hero's steal attempt % (for exploitation score)
        hero_3bet_pct:      Hero's 3-bet % (for exploitation score)

    Returns:
        PositionValueResult
    """
    POSITION_ORDER = ['utg', 'ep', 'mp', 'co', 'btn', 'sb', 'bb']

    def pos_idx(p: str) -> int:
        p = p.lower()
        if p in POSITION_ORDER:
            return POSITION_ORDER.index(p)
        return 2  # default middle

    hero_ip = pos_idx(hero_pos) > pos_idx(villain_pos) or (
        hero_pos.lower() == 'btn' and villain_pos.lower() in ('sb', 'bb')
    )

    base = _base_position_value(hero_pos, villain_pos)
    ev_edge = _per_hand_ev_edge(base, villain_type, hand_type, spr, board_texture)
    eq_gap = _equity_realization_gap(spr)
    exploit = _exploitation_score(hero_pos, hero_steal_pct, hero_3bet_pct)

    pos_label = 'IP' if hero_ip else 'OOP'
    vill_mod = VILLAIN_AGGRESSION_MULTIPLIER.get(villain_type, 1.0)

    verdict = (
        f'[PVQ {hero_pos.upper()}vs{villain_pos.upper()}|{pos_label}] '
        f'base={base:+.1f}BB/100 per_hand={ev_edge:+.3f}BB '
        f'exploit_score={exploit}/10'
    )

    reasoning = (
        f'Position value: {hero_pos.upper()} vs {villain_pos.upper()} ({pos_label}). '
        f'Base value: {base:+.1f}BB/100. '
        f'Villain {villain_type} aggression mod: {vill_mod:.2f}x. '
        f'SPR={spr:.1f} modifier: {_spr_modifier(spr):.2f}x. '
        f'Per-hand EV edge: {ev_edge:+.3f}BB. '
        f'Exploitation score: {exploit}/10.'
    )

    tips = []

    tips.append(
        f'POSITION EDGE: {pos_label} advantage = {base:+.1f}BB/100 base. '
        f'Per-hand EV edge with current adjustments: {ev_edge:+.3f}BB. '
        f'{"IP advantage -- extract full value." if hero_ip else "OOP disadvantage -- play conservatively; reduce bluff frequency."}'
    )

    tips.append(
        f'EXPLOITATION SCORE: {exploit}/10. '
        f'{"Good positional exploitation." if exploit >= 7 else "Improve by stealing more often from BTN/CO and 3-betting more in position." if exploit < 5 else "Decent -- small improvements possible."}'
    )

    if hero_ip:
        tips.append(
            f'IP ADVANTAGES: Act last on all streets; free card plays available; '
            f'IP equity realization={EQUITY_REALIZATION["ip"]:.0%} vs OOP={EQUITY_REALIZATION["oop"]:.0%}. '
            f'Gap={eq_gap:.0%} -- your equity converts to chips more efficiently.'
        )
    else:
        tips.append(
            f'OOP MITIGATION: Use check-raises to compensate for positional disadvantage. '
            f'Equity realization={EQUITY_REALIZATION["oop"]:.0%} -- ~{eq_gap:.0%} less efficient than IP. '
            f'Reduce speculative calls; increase range strength for OOP play.'
        )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Positional edge worth {vill_mod:.1f}x normal. '
            f'Aggressive villains make OOP spots especially costly. '
            f'Tighten OOP calling ranges vs LAG; 3-bet more IP to deny their positional squeeze.'
        )

    return PositionValueResult(
        hero_pos=hero_pos,
        villain_pos=villain_pos,
        villain_type=villain_type,
        hand_type=hand_type,
        base_value_bb100=base,
        per_hand_ev_edge_bb=ev_edge,
        equity_realization_gap=eq_gap,
        exploitation_score=exploit,
        hero_is_ip=hero_ip,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pvq_one_liner(r: PositionValueResult) -> str:
    pos = 'IP' if r.hero_is_ip else 'OOP'
    return (
        f'[PVQ {r.hero_pos.upper()}vs{r.villain_pos.upper()}|{pos}] '
        f'base={r.base_value_bb100:+.1f}BB/100 '
        f'per_hand={r.per_hand_ev_edge_bb:+.3f}BB '
        f'exploit={r.exploitation_score}/10'
    )
