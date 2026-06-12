"""
Big Blind Defense Range Guide (bb_defense_range_guide.py)

How to construct a BB defense range vs steal raises from various positions.
BB closes the action and gets a discount (already has 1BB invested), so
should defend wider than other positions at the same price.

THEORY:
  BB DEFENSE FUNDAMENTALS:
  BB gets 1BB discount (already invested). When facing a 3BB open:
  - Effective call price = 2BB (put in 1 more; already have 1)
  - Pot odds = 2/(3+1.5+2) = 2/6.5 = 30.8% equity needed
  - Much cheaper than cold-calling 3BB from another position

  BB DEFENSE FREQUENCY BY OPEN POSITION:
  vs BTN steal: Defend ~60% (BTN opens very wide ~40%; BB has best price)
  vs CO steal:  Defend ~52% (CO range tighter ~26%)
  vs MP open:   Defend ~42% (MP range tight ~18%; harder to defend wide)
  vs UTG open:  Defend ~35% (UTG very tight ~14%; BB should fold marginal)
  vs SB open:   Defend ~65% (SB range wide ~52%; cheap to call in position)

  DEFENSE ACTIONS:
  1. 3-BET: Value (AA-JJ, AKs, AQs) + Polarized bluffs (A5s, 76s)
  2. CALL: Speculative hands, medium pairs, suited connectors, suited aces
  3. FOLD: Offsuit dominated hands, weak backdoor-only hands

  VILLIANS THAT CHANGE DEFENSE:
  vs Wide stealers (fish/LAG): Defend more; 3-bet wider (bluffs more profitable)
  vs Tight openers (nit/UTG): Defend less; fold more non-premium hands

  SIZING IMPACT:
  Min-raise (2BB): Defend very wide (~70%)
  Standard (2.5-3BB): Standard defense
  4BB+: Fold more speculative hands

DISTINCT FROM:
  bb_defense_optimizer.py:  Optimizer tool
  blind_vs_blind_strategy_guide.py: SB vs BB specific
  THIS MODULE:              BB RANGE CONSTRUCTION; by opener position;
                            3-bet vs call vs fold decision by hand type.
"""

from dataclasses import dataclass, field
from typing import List, Dict


DEFENSE_FREQ_VS_POSITION: dict = {
    'utg': 0.35,
    'utg1': 0.37,
    'mp':  0.42,
    'hj':  0.46,
    'co':  0.52,
    'btn': 0.60,
    'sb':  0.65,
}

VILLAIN_OPEN_RANGE_PCT: dict = {
    'utg': 0.14,
    'utg1': 0.16,
    'mp':  0.18,
    'hj':  0.22,
    'co':  0.26,
    'btn': 0.40,
    'sb':  0.52,
}

OPEN_SIZE_DEFENSE_MODIFIER: dict = {
    2.0: +0.10,
    2.5: +0.05,
    3.0:  0.00,
    3.5: -0.05,
    4.0: -0.10,
    5.0: -0.18,
}

VILLAIN_TYPE_DEFENSE_MODIFIER: dict = {
    'fish':  +0.08,
    'rec':   +0.04,
    'nit':   -0.10,
    'lag':   +0.08,
    'reg':    0.00,
}

THREEBET_FREQ_VS_POSITION: dict = {
    'utg': 0.06,
    'mp':  0.07,
    'co':  0.09,
    'btn': 0.12,
    'sb':  0.14,
}

HAND_CATEGORY_ACTION: dict = {
    'AA':   '3bet_value', 'KK':   '3bet_value', 'QQ':   '3bet_value',
    'JJ':   '3bet_value', 'TT':   'call_or_3bet', 'AKs':  '3bet_value',
    'AQs':  '3bet_value', 'AJs':  'call', 'ATs': 'call',
    'A2s-A5s': '3bet_bluff', 'KQs': 'call', 'KJs': 'call',
    'QJs':  'call', 'JTs':  'call', 'T9s': 'call',
    '99':   'call', '88':   'call', '77':  'call',
    '66-22': 'call', 'AKo':  '3bet_value', 'AQo': 'call',
    'offsuit_broadway': 'call', 'weak_offsuit': 'fold',
}


def _defense_frequency(
    open_position: str,
    open_size_bb: float,
    villain_type: str,
) -> float:
    base = DEFENSE_FREQ_VS_POSITION.get(open_position, 0.45)
    size_mod = 0.0
    for size, mod in sorted(OPEN_SIZE_DEFENSE_MODIFIER.items()):
        if open_size_bb <= size:
            size_mod = mod
            break
    else:
        size_mod = -0.18
    vil_mod = VILLAIN_TYPE_DEFENSE_MODIFIER.get(villain_type, 0.00)
    result = base + size_mod + vil_mod
    return round(min(0.85, max(0.15, result)), 3)


