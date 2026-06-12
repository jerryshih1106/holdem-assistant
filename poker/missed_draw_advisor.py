"""
Missed Draw Advisor (missed_draw_advisor.py)

When hero holds a draw (flush draw, straight draw, combo draw) and it does NOT
complete on the next card, hero faces one of the most complex decisions in poker:

  1. Give up: check-fold / fold to a bet
  2. Continue bluffing: bet or raise as a semi-bluff (now pure bluff since draw missed)
  3. Check-call: if hero still has some showdown value (high cards, pair + missed draw)

Why this matters:
  - Mechanically giving up every missed draw = over-folding, easily exploitable
  - Blindly firing on missed draws = over-bluffing, leaking chips
  - Correct answer depends on: blockers, board, villain tendencies, previous action

Key variables:
  1. Draw type: flush draw (9 outs), OESD (8), gutshot (4), combo (12+)
  2. Remaining outs if any: sometimes draw partially missed but still has backdoor outs
  3. Showdown value: does hero's hand have any value at showdown? (e.g., A-high has SDV)
  4. Blocker quality: does hero's missed draw card block villain's value range?
     - Missed flush draw: hero holds two suited cards → blocks flush combos in villain's range
     - Missed straight: hero holds connector cards → blocks some straights
  5. Board is scary: an overcard or scare card fell, which might make villain check back
  6. Villain's fold frequency to bets: affects bluff EV

EV(bluff) = fold_freq × pot - (1 - fold_freq) × bet_size
EV(check) = sdv_equity × pot_bb (simplified)

Bluff is profitable when:
  fold_freq > bet_size / (pot + bet_size) = alpha

Sizing: missed draws should typically use smaller bets (50-67% pot) on turn,
larger bets (75-100% pot) on river when range is more polarized.

Showdown value:
  - A-high or K-high with missed flush draw: ~20-30% SDV
  - Overcards + missed gut-shot: ~15-25% SDV
  - Low connected cards that missed everything: ~0-5% SDV

Blocker value for missed flush:
  - Ace of suit: blocks strongest flush combos
  - King of suit: blocks second-nut flush
  - Low cards of suit: minimal blocker value

Usage:
    from poker.missed_draw_advisor import advise_missed_draw, MissedDrawAdvice
    from poker.missed_draw_advisor import missed_draw_one_liner

    result = advise_missed_draw(
        draw_type='flush_draw',
        street='turn',
        hero_pos='IP',
        board_type='wet',
        villain_fold_to_bet=0.45,
        hero_sdv=0.20,
        has_blocker=True,
        pot_bb=25.0,
        hero_stack_bb=80.0,
        villain_af=2.0,
        n_opponents=1,
    )
    print(result.action, result.bluff_ev)
"""

from dataclasses import dataclass, field
from typing import List


def _draw_strength(draw_type: str) -> dict:
    """Returns initial outs and basic properties for the draw type."""
    return {
        'flush_draw': {'outs': 9, 'blocker_value': 0.40, 'sdv_bonus': 0.10},
        'oesd': {'outs': 8, 'blocker_value': 0.20, 'sdv_bonus': 0.05},
        'combo_draw': {'outs': 12, 'blocker_value': 0.30, 'sdv_bonus': 0.10},
        'gutshot': {'outs': 4, 'blocker_value': 0.15, 'sdv_bonus': 0.02},
        'backdoor_flush': {'outs': 2, 'blocker_value': 0.20, 'sdv_bonus': 0.05},
        'overcards': {'outs': 6, 'blocker_value': 0.10, 'sdv_bonus': 0.08},
    }.get(draw_type.lower(), {'outs': 4, 'blocker_value': 0.10, 'sdv_bonus': 0.03})


