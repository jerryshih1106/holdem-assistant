"""
Free Card Play Advisor (free_card_play_advisor.py)

The "free card play" is a classic semi-bluff tactic: raise on the flop
(or turn) with a drawing hand, so that your opponent checks to you on
the next street, allowing you to see that card for free.

MECHANICS:
  1. Hero has a draw (flush draw, straight draw, etc.)
  2. Hero raises villain's flop bet (or bets into villain OOP)
  3. Villain calls the raise but is now uncertain about hero's hand
  4. Villain typically checks the turn, giving hero a "free card"
  5. Hero can now bet if they hit, or check back if they miss

EV ANALYSIS:
  EV(free_card_play) = [
    fold_pct * pot_before_raise             +   (villain folds flop)
    (1-fold_pct) * free_card_pct * [        +   (villain calls, then checks turn)
      hit_pct * EV_when_hit                 +
      (1-hit_pct) * EV_when_miss_check_back
    ]                                       +
    (1-fold_pct) * (1-free_card_pct) * [       (villain calls, then bets turn)
      EV_when_villain_bets_turn
    ]
  ]

WHEN FREE CARD PLAYS WORK:
  - Against tight players who check when scared (nits, TAG players)
  - IP (in position) where hero can bet turn if they hit
  - Strong draws (9+ outs: flush draws, open-ended straight draws)
  - When the raise looks like a value hand raise (disguise)

WHEN THEY FAIL:
  - Against calling stations (villain never folds, always bets turn anyway)
  - OOP (villain bets into hero on turn, denying the free card)
  - Weak draws (<6 outs) where hitting turn doesn't win often
  - Against aggressive LAG players who re-raise raises

Usage:
    from poker.free_card_play_advisor import advise_free_card_play, FreeCardPlayAdvice, fcp_one_liner

    advice = advise_free_card_play(
        draw_type='flush_draw',
        hero_position='IP',
        villain_vpip=0.22,
        villain_af=2.0,
        pot_bb=15.0,
        villain_bet_bb=10.0,
        hero_raise_to_bb=28.0,
        street='flop',
    )
    print(fcp_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List

# Draw strength: (outs, flop_to_turn_equity, flop_to_river_equity, label)
_DRAW_STATS = {
    'flush_draw':         (9,  0.19, 0.35, 'flush draw'),
    'open_ended':         (8,  0.17, 0.32, 'open-ended straight draw'),
    'combo_draw':         (15, 0.32, 0.54, 'combo draw (flush+straight)'),
    'gutshot':            (4,  0.09, 0.17, 'gutshot'),
    'two_overcards':      (6,  0.13, 0.24, 'two overcards'),
    'flush_plus_gut':     (12, 0.26, 0.45, 'flush draw + gutshot'),
    'pair_plus_fd':       (14, 0.30, 0.52, 'pair + flush draw'),
    'backdoor_fd':        (3,  0.06, 0.12, 'backdoor flush draw'),
}

# Villain type -> probability they check turn after calling raise
_CHECK_TURN_PROB = {
    'nit':            0.80,   # nits check when scared after raise
    'tag':            0.65,   # solid regs check sometimes
    'lag':            0.35,   # LAG players barrel turn anyway
    'fish':           0.45,   # fish play passively sometimes
    'calling_station':0.55,   # station calls but often checks turn
    'unknown':        0.55,
}

# Villain type -> fold to raise probability (flop)
_FOLD_TO_RAISE = {
    'nit':            0.45,
    'tag':            0.35,
    'lag':            0.20,
    'fish':           0.15,
    'calling_station':0.10,
    'unknown':        0.30,
}


def _classify_villain(vpip: float, af: float) -> str:
    if vpip < 0.18 and af < 2.5:   return 'nit'
    if vpip < 0.28 and af > 2.5:   return 'tag'
    if vpip > 0.35 and af > 3.0:   return 'lag'
    if vpip > 0.40 and af < 2.0:   return 'calling_station'
    if vpip > 0.35:                 return 'fish'
    return 'unknown'


def _ev_free_card(
    pot: float,
    villain_bet: float,
    hero_raise: float,
    outs: float,
    hit_equity: float,
    fold_pct: float,
    check_turn_pct: float,
) -> float:
    """
    Simplified EV of the free card play.
    """
    # If villain folds: hero wins pot + villain bet
    ev_fold = fold_pct * (pot + villain_bet)

    # Hero's investment in the raise (net additional chips after calling bet)
    hero_investment = hero_raise - villain_bet  # extra chips beyond calling the bet

    # Called scenarios
    called_pct = 1 - fold_pct

    # If villain checks turn (free card achieved):
    hit_pct = outs / 46.0  # rough: outs out of 46 remaining cards
    # When hero hits: EV of winning a bigger pot
    ev_hit = hit_pct * (pot + villain_bet + hero_raise)  # win the pot
    # When hero misses and checks back: EV roughly 0 (check/fold decision later)
    ev_miss_check = (1 - hit_pct) * 0.0  # simplified: hero checks, wins nothing from this line
    ev_free_card = check_turn_pct * (ev_hit + ev_miss_check)

    # If villain bets turn (free card denied):
    # Hero typically folds with miss (~hit_pct gets to showdown)
    ev_villain_bets = (1 - check_turn_pct) * (hit_pct * (pot + villain_bet + hero_raise) - hero_raise)

    ev_called = called_pct * (ev_free_card + ev_villain_bets)

    # Net EV (subtract hero's investment from raise)
    net_ev = ev_fold + ev_called - hero_investment * called_pct

    return round(net_ev, 3)


def _ev_just_call(pot: float, villain_bet: float, hit_pct: float) -> float:
    """EV of just calling the flop bet (no raise) -- baseline comparison."""
    pot_after = pot + 2 * villain_bet
    ev = hit_pct * pot_after - villain_bet
    return round(ev, 3)


@dataclass
class FreeCardPlayAdvice:
    # Inputs
    draw_type: str
    hero_position: str
    villain_type: str
    pot_bb: float
    villain_bet_bb: float
    hero_raise_to_bb: float
    street: str

    # Draw stats
    outs: int
    hit_equity_this_street: float   # probability of hitting on next card
    draw_label: str

    # Villain tendencies
    fold_to_raise_pct: float
    check_turn_pct: float

    # EV analysis
    ev_free_card_play: float
    ev_just_call: float
    ev_advantage: float             # FCP vs calling

    # Decision
    recommended_action: str         # 'raise_free_card', 'call', 'fold'
    free_card_play_feasible: bool
    confidence: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_free_card_play(
    draw_type: str = 'flush_draw',
    hero_position: str = 'IP',
    villain_vpip: float = 0.22,
    villain_af: float = 2.0,
    pot_bb: float = 15.0,
    villain_bet_bb: float = 10.0,
    hero_raise_to_bb: float = 28.0,
    street: str = 'flop',
) -> FreeCardPlayAdvice:
    """
    Advise whether to make a "free card play" (raise a draw for a free card).

    Args:
        draw_type:       Type of draw ('flush_draw', 'open_ended', 'gutshot', etc.)
        hero_position:   'IP' or 'OOP'
        villain_vpip:    Villain VPIP
        villain_af:      Villain aggression factor
        pot_bb:          Current pot in BB
        villain_bet_bb:  Villain's flop bet in BB
        hero_raise_to_bb: Hero's proposed raise size in BB total
        street:          'flop' or 'turn'

    Returns:
        FreeCardPlayAdvice
    """
    draw_stats = _DRAW_STATS.get(draw_type, _DRAW_STATS['flush_draw'])
    outs, hit_eq, river_eq, draw_label = draw_stats

    vtype = _classify_villain(villain_vpip, villain_af)
    fold_pct = _FOLD_TO_RAISE[vtype]
    check_turn = _CHECK_TURN_PROB[vtype]

    # Position adjustment: OOP makes free card plays worse (villain bets turn more)
    if hero_position == 'OOP':
        check_turn = max(0.20, check_turn - 0.15)
        fold_pct = max(0.05, fold_pct - 0.05)

    ev_fcp = _ev_free_card(
        pot_bb, villain_bet_bb, hero_raise_to_bb,
        outs, hit_eq, fold_pct, check_turn
    )
    ev_call = _ev_just_call(pot_bb, villain_bet_bb, hit_eq)
    ev_adv = round(ev_fcp - ev_call, 3)

    # Feasibility checks
    feasible = (
        outs >= 6 and              # need reasonable draw
        hero_position == 'IP' and  # best when IP
        vtype not in ('calling_station', 'lag')  # doesn't work vs those
    )

    if ev_fcp > ev_call and feasible:
        action = 'raise_free_card'
        conf = 'strong' if ev_adv > 1.0 else 'moderate'
    elif ev_call > 0:
        action = 'call'
        conf = 'moderate'
    else:
        action = 'fold'
        conf = 'moderate'

    reasoning = (
        f'{draw_label} ({outs} outs, {hit_eq:.0%} hit_prob). '
        f'Villain: {vtype} (fold_to_raise={fold_pct:.0%}, check_turn={check_turn:.0%}). '
        f'Position: {hero_position}. '
        f'EV: FCP={ev_fcp:+.2f}BB vs call={ev_call:+.2f}BB (adv={ev_adv:+.2f}BB). '
        f'Feasible: {feasible}. Action: {action}.'
    )

    verdict = (
        f'FREE CARD PLAY: {action.upper()} ({conf}). '
        f'{draw_label.capitalize()}: {outs} outs, hit={hit_eq:.0%}/card. '
        f'EV: raise={ev_fcp:+.2f}BB vs call={ev_call:+.2f}BB. '
        f'Villain ({vtype}) folds {fold_pct:.0%}, checks turn {check_turn:.0%}.'
    )

    tips = []

    if action == 'raise_free_card':
        tips.append(
            f'FREE CARD PLAY: Raise to {hero_raise_to_bb:.0f}BB ({hero_raise_to_bb/villain_bet_bb:.1f}x bet). '
            f'Goal: {vtype} checks turn {check_turn:.0%} of the time. '
            f'If villain bets turn anyway: you can still call with {hit_eq:.0%} equity.'
        )
    elif action == 'call':
        tips.append(
            f'JUST CALL: Free card play is {"-" if ev_adv < 0 else "+"}EV ({ev_adv:+.2f}BB) but not optimal. '
            f'Reasons: ' +
            ('OOP reduces free card probability. ' if hero_position == 'OOP' else '') +
            (f'{vtype} rarely folds to raises ({fold_pct:.0%}). ' if fold_pct < 0.20 else '') +
            f'Simply calling with {outs} outs is the better line.'
        )

    if hero_position == 'OOP':
        tips.append(
            f'OOP CAUTION: Free card plays work best IP. '
            f'OOP, villain may bet turn even after calling your raise, denying the free card. '
            f'Check-calling the flop may be better OOP.'
        )

    if vtype == 'calling_station':
        tips.append(
            f'CALLING STATION: Free card plays FAIL vs {vtype}. '
            f'They call raises and then bet turns ({(1-check_turn):.0%}). '
            f'Against stations: pure pot odds is the correct framework.'
        )

    if outs < 6:
        tips.append(
            f'WEAK DRAW ({outs} outs): Free card plays need 8+ outs to be reliably profitable. '
            f'With only {outs} outs, the pot odds of just calling are likely better.'
        )

    if not tips:
        tips.append(f'{verdict}')

    return FreeCardPlayAdvice(
        draw_type=draw_type,
        hero_position=hero_position,
        villain_type=vtype,
        pot_bb=round(pot_bb, 1),
        villain_bet_bb=round(villain_bet_bb, 1),
        hero_raise_to_bb=round(hero_raise_to_bb, 1),
        street=street,
        outs=outs,
        hit_equity_this_street=round(hit_eq, 4),
        draw_label=draw_label,
        fold_to_raise_pct=round(fold_pct, 3),
        check_turn_pct=round(check_turn, 3),
        ev_free_card_play=ev_fcp,
        ev_just_call=ev_call,
        ev_advantage=ev_adv,
        recommended_action=action,
        free_card_play_feasible=feasible,
        confidence=conf,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def fcp_one_liner(r: FreeCardPlayAdvice) -> str:
    return (
        f'[FCP {r.draw_type}|{r.hero_position}|{r.street}] '
        f'{r.recommended_action.upper()} ({r.confidence}) | '
        f'ev_raise={r.ev_free_card_play:+.2f}BB vs call={r.ev_just_call:+.2f}BB | '
        f'fold={r.fold_to_raise_pct:.0%} check_turn={r.check_turn_pct:.0%}'
    )