def _threebet_frequency(open_position: str, villain_type: str) -> float:
    base = THREEBET_FREQ_VS_POSITION.get(open_position, 0.08)
    vil_mod = VILLAIN_TYPE_DEFENSE_MODIFIER.get(villain_type, 0.00) * 0.5
    return round(min(0.25, max(0.04, base + vil_mod)), 3)


def _pot_odds_equity(open_size_bb: float) -> float:
    call_amount = open_size_bb - 1.0
    total_pot = open_size_bb + 0.5 + call_amount
    return round(call_amount / total_pot, 3)


@dataclass
class BBDefenseRangeResult:
    open_position: str
    open_size_bb: float
    villain_type: str

    defense_frequency: float
    threebet_frequency: float
    call_frequency: float
    fold_frequency: float
    pot_odds_equity: float
    villain_open_range_pct: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_bb_defense_range(
    open_position: str = 'btn',
    open_size_bb: float = 3.0,
    villain_type: str = 'reg',
) -> BBDefenseRangeResult:
    """
    Construct BB defense range vs a raise from given position.

    Args:
        open_position:  Villain's position ('utg','mp','co','btn','sb')
        open_size_bb:   Villain's open raise size in BB (2.0, 2.5, 3.0, 4.0)
        villain_type:   Villain type ('fish','rec','nit','lag','reg')

    Returns:
        BBDefenseRangeResult
    """
    defense = _defense_frequency(open_position, open_size_bb, villain_type)
    threebet = _threebet_frequency(open_position, villain_type)
    call_freq = round(defense - threebet, 3)
    fold_freq = round(1.0 - defense, 3)
    pot_eq = _pot_odds_equity(open_size_bb)
    vil_range = VILLAIN_OPEN_RANGE_PCT.get(open_position, 0.25)

    verdict = (
        f'[BBD vs {open_position.upper()}|{villain_type}|{open_size_bb:.1f}BB] '
        f'defend={defense:.0%} 3bet={threebet:.0%} call={call_freq:.0%} fold={fold_freq:.0%}'
    )

    reasoning = (
        f'BB defense vs {open_position.upper()} ({villain_type}) open to {open_size_bb:.1f}BB. '
        f'Villain open range={vil_range:.0%}. '
        f'Pot odds equity needed={pot_eq:.0%}. '
        f'Defense={defense:.0%}: 3-bet {threebet:.0%} + call {call_freq:.0%}. '
        f'Fold={fold_freq:.0%}.'
    )

    tips = []

    tips.append(
        f'BB DEFENSE vs {open_position.upper()} ({open_size_bb:.1f}BB open): '
        f'Defend {defense:.0%} total (3-bet {threebet:.0%} + call {call_freq:.0%}). '
        f'Villain range={vil_range:.0%}; pot odds need {pot_eq:.0%} equity. '
        f'Fold {fold_freq:.0%} (weakest offsuit hands, dominated kickers).'
    )

    tips.append(
        f'3-BET RANGE ({threebet:.0%}): Value (AA-JJ, AKs-AQs) + polarized bluffs (A5s-A2s, 65s). '
        f'vs {villain_type}: {"3-bet wider -- villain folds too much." if villain_type == "nit" else "3-bet value/strong semi-bluffs." if villain_type in ("fish","lag") else "Standard polarized 3-bet."} '
        f'CALL RANGE ({call_freq:.0%}): Suited connectors, medium pairs 22-99, suited aces ATs-A6s.'
    )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Widen defense to {defense:.0%} (+{VILLAIN_TYPE_DEFENSE_MODIFIER["lag"]:.0%}). '
            f'LAG opens wide -- your suited connectors and weak aces play better vs wider range. '
            f'3-bet more bluffs vs LAG; they fold to 3-bets reasonably often.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT: Tighten defense to {defense:.0%} ({VILLAIN_TYPE_DEFENSE_MODIFIER["nit"]:.0%}). '
            f'Nit opens only 10-14% from UTG -- your suited connectors have poor implied odds. '
            f'Fold marginal speculative hands; call only strong value or premium suited hands.'
        )

    if open_position in ('utg', 'mp'):
        tips.append(
            f'VS {open_position.upper()} (TIGHT RANGE): {vil_range:.0%} open range. '
            f'Villain has premium hands; reduce speculative calls. '
            f'Fold: weak pairs (22-55 from UTG), offsuit Broadway combos with bad kicker.'
        )

    return BBDefenseRangeResult(
        open_position=open_position,
        open_size_bb=open_size_bb,
        villain_type=villain_type,
        defense_frequency=defense,
        threebet_frequency=threebet,
        call_frequency=call_freq,
        fold_frequency=fold_freq,
        pot_odds_equity=pot_eq,
        villain_open_range_pct=vil_range,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bbd_one_liner(r: BBDefenseRangeResult) -> str:
    return (
        f'[BBD vs {r.open_position.upper()}|{r.villain_type}] '
        f'defend={r.defense_frequency:.0%} 3bet={r.threebet_frequency:.0%}'
    )