def _optimal_bet_pct(street: str, hero_pos: str, board_type: str, has_blocker: bool) -> float:
    """Recommended bluff bet as fraction of pot."""
    if street == 'river':
        # River bluff: larger, polarized sizing
        base = 0.75
        if has_blocker:
            base += 0.10   # Strong blocker: can bet larger
        if board_type == 'wet':
            base -= 0.05   # Wet board: villain may have draws too; size down
        if hero_pos == 'OOP':
            base -= 0.05
    elif street == 'turn':
        base = 0.55
        if has_blocker:
            base += 0.05
        if board_type == 'wet':
            base -= 0.05
        if hero_pos == 'OOP':
            base -= 0.05
    else:
        base = 0.50

    return round(min(1.00, max(0.33, base)), 2)


def _fold_frequency_needed(bet_pct: float) -> float:
    """Minimum fold frequency for bluff to break even: alpha = bet/(pot+bet)."""
    return round(bet_pct / (1.0 + bet_pct), 4)


def _adjusted_fold_freq(
    villain_fold_to_bet: float,
    street: str,
    board_type: str,
    villain_af: float,
    n_opponents: int,
) -> float:
    """Adjusted fold frequency based on street/board/villain."""
    fold = villain_fold_to_bet

    # River: villain has less reason to fold made hands
    if street == 'river':
        fold -= 0.08
    # Wet board: villain has draws themselves → calls more
    if board_type == 'wet':
        fold -= 0.05
    elif board_type == 'dry':
        fold += 0.03

    # Aggressive villain: less fold equity (they raise more, not fold)
    if villain_af >= 3.0:
        fold -= 0.08
    elif villain_af >= 2.0:
        fold -= 0.03
    elif villain_af < 1.0:
        fold += 0.08   # Passive villain: checks and folds more

    # Multiway: need all opponents to fold
    if n_opponents >= 2:
        fold = fold ** n_opponents  # independent fold probability per opponent

    return round(min(0.90, max(0.05, fold)), 3)


def _bluff_ev(
    pot_bb: float,
    bet_pct: float,
    adj_fold_freq: float,
) -> float:
    """EV of bluffing: EV = f × pot - (1-f) × bet."""
    bet = pot_bb * bet_pct
    return round(adj_fold_freq * pot_bb - (1 - adj_fold_freq) * bet, 2)


def _check_ev(hero_sdv: float, pot_bb: float) -> float:
    """Simplified EV of checking/giving up: hero wins pot × SDV equity."""
    return round(hero_sdv * pot_bb, 2)


def _blocker_score(draw_type: str, has_blocker: bool, has_ace_blocker: bool) -> float:
    """Score representing how well hero's cards block villain's value range."""
    props = _draw_strength(draw_type)
    if not has_blocker:
        return 0.0
    base = props['blocker_value']
    if has_ace_blocker:
        base = min(0.70, base + 0.20)
    return round(base, 2)


def _action(
    ev_bluff: float,
    ev_check: float,
    adj_fold_freq: float,
    alpha: float,
    hero_sdv: float,
    street: str,
    n_opponents: int,
) -> tuple:
    """Returns (action, reasoning)."""
    # Multiway: bluffing is much harder
    if n_opponents >= 2:
        if ev_bluff > ev_check and adj_fold_freq >= alpha * 1.2:
            return (
                'bluff',
                f'Multiway bluff: requires high fold freq ({alpha:.0%} needed, {adj_fold_freq:.0%} estimated × {n_opponents} opponents). '
                f'EV_bluff={ev_bluff:.1f}BB > EV_check={ev_check:.1f}BB.'
            )
        return (
            'check_fold',
            f'Multiway ({n_opponents} opponents): fold equity too low. '
            f'Need all opponents to fold. EV_bluff={ev_bluff:.1f}BB < EV_check={ev_check:.1f}BB.'
        )

    # Bluff is profitable
    if ev_bluff > 0 and ev_bluff > ev_check:
        return (
            'bluff',
            f'Bluff: EV_bluff={ev_bluff:.1f}BB > EV_check={ev_check:.1f}BB. '
            f'Fold_freq={adj_fold_freq:.0%} > alpha={alpha:.0%}.'
        )

    # Has showdown value → check-call on turn, check-fold on river
    if hero_sdv >= 0.25:
        if street == 'river':
            return (
                'check_call',
                f'SDV={hero_sdv:.0%}: hand has showdown value. '
                f'Check-call river if villain bets small.'
            )
        return (
            'check_call',
            f'SDV={hero_sdv:.0%}: check-call. '
            f'Turn: may improve to best hand on river or villain checks behind.'
        )

    # Low SDV, bluff not profitable → give up
    return (
        'check_fold',
        f'Give up: EV_bluff={ev_bluff:.1f}BB < EV_check={ev_check:.1f}BB. '
        f'SDV={hero_sdv:.0%} too low to check-call. '
        f'Fold_freq={adj_fold_freq:.0%} < alpha={alpha:.0%}.'
    )


