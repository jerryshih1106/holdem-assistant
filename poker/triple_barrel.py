"""
Triple Barrel Advisor (triple_barrel.py)

A triple barrel is a 3-street bluff or value bet sequence: cbet flop,
barrel turn, barrel river. It requires the most commitment of any
aggression line and carries the highest risk/reward profile.

Key decision factors:
  1. Hand type: value hands barrel 100%, bluffs must have equity or
     strong blockers to justify 3 streets
  2. Villain profile: passive fish call down too much → fewer bluffs;
     tight/solid regs fold too much → more bluffs
  3. Board runout: blank-blank runouts (villain's draws bricked) are
     ideal for triple barrels; completing draws hurt triple barrel lines
  4. Position: in position barrels are more credible and lower-risk
  5. Bet sizing: decreasing sizes signal weakness; increasing or
     consistent sizes signal strength/polarization

Triple barrel bluff math:
  If villain folded to flop cbet P1 of the time and
  villain folds on each street independently (approximation):
    3-street fold rate = 1 - (1-P1)(1-P2)(1-P3)
  For EV to be positive vs a pot-sized 3-barrel:
    fold rate per street needs to be roughly 45%+

When NOT to triple barrel:
  - Villain is a calling station (WTSD > 45%)
  - Board ran out in villain's favor (draws completed)
  - Villain check-raised flop/turn (range is capped strong)
  - Hero has significant showdown value (SDV) — check back instead

Usage:
    from poker.triple_barrel import advise_triple_barrel, TripleBarrelAdvice
    result = advise_triple_barrel(
        hero_hand_class='air',
        hero_equity=0.12,
        flop_cbet_pct=0.65,
        turn_barrel_pct=0.55,
        river_board_type='blank',
        pot_bb=28.0,
        eff_stack_bb=72.0,
        villain_wtsd=0.28,
        villain_af=2.2,
        villain_fold_cbet=0.48,
        hero_has_blocker=False,
        hero_in_position=True,
    )
    print(result.action, result.river_bet_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0,
        'draw': 1, 'speculative': 1,
        'bottom_pair': 2, 'marginal': 2,
        'middle_pair': 3,
        'top_pair': 4, 'tptk': 5,
        'overpair': 6,
        'two_pair': 7,
        'set': 8, 'flush': 8, 'straight': 8,
        'premium': 9,
    }.get(hand_class.lower(), 3)


def _villain_fold_river(wtsd: float, af: float, fold_cbet: float) -> float:
    """
    Estimate villain fold rate on river vs a triple barrel.
    Players who fold to cbets often and rarely go to showdown fold more on river.
    """
    base = 0.40
    # High WTSD → calls a lot
    wtsd_adj = -(wtsd - 0.30) * 1.5
    # High AF → fights back or calls frequently
    af_adj = -(af - 2.0) * 0.05
    # Fold-to-cbet: high fold-cbet means villain folds draws and weak hands
    cbet_adj = (fold_cbet - 0.45) * 0.30
    return round(max(0.25, min(0.70, base + wtsd_adj + af_adj + cbet_adj)), 3)


def _cumulative_fold(p_flop: float, p_turn: float, p_river: float) -> float:
    """Probability villain folds on any of the 3 streets."""
    survive = (1 - p_flop) * (1 - p_turn) * (1 - p_river)
    return round(1 - survive, 3)


def _river_sizing(hand_rank: int, board_type: str, hero_in_pos: bool) -> float:
    """River bet as fraction of pot."""
    if hand_rank >= 7:    # value: set/two pair+
        size = 0.75
    elif hand_rank >= 5:  # tptk/overpair
        size = 0.65
    elif hand_rank == 0:  # pure bluff
        size = 0.65       # polarized river bluff typical sizing
    else:
        size = 0.55
    # Board adjustments
    if board_type in ('blank', 'dry'):
        size += 0.05      # can size up on boards where villain has few nutted hands
    elif board_type in ('wet', 'completed_flush', 'completed_straight'):
        size -= 0.10      # board is scary for villain too; use smaller bluff
    # Position premium
    if not hero_in_pos:
        size -= 0.05
    return round(min(1.20, max(0.40, size)), 2)


def _ev_triple_barrel(
    pot_bb: float,
    fold_rate: float,
    hero_equity: float,
    bet_bb: float,
) -> float:
    """EV = fold_rate * pot + (1-fold) * [equity*(pot+2bet) - bet]"""
    ev = fold_rate * pot_bb + (1 - fold_rate) * (hero_equity * (pot_bb + 2 * bet_bb) - bet_bb)
    return round(ev, 2)


@dataclass
class TripleBarrelAdvice:
    """Advice on whether and how to fire the 3rd barrel (river)."""
    hero_hand_class: str
    hero_equity: float
    pot_bb: float
    eff_stack_bb: float

    # Decision
    action: str          # 'fire_3', 'check_back', 'check_call'
    river_bet_bb: float
    river_bet_pct: float
    fire_freq: float     # recommended frequency if mixed

    # Villain model
    villain_fold_river: float
    cumulative_fold_rate: float  # across all 3 streets

    # EV
    ev_fire_bb: float
    ev_check_bb: float   # EV of checking (SDV based)

    # Context
    is_value_bet: bool
    has_blocker_advantage: bool
    reasoning: str
    strategic_tips: List[str] = field(default_factory=list)


def advise_triple_barrel(
    hero_hand_class: str = 'air',
    hero_equity: float = 0.12,
    flop_cbet_pct: float = 0.65,
    turn_barrel_pct: float = 0.55,
    river_board_type: str = 'blank',
    pot_bb: float = 28.0,
    eff_stack_bb: float = 72.0,
    villain_wtsd: float = 0.30,
    villain_af: float = 2.0,
    villain_fold_cbet: float = 0.45,
    hero_has_blocker: bool = False,
    hero_in_position: bool = True,
) -> TripleBarrelAdvice:
    """
    Advise on firing a 3rd barrel (river continuation bet after
    cbetting flop and barreling turn).

    Args:
        hero_hand_class:    Hero's made hand classification
        hero_equity:        Showdown equity (0-1), 0.12 for pure air
        flop_cbet_pct:      Fraction of hero's flop range that cbets
        turn_barrel_pct:    Fraction of hero's turn range that barrels
        river_board_type:   'blank', 'dry', 'wet', 'completed_flush',
                            'completed_straight', 'broadway'
        pot_bb:             Current pot size before river bet
        eff_stack_bb:       Remaining effective stack
        villain_wtsd:       Villain's went-to-showdown frequency
        villain_af:         Villain's aggression factor
        villain_fold_cbet:  Villain's fold-to-cbet on earlier streets
        hero_has_blocker:   Hero holds a key blocker (e.g., nut flush blocker)
        hero_in_position:   Hero acts last on river

    Returns:
        TripleBarrelAdvice
    """
    rank = _hand_rank(hero_hand_class)
    is_value = rank >= 7  # set or better gets all value-bet treatment

    villain_fold = _villain_fold_river(villain_wtsd, villain_af, villain_fold_cbet)
    cum_fold = _cumulative_fold(villain_fold_cbet, villain_fold_cbet, villain_fold)
    size_pct = _river_sizing(rank, river_board_type, hero_in_position)
    bet_bb = round(pot_bb * size_pct, 1)

    # Blocker bonus: having the nut blocker increases bluff credibility
    blocker_adj = 0.08 if hero_has_blocker else 0.0
    effective_fold = min(0.75, villain_fold + blocker_adj)

    ev_fire = _ev_triple_barrel(pot_bb, effective_fold, hero_equity, bet_bb)
    # EV of checking: showdown value
    ev_check = round(hero_equity * pot_bb * 0.85, 2)  # slight discount (villain may bet)

    # Completed boards are bad for bluffs
    board_is_bad = river_board_type in ('completed_flush', 'completed_straight', 'wet')
    can_bluff = (
        effective_fold >= 0.45 and
        not board_is_bad and
        hero_equity < 0.40  # else has SDV → check
    )
    has_sdv = hero_equity >= 0.35 and not is_value

    # Decision logic
    if is_value:
        action = 'fire_3'
        fire_freq = 1.0
        reasoning = (
            f'VALUE triple barrel with {hero_hand_class} (rank={rank}). '
            f'Extract max value. Size: {size_pct:.0%}pot = {bet_bb:.1f}BB.'
        )
    elif has_sdv and not hero_has_blocker:
        action = 'check_back'
        fire_freq = 0.0
        reasoning = (
            f'{hero_hand_class} has showdown value ({hero_equity:.0%} equity). '
            f'Triple barreling folds out villain\'s bluff-catching range but '
            f'hero can\'t bluff efficiently. CHECK BACK and win at showdown.'
        )
    elif can_bluff and ev_fire >= ev_check:
        action = 'fire_3'
        fire_freq = min(1.0, round(effective_fold * 1.5, 2))
        reasoning = (
            f'BLUFF triple barrel. Villain folds {effective_fold:.0%} on river. '
            f'EV fire = {ev_fire:.1f}BB vs check = {ev_check:.1f}BB. '
            + ('Blocker boosts credibility. ' if hero_has_blocker else '')
            + f'Size: {size_pct:.0%}pot = {bet_bb:.1f}BB.'
        )
    elif board_is_bad:
        action = 'check_back' if hero_equity >= 0.20 else 'check_back'
        fire_freq = 0.10
        reasoning = (
            f'Board runout ({river_board_type}) favors villain\'s range. '
            f'Triple barrel bluff is too risky. Give up and check back.'
        )
    else:
        action = 'check_back'
        fire_freq = 0.15
        reasoning = (
            f'Villain fold rate ({effective_fold:.0%}) too low for profitable bluff. '
            f'EV fire = {ev_fire:.1f}BB < check = {ev_check:.1f}BB. Give up.'
        )

    # Strategic tips
    tips = []
    if villain_wtsd >= 0.40:
        tips.append(
            f'Calling station (WTSD={villain_wtsd:.0%}): avoid bluffing. '
            f'Only triple barrel with strong value hands.'
        )
    if hero_in_position:
        tips.append(
            'In position: can choose bet or check-back freely. '
            'Prefer checking back SDV hands to capture villain bluffs.'
        )
    else:
        tips.append(
            'Out of position: smaller bluff sizing is preferred (0.50-0.65 pot). '
            'OOP triple barrels require more fold equity.'
        )
    if hero_has_blocker:
        tips.append(
            'Blocker gives your bluff extra credibility: villain must fold more '
            'of their range since key combos are blocked.'
        )
    if river_board_type == 'blank':
        tips.append(
            'Blank river: villain\'s draw-heavy hands missed. Ideal spot to fire. '
            'Villain\'s range narrows to medium-strength made hands → bluffs work well.'
        )

    return TripleBarrelAdvice(
        hero_hand_class=hero_hand_class,
        hero_equity=hero_equity,
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        action=action,
        river_bet_bb=bet_bb if action == 'fire_3' else 0.0,
        river_bet_pct=size_pct if action == 'fire_3' else 0.0,
        fire_freq=fire_freq,
        villain_fold_river=villain_fold,
        cumulative_fold_rate=cum_fold,
        ev_fire_bb=ev_fire,
        ev_check_bb=ev_check,
        is_value_bet=is_value,
        has_blocker_advantage=hero_has_blocker,
        reasoning=reasoning,
        strategic_tips=tips,
    )


def triple_barrel_one_liner(result: TripleBarrelAdvice) -> str:
    action_str = result.action.upper().replace('_', '-')
    ev_str = f'+{result.ev_fire_bb:.1f}' if result.ev_fire_bb >= 0 else f'{result.ev_fire_bb:.1f}'
    return (
        f'[3B {result.hero_hand_class}] {action_str} '
        f'(freq={result.fire_freq:.0%}) | '
        f'bet={result.river_bet_bb:.0f}BB | '
        f'vfold={result.villain_fold_river:.0%} | EV={ev_str}BB'
    )
