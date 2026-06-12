"""
C-Bet Continuation Rate Advisor (cbet_continuation_rate.py)

Guides optimal c-bet frequency across all streets and situations.
C-betting is the most common postflop action -- knowing WHEN to c-bet
and at what FREQUENCY is critical for winning poker.

C-BET THEORY:
  C-betting (continuation betting) after being PFR is the foundation of
  postflop aggression. The GTO c-bet frequency balances your range so
  villain cannot exploit you by calling or folding too much.

  FLOP C-BET:
    GTO baseline: ~55-65% (varies by position and board texture)
    Dry boards: higher frequency (less strong hands in villain's range)
    Wet boards: lower frequency (villain hits more often)
    IP: higher frequency; OOP: lower frequency

  TURN C-BET (after flop c-bet):
    GTO: ~45-55% (must have strong hand or strong draw)
    Turn c-bet represents a stronger range (double-barreling = strong)

  RIVER C-BET (third barrel):
    GTO: ~35-42% (very polarized -- nuts or bluff)
    River c-bet must be highly polarized; medium hands check

  SINGLE VS DOUBLE VS TRIPLE BARREL:
    Single (flop only):    Wide range including many bluffs/semi-bluffs
    Double (flop+turn):    Stronger range; must have good equity or draw
    Triple (all streets):  Polarized -- very strong or missed draw bluff

MULTI-STREET PLANNING:
  Before c-betting, plan for all streets:
  "If I bet flop, what happens on turn? What river?"
  Good c-bets have a plan through showdown.

DISTINCT FROM:
  triple_barrel.py:          Triple barrel bluff decision
  value_bet_sizing.py:       Sizing guide
  board_texture_advisor.py:  Board texture analysis
  THIS MODULE:               When and how OFTEN to c-bet each street;
                             multi-street continuation planning;
                             exploitative frequency adjustments

Usage:
    from poker.cbet_continuation_rate import advise_cbet_rate, CbetRateAdvice, ccr_one_liner

    result = advise_cbet_rate(
        hero_hand_category='top_pair',
        street='flop',
        hero_position='ip',
        board_texture='dry',
        villain_fold_to_cbet=0.50,
        villain_af=2.0,
        prior_cbets=0,
        hero_equity=0.62,
        pot_bb=20.0,
        spr=6.0,
    )
    print(ccr_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# GTO baseline c-bet frequencies by street + position
GTO_CBET_BASE = {
    ('flop', 'ip'):   0.62,
    ('flop', 'oop'):  0.52,
    ('turn', 'ip'):   0.52,
    ('turn', 'oop'):  0.44,
    ('river', 'ip'):  0.42,
    ('river', 'oop'): 0.35,
}

# Board texture adjustments (delta from baseline)
TEXTURE_ADJ = {
    'dry':      +0.10,
    'semi_wet':  0.00,
    'wet':      -0.12,
    'monotone': -0.15,
    'paired':   +0.05,
}

# Hand category contribution to c-bet frequency
HAND_ADJ = {
    'nuts':          +0.20,
    'set':           +0.18,
    'two_pair':      +0.15,
    'overpair':      +0.12,
    'top_pair':      +0.08,
    'flush_draw':    +0.05,   # semi-bluff
    'combo_draw':    +0.10,
    'straight_draw': +0.05,
    'air':           -0.05,   # bluff cbet
    'overcards':     -0.08,
    'middle_pair':   +0.00,
    'bottom_pair':   -0.05,
}


def _gto_cbet_freq(
    street: str,
    hero_position: str,
    board_texture: str,
    hero_hand_category: str,
    villain_fold_to_cbet: float,
    villain_af: float,
    prior_cbets: int,
) -> float:
    base = GTO_CBET_BASE.get((street, hero_position), 0.50)
    base += TEXTURE_ADJ.get(board_texture, 0.0)
    base += HAND_ADJ.get(hero_hand_category, 0.0)

    # Villain folds too much: increase c-bet freq
    if villain_fold_to_cbet >= 0.60:
        base += 0.10
    elif villain_fold_to_cbet <= 0.35:
        base -= 0.15  # villain calls too much; check more

    # Villain is aggressive: check more to avoid being raised off hand
    if villain_af >= 3.0:
        base -= 0.10
    elif villain_af <= 1.5:
        base += 0.05  # passive villain won't punish cbets

    # Prior cbets: double barrel requires stronger reason
    if prior_cbets >= 2:
        base -= 0.10   # third barrel is very selective

    return round(min(0.95, max(0.05, base)), 3)


def _should_cbet(
    cbet_freq: float,
    hero_hand_category: str,
    street: str,
    prior_cbets: int,
) -> bool:
    if hero_hand_category in ('nuts', 'set', 'two_pair', 'overpair', 'top_pair',
                               'flush_draw', 'combo_draw'):
        return True   # always c-bet value/strong semi-bluffs
    if cbet_freq >= 0.55:
        return True
    if street == 'river' and hero_hand_category not in ('air',) and prior_cbets < 2:
        return cbet_freq >= 0.40
    return cbet_freq >= 0.40


def _cbet_size(
    street: str,
    board_texture: str,
    hero_hand_category: str,
) -> float:
    """Recommended c-bet size as fraction of pot."""
    sizes = {
        ('flop', 'dry'):      0.55,
        ('flop', 'semi_wet'): 0.50,
        ('flop', 'wet'):      0.38,
        ('flop', 'monotone'): 0.33,
        ('turn', 'dry'):      0.65,
        ('turn', 'semi_wet'): 0.58,
        ('turn', 'wet'):      0.50,
        ('river', 'dry'):     0.75,
        ('river', 'semi_wet'): 0.70,
        ('river', 'wet'):     0.60,
    }
    base = sizes.get((street, board_texture), 0.55)
    # Strong hands: size up slightly for value
    if hero_hand_category in ('nuts', 'set', 'two_pair', 'overpair'):
        base = min(0.90, base + 0.08)
    return round(base, 2)


def _multi_street_plan(
    hero_hand_category: str,
    board_texture: str,
    hero_equity: float,
    spr: float,
) -> str:
    if hero_hand_category in ('set', 'two_pair', 'overpair', 'nuts'):
        return 'triple_barrel_value'
    elif hero_hand_category in ('top_pair',):
        if board_texture == 'dry':
            return 'double_barrel_plan'
        else:
            return 'single_then_evaluate'
    elif hero_hand_category in ('flush_draw', 'combo_draw'):
        if hero_equity >= 0.40:
            return 'semi_bluff_double_barrel'
        else:
            return 'semi_bluff_single_barrel'
    else:
        return 'single_barrel_or_give_up'


@dataclass
class CbetRateAdvice:
    # Inputs
    hero_hand_category: str
    street: str
    hero_position: str
    board_texture: str
    villain_fold_to_cbet: float
    villain_af: float
    prior_cbets: int
    hero_equity: float
    pot_bb: float
    spr: float

    # Analysis
    gto_cbet_freq: float
    should_cbet: bool
    cbet_size: float
    multi_street_plan: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_cbet_rate(
    hero_hand_category: str = 'top_pair',
    street: str = 'flop',
    hero_position: str = 'ip',
    board_texture: str = 'dry',
    villain_fold_to_cbet: float = 0.50,
    villain_af: float = 2.0,
    prior_cbets: int = 0,
    hero_equity: float = 0.62,
    pot_bb: float = 20.0,
    spr: float = 6.0,
) -> CbetRateAdvice:
    """
    Advise on c-bet frequency and continuation strategy.

    Args:
        hero_hand_category:    Current hand category
        street:                'flop' / 'turn' / 'river'
        hero_position:         'ip' / 'oop'
        board_texture:         'dry' / 'semi_wet' / 'wet' / 'monotone' / 'paired'
        villain_fold_to_cbet:  Villain's fold-to-cbet stat
        villain_af:            Villain's AF
        prior_cbets:           How many streets hero has already bet (0=first bet)
        hero_equity:           Current equity
        pot_bb:                Current pot
        spr:                   Stack-to-pot ratio

    Returns:
        CbetRateAdvice
    """
    freq = _gto_cbet_freq(street, hero_position, board_texture, hero_hand_category,
                           villain_fold_to_cbet, villain_af, prior_cbets)
    do_cbet = _should_cbet(freq, hero_hand_category, street, prior_cbets)
    size = _cbet_size(street, board_texture, hero_hand_category)
    ms_plan = _multi_street_plan(hero_hand_category, board_texture, hero_equity, spr)

    barrel_label = {0: 'first_barrel', 1: 'double_barrel', 2: 'triple_barrel'}.get(prior_cbets, 'extra_barrel')

    verdict = (
        f'[CCR {hero_hand_category}|{street}|{barrel_label}] '
        f'{"CBET" if do_cbet else "CHECK"} {size:.0%}pot '
        f'| freq={freq:.0%} plan={ms_plan}'
    )

    reasoning = (
        f'C-bet rate: {hero_hand_category} on {board_texture} {street}. '
        f'Position={hero_position}. Prior_cbets={prior_cbets} ({barrel_label}). '
        f'GTO_freq={freq:.0%}. Size={size:.0%}pot. '
        f'FoldToCbet={villain_fold_to_cbet:.0%} AF={villain_af:.1f}. '
        f'Plan={ms_plan}. Should_cbet={do_cbet}.'
    )

    tips = []

    tips.append(
        f'C-BET FREQUENCY: {hero_hand_category} on {board_texture} {street} = {freq:.0%} c-bet rate. '
        f'Recommended size: {size:.0%} pot ({size * pot_bb:.1f}BB). '
        f'Multi-street plan: {ms_plan.upper().replace("_", " ")}.'
    )

    tips.append(
        f'BARREL COUNT: This is {barrel_label.upper().replace("_", " ")}. '
        f'Each additional barrel narrows hero\'s range. '
        f'Triple barrel = very polarized (nuts or bluff). '
        f'Villain respects multi-barrel more if you are selective.'
    )

    if villain_fold_to_cbet >= 0.60:
        tips.append(
            f'EXPLOITABLE FOLDER (fold_to_cbet={villain_fold_to_cbet:.0%}): '
            f'Increase c-bet frequency. '
            f'Villain folds too often -- profitable to c-bet wide. '
            f'Bluff with more hands than GTO (air, overcards, weak draws).'
        )
    elif villain_fold_to_cbet <= 0.35:
        tips.append(
            f'C-BET CALLER (fold_to_cbet={villain_fold_to_cbet:.0%}): '
            f'Reduce c-bet frequency. '
            f'Villain calls too often -- only c-bet strong value and strong draws. '
            f'Check and give up with air and marginal hands.'
        )

    if villain_af >= 3.0:
        tips.append(
            f'AGGRESSIVE VILLAIN (AF={villain_af:.1f}): '
            f'Check more to induce bluffs. '
            f'C-betting into aggressive villain risks getting raised off your hand. '
            f'Check strong hands too (mix check-raise into range).'
        )

    if prior_cbets >= 2:
        tips.append(
            f'THIRD BARREL: Very selective bet. '
            f'Your range should be: nuts/near-nuts OR missed draws as bluffs. '
            f'Medium hands (top pair) should usually check river to showdown. '
            f'Triple barrel bluffs work best with blockers + good fold equity.'
        )

    return CbetRateAdvice(
        hero_hand_category=hero_hand_category,
        street=street,
        hero_position=hero_position,
        board_texture=board_texture,
        villain_fold_to_cbet=villain_fold_to_cbet,
        villain_af=villain_af,
        prior_cbets=prior_cbets,
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        spr=spr,
        gto_cbet_freq=freq,
        should_cbet=do_cbet,
        cbet_size=size,
        multi_street_plan=ms_plan,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ccr_one_liner(r: CbetRateAdvice) -> str:
    return (
        f'[CCR {r.hero_hand_category}|{r.street}|{r.hero_position}] '
        f'{"CBET" if r.should_cbet else "CHECK"} {r.cbet_size:.0%}pot '
        f'| freq={r.gto_cbet_freq:.0%} plan={r.multi_street_plan}'
    )