@dataclass
class MissedDrawAdvice:
    """Advice for hero when draw misses on turn or river."""
    draw_type: str
    street: str
    hero_pos: str
    board_type: str
    villain_fold_to_bet: float
    hero_sdv: float         # Showdown value vs villain's check range
    has_blocker: bool       # Hero blocks some of villain's value combos
    has_ace_blocker: bool
    pot_bb: float
    hero_stack_bb: float
    villain_af: float
    n_opponents: int

    # Decision
    action: str             # 'bluff', 'check_call', 'check_fold'
    recommended_bet_pct: float
    recommended_bet_bb: float

    # EV breakdown
    bluff_ev: float
    check_ev: float
    ev_advantage: float     # bluff_ev - check_ev

    # Math
    fold_freq_needed: float   # alpha = break-even fold frequency
    adjusted_fold_freq: float  # estimated actual fold frequency
    blocker_score: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_missed_draw(
    draw_type: str = 'flush_draw',
    street: str = 'turn',
    hero_pos: str = 'IP',
    board_type: str = 'wet',
    villain_fold_to_bet: float = 0.45,
    hero_sdv: float = 0.20,
    has_blocker: bool = True,
    has_ace_blocker: bool = False,
    pot_bb: float = 25.0,
    hero_stack_bb: float = 80.0,
    villain_af: float = 2.0,
    n_opponents: int = 1,
) -> MissedDrawAdvice:
    """
    Advise hero when a draw missed and it's time to decide: bluff, check-call, or give up.

    Args:
        draw_type:          'flush_draw', 'oesd', 'combo_draw', 'gutshot', 'overcards'
        street:             'turn' or 'river'
        hero_pos:           'IP' or 'OOP'
        board_type:         'dry', 'medium', 'wet'
        villain_fold_to_bet: Villain's estimated fold frequency to hero's bet
        hero_sdv:           Hero's showdown value (0-1); A-high = ~0.25, low cards = ~0.05
        has_blocker:        True if hero's cards block villain's value combos
        has_ace_blocker:    True if hero holds the Ace of the flush suit
        pot_bb:             Pot size in BB
        hero_stack_bb:      Hero's remaining stack in BB
        villain_af:         Villain's aggression factor
        n_opponents:        Number of opponents

    Returns:
        MissedDrawAdvice
    """
    bet_pct = _optimal_bet_pct(street, hero_pos, board_type, has_blocker)
    alpha = _fold_frequency_needed(bet_pct)
    adj_fold = _adjusted_fold_freq(villain_fold_to_bet, street, board_type, villain_af, n_opponents)
    ev_bluff = _bluff_ev(pot_bb, bet_pct, adj_fold)
    ev_check = _check_ev(hero_sdv, pot_bb)
    blocker = _blocker_score(draw_type, has_blocker, has_ace_blocker)
    action, reasoning = _action(ev_bluff, ev_check, adj_fold, alpha, hero_sdv, street, n_opponents)

    # Build tips
    tips = []
    if action == 'bluff':
        tips.append(
            f'Bluff {bet_pct:.0%} pot ({pot_bb * bet_pct:.1f}BB). '
            f'Villain needs to fold {alpha:.0%}; estimated fold rate {adj_fold:.0%}. '
            f'EV={ev_bluff:.1f}BB. '
            f'{"Blockers help: you hold cards that reduce villain value combos. " if has_blocker else ""}'
            f'Fire confidently — fold equity justifies the risk.'
        )
        if street == 'turn' and n_opponents == 1:
            tips.append(
                'Turn bluff: if called, reassess river. '
                'Only fire river again if: (a) a scare card hits, '
                '(b) you have strong blocker, or (c) villain checks (weak signal).'
            )
    elif action == 'check_call':
        tips.append(
            f'Check with SDV={hero_sdv:.0%}. If villain bets large (>60% pot), fold. '
            f'If villain checks back, you may win at showdown or get free card. '
            f'SDV hands: A-high, K-high with missed flush draw, overcards.'
        )
    else:  # check_fold
        tips.append(
            f'Give up: bluff EV={ev_bluff:.1f}BB not profitable (need {alpha:.0%} fold, '
            f'estimated only {adj_fold:.0%}). SDV={hero_sdv:.0%} too low to check-call. '
            f'Check and fold to any bet.'
        )
        if n_opponents >= 2:
            tips.append(
                f'Multiway ({n_opponents} opponents): bluffing into multiple opponents '
                f'requires each one to fold — probability compounds multiplicatively. '
                f'Reserve bluffs for heads-up pots on this type of board.'
            )

    if has_blocker and action != 'check_fold':
        tips.append(
            f'Blocker advantage (score={blocker:.2f}): '
            f'{"Ace-high blocker — reduces villain nut flush combos significantly. " if has_ace_blocker else ""}'
            f'Your missed draw cards block villain\'s strongest hands. '
            f'This makes your bluff more likely to succeed and increases your call-back EV.'
        )

    if board_type == 'dry' and action == 'check_fold':
        tips.append(
            'Dry board: villain likely has a made hand and will call wide. '
            'Correct to give up missed draws on dry boards — fold equity is minimal.'
        )

    if not tips:
        tips.append(
            f'Missed {draw_type} on {street}: {action}. '
            f'EV_bluff={ev_bluff:.1f}BB, EV_check={ev_check:.1f}BB, '
            f'fold={adj_fold:.0%} vs alpha={alpha:.0%}.'
        )

    return MissedDrawAdvice(
        draw_type=draw_type,
        street=street,
        hero_pos=hero_pos,
        board_type=board_type,
        villain_fold_to_bet=round(villain_fold_to_bet, 3),
        hero_sdv=round(hero_sdv, 3),
        has_blocker=has_blocker,
        has_ace_blocker=has_ace_blocker,
        pot_bb=round(pot_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        villain_af=round(villain_af, 2),
        n_opponents=n_opponents,
        action=action,
        recommended_bet_pct=bet_pct,
        recommended_bet_bb=round(pot_bb * bet_pct, 1),
        bluff_ev=ev_bluff,
        check_ev=ev_check,
        ev_advantage=round(ev_bluff - ev_check, 2),
        fold_freq_needed=alpha,
        adjusted_fold_freq=adj_fold,
        blocker_score=blocker,
        reasoning=reasoning,
        tips=tips,
    )


def missed_draw_one_liner(result: MissedDrawAdvice) -> str:
    return (
        f'[MDA {result.draw_type[:5]}@{result.street}|{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'EV_bluff={result.bluff_ev:.1f} EV_chk={result.check_ev:.1f} | '
        f'fold={result.adjusted_fold_freq:.0%} alpha={result.fold_freq_needed:.0%} | '
        f'blkr={result.blocker_score:.2f}'
    )
