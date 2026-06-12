"""
Board Runout Planner (board_runout_planner.py)

Plans strategic action for different board runout scenarios from the
current street forward. Given the flop/turn situation, creates a
concrete plan for each type of turn/river card that might arrive.

WHY RUNOUT PLANNING MATTERS:
  Most players react to each card individually. Strong players have a
  PLAN before cards arrive:
  - Blank: continue cbet plan
  - Flush completes: check back (don't bet into improved range)
  - Hero draw hits: bet strong
  - Board pairs: be cautious (trips enter)
  - Broadway arrives: adjust sizing

  Having a pre-built plan prevents decision mistakes in the moment.

RUNOUT CATEGORIES:
  1. BLANK:           No obvious change to range dynamics
  2. HERO_IMPROVES:   Card completes hero's draw or improves hand
  3. FLUSH_COMPLETES: Third (or fourth) flush card arrives
  4. STRAIGHT_COMPLETES: Board makes obvious straight possible
  5. BOARD_PAIRS:     Board pairs (trips become possible)
  6. OVERCARDS:       High card falls above all board cards
  7. SCARE_CARD:      Card benefits villain's range more than hero's

DISTINCT FROM:
  runout_simulator.py:        Calculates equity delta for each card
  turn_scare_card_advisor.py: Scare card strategy once it arrives
  street_plan_builder.py:     Builds multi-street plan from current position
  THIS MODULE:                Pre-plans response to each runout TYPE;
                              gives decision tree before cards arrive

Usage:
    from poker.board_runout_planner import plan_runout, RunoutPlan, brp_one_liner

    result = plan_runout(
        hero_hand_category='top_pair',
        hero_has_draw=True,
        hero_draw_type='flush_draw',
        board_texture='semi_wet',
        street='flop',
        hero_position='ip',
        hero_role='pfr',
        hero_equity=0.62,
        pot_bb=20.0,
        spr=4.5,
        villain_af=2.2,
    )
    print(brp_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class RunoutScenario:
    """Plan for one runout type."""
    runout_type: str      # 'blank' / 'hero_improves' / 'flush_completes' / etc.
    probability: float    # rough probability this card type arrives (0-1)
    action: str           # recommended action
    bet_size_pct: float   # bet size as fraction of pot (0 = no bet)
    frequency: float      # how often to take this action (0-1; <1.0 = mixing)
    reasoning: str        # why this action


def _runout_probability(runout_type: str, board_texture: str, hero_has_draw: bool,
                        hero_draw_type: str) -> float:
    """Rough probability each runout type arrives."""
    if runout_type == 'blank':
        base = 0.40 if board_texture in ('dry', 'semi_wet') else 0.25
    elif runout_type == 'hero_improves':
        if hero_has_draw:
            return {'flush_draw': 0.19, 'straight_draw': 0.17, 'gutshot': 0.09,
                    'combo_draw': 0.30, 'oesd': 0.17}.get(hero_draw_type, 0.15)
        return 0.06
    elif runout_type == 'flush_completes':
        base = 0.20 if board_texture in ('semi_wet', 'wet', 'monotone') else 0.06
    elif runout_type == 'straight_completes':
        base = 0.15 if board_texture in ('semi_wet', 'wet') else 0.08
    elif runout_type == 'board_pairs':
        base = 0.18
    elif runout_type == 'overcards':
        base = 0.15
    elif runout_type == 'scare_card':
        base = 0.12
    else:
        base = 0.10
    return base


def _plan_blank(hero_hand_category: str, hero_position: str, hero_role: str,
                hero_equity: float, spr: float, villain_af: float) -> RunoutScenario:
    """Plan for blank runout (no significant texture change)."""
    if hero_hand_category in ('set', 'two_pair', 'flush', 'straight', 'full_house'):
        action = 'bet_strong'
        size = 0.65
        freq = 0.90
        reasoning = 'Strong hand + blank: continue building pot.'
    elif hero_hand_category in ('overpair', 'top_pair'):
        if hero_position == 'ip':
            action = 'bet_value'
            size = 0.55
            freq = 0.70
            reasoning = 'Top pair IP on blank: bet for value at medium size.'
        else:
            action = 'bet_or_check_call'
            size = 0.50
            freq = 0.55
            reasoning = 'Top pair OOP on blank: bet or check-call depending on villain tendency.'
    elif hero_hand_category in ('flush_draw', 'straight_draw', 'combo_draw'):
        action = 'continue_semi_bluff'
        size = 0.55
        freq = 0.60
        reasoning = 'Draw on blank: continue with semi-bluff; draw not yet complete.'
    else:
        action = 'check_evaluate'
        size = 0.0
        freq = 0.0
        reasoning = 'Weak hand on blank: check and give up unless pot odds are good.'
    prob = _runout_probability('blank', 'semi_wet', False, '')
    return RunoutScenario('blank', prob, action, size, freq, reasoning)


def _plan_hero_improves(hero_hand_category: str, hero_draw_type: str,
                        spr: float) -> RunoutScenario:
    """Plan for when hero's draw completes."""
    if hero_draw_type in ('flush_draw', 'oesd', 'combo_draw'):
        action = 'bet_strong' if spr >= 3.0 else 'shove'
        size = 0.75 if spr >= 3.0 else 1.0
        freq = 0.95
        reasoning = f'{hero_draw_type} completes: strong hand, bet aggressively. '
    elif hero_draw_type == 'gutshot':
        action = 'bet_value'
        size = 0.60
        freq = 0.85
        reasoning = 'Gutshot completes: semi-concealed straight, bet for value.'
    else:
        action = 'bet_value'
        size = 0.65
        freq = 0.90
        reasoning = 'Draw improved: bet for value.'
    prob = _runout_probability('hero_improves', '', True, hero_draw_type)
    return RunoutScenario('hero_improves', prob, action, size, freq, reasoning)


def _plan_flush_completes(hero_hand_category: str, hero_position: str,
                          hero_role: str, hero_has_draw: bool,
                          hero_draw_type: str) -> RunoutScenario:
    """Plan for flush card arriving."""
    # If hero has the flush:
    if hero_draw_type == 'flush_draw' and hero_has_draw:
        return RunoutScenario('flush_completes', 0.18, 'bet_strong', 0.75, 0.90,
                              'Hero completes flush: bet strong for value. Villain may have second-best flush or 2-pair.')
    # Hero has no flush:
    if hero_role == 'pfr':
        action = 'check_back'
        reasoning = 'Flush completes without hero\'s flush: check back. Villain\'s range improved significantly.'
    else:
        action = 'check_evaluate'
        reasoning = 'Flush completes: villain (PFR) now has many flushes. Check-fold marginal hands.'
    prob = _runout_probability('flush_completes', 'semi_wet', False, '')
    return RunoutScenario('flush_completes', prob, action, 0.0, 0.0, reasoning)


def _plan_straight_completes(hero_hand_category: str, hero_role: str,
                              hero_has_draw: bool, hero_draw_type: str) -> RunoutScenario:
    """Plan for straight card arriving."""
    if hero_draw_type in ('oesd', 'gutshot', 'straight_draw') and hero_has_draw:
        return RunoutScenario('straight_completes', 0.15, 'bet_value', 0.65, 0.90,
                              'Hero completes straight: bet for value (concealed strength).')
    if hero_hand_category in ('set', 'two_pair', 'overpair'):
        return RunoutScenario('straight_completes', 0.15, 'check_or_bet_small', 0.35, 0.50,
                              'Strong made hand but straight completes: be cautious; check or bet small to see where you stand.')
    return RunoutScenario('straight_completes', 0.10, 'check_fold', 0.0, 0.0,
                          'Straight completes without hero\'s hand: check-fold weak hands vs bets.')


def _plan_board_pairs(hero_hand_category: str, villain_af: float) -> RunoutScenario:
    """Plan for board pairing (trips become possible)."""
    if hero_hand_category in ('set', 'full_house', 'quads'):
        return RunoutScenario('board_pairs', 0.18, 'bet_value', 0.65, 0.90,
                              'Hero has boat/quads: bet for value. Villain may have trips thinking they\'re ahead.')
    if hero_hand_category in ('top_pair', 'overpair', 'two_pair'):
        action = 'check_call' if villain_af >= 2.5 else 'bet_small'
        reasoning = (
            'Board pairs with top pair/overpair: be cautious -- villain has trips possible. '
            f'{"Check-call vs aggressive villain." if villain_af >= 2.5 else "Bet small for pot control."}'
        )
        return RunoutScenario('board_pairs', 0.18, action, 0.33, 0.60, reasoning)
    return RunoutScenario('board_pairs', 0.18, 'check_evaluate', 0.0, 0.0,
                          'Board pairs without strong hand: check and evaluate.')


def _plan_overcard(hero_hand_category: str, hero_role: str) -> RunoutScenario:
    """Plan for overcard arriving above all board cards."""
    if hero_hand_category in ('set', 'two_pair', 'flush', 'straight'):
        return RunoutScenario('overcard', 0.15, 'bet_value', 0.60, 0.85,
                              'Strong hand: bet despite overcard; villain\'s range doesn\'t necessarily include it.')
    if hero_role == 'pfr' and hero_hand_category in ('top_pair',):
        return RunoutScenario('overcard', 0.15, 'check_back', 0.0, 0.0,
                              'Top pair + overcard: check back (top pair now second pair; be cautious).')
    return RunoutScenario('overcard', 0.15, 'check_fold', 0.0, 0.0,
                          'Overcard arrives and hero has weak hand: check-fold vs bets.')


@dataclass
class RunoutPlan:
    # Inputs
    hero_hand_category: str
    hero_has_draw: bool
    hero_draw_type: str
    board_texture: str
    street: str
    hero_position: str
    hero_role: str
    hero_equity: float
    pot_bb: float
    spr: float
    villain_af: float

    # Plans for each runout type
    scenarios: Dict[str, RunoutScenario]

    # Summary
    most_likely_runout: str
    most_dangerous_runout: str
    overall_plan_strength: str   # 'strong' / 'medium' / 'weak'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def plan_runout(
    hero_hand_category: str = 'top_pair',
    hero_has_draw: bool = True,
    hero_draw_type: str = 'flush_draw',
    board_texture: str = 'semi_wet',
    street: str = 'flop',
    hero_position: str = 'ip',
    hero_role: str = 'pfr',
    hero_equity: float = 0.62,
    pot_bb: float = 20.0,
    spr: float = 4.5,
    villain_af: float = 2.2,
) -> RunoutPlan:
    """
    Build a strategic plan for all possible board runouts.

    Args:
        hero_hand_category:  Current hand category
        hero_has_draw:       Does hero have a draw?
        hero_draw_type:      Type of draw ('flush_draw'/'oesd'/'gutshot'/etc.)
        board_texture:       'dry' / 'semi_wet' / 'wet' / 'paired' / 'monotone'
        street:              'flop' / 'turn' (planning for next street)
        hero_position:       'ip' / 'oop'
        hero_role:           'pfr' / 'caller'
        hero_equity:         Current equity
        pot_bb:              Current pot
        spr:                 Stack-to-pot ratio
        villain_af:          Villain AF

    Returns:
        RunoutPlan
    """
    scenarios = {
        'blank':             _plan_blank(hero_hand_category, hero_position, hero_role,
                                         hero_equity, spr, villain_af),
        'hero_improves':     _plan_hero_improves(hero_hand_category, hero_draw_type, spr),
        'flush_completes':   _plan_flush_completes(hero_hand_category, hero_position,
                                                    hero_role, hero_has_draw, hero_draw_type),
        'straight_completes': _plan_straight_completes(hero_hand_category, hero_role,
                                                        hero_has_draw, hero_draw_type),
        'board_pairs':       _plan_board_pairs(hero_hand_category, villain_af),
        'overcard':          _plan_overcard(hero_hand_category, hero_role),
    }

    # Most likely runout
    most_likely = max(scenarios.items(), key=lambda x: x[1].probability)[0]

    # Most dangerous runout (lowest freq plan = hardest scenario)
    danger_map = {k: v for k, v in scenarios.items() if v.action in ('check_fold', 'check_evaluate', 'check_back')}
    most_dangerous = max(danger_map.items(), key=lambda x: x[1].probability)[0] if danger_map else 'board_pairs'

    # Overall plan strength
    strong_actions = sum(1 for s in scenarios.values() if s.action in ('bet_strong', 'bet_value', 'shove'))
    if strong_actions >= 4:
        plan_strength = 'strong'
    elif strong_actions >= 2:
        plan_strength = 'medium'
    else:
        plan_strength = 'weak'

    reasoning = (
        f'Runout planning: {hero_hand_category} '
        f'{"+" + hero_draw_type if hero_has_draw else ""} on {board_texture} {street}. '
        f'Hero={hero_role} {hero_position}. SPR={spr:.1f}. '
        f'Most likely={most_likely}. Most dangerous={most_dangerous}. '
        f'Plan strength={plan_strength}.'
    )

    verdict = (
        f'[BRP {hero_hand_category}|{board_texture}|{street}] '
        f'plan={plan_strength.upper()} | '
        f'likely={most_likely} danger={most_dangerous} | '
        f'blank={scenarios["blank"].action}'
    )

    tips = [
        f'BLANK RUNOUT ({scenarios["blank"].probability:.0%} likely): '
        f'{scenarios["blank"].action.upper()} at {scenarios["blank"].bet_size_pct:.0%}pot '
        f'({scenarios["blank"].frequency:.0%} frequency). '
        f'{scenarios["blank"].reasoning}',

        f'HERO IMPROVES ({scenarios["hero_improves"].probability:.0%} likely): '
        f'{scenarios["hero_improves"].action.upper()} at {scenarios["hero_improves"].bet_size_pct:.0%}pot. '
        f'{scenarios["hero_improves"].reasoning}',

        f'DANGER CARD ({most_dangerous.replace("_", " ")}): '
        f'{scenarios[most_dangerous].action.upper()}. '
        f'{scenarios[most_dangerous].reasoning}',
    ]

    tips.append(
        f'FULL RUNOUT TREE: '
        f'flush_completes={scenarios["flush_completes"].action} | '
        f'straight_completes={scenarios["straight_completes"].action} | '
        f'board_pairs={scenarios["board_pairs"].action} | '
        f'overcard={scenarios["overcard"].action}'
    )

    if plan_strength == 'weak':
        tips.append(
            f'WEAK POSITION: Most runouts favor villain. Consider check-calling rather than '
            f'betting aggressively on {board_texture} board with {hero_hand_category}. '
            f'Bet only {hero_draw_type if hero_has_draw else "strong made hands"}.'
        )

    return RunoutPlan(
        hero_hand_category=hero_hand_category,
        hero_has_draw=hero_has_draw,
        hero_draw_type=hero_draw_type,
        board_texture=board_texture,
        street=street,
        hero_position=hero_position,
        hero_role=hero_role,
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        spr=spr,
        villain_af=villain_af,
        scenarios=scenarios,
        most_likely_runout=most_likely,
        most_dangerous_runout=most_dangerous,
        overall_plan_strength=plan_strength,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def brp_one_liner(r: RunoutPlan) -> str:
    blank = r.scenarios.get('blank', None)
    blank_str = f'{blank.action}@{blank.bet_size_pct:.0%}' if blank else 'n/a'
    return (
        f'[BRP {r.hero_hand_category}|{r.board_texture}|{r.street}] '
        f'plan={r.overall_plan_strength.upper()} | '
        f'blank={blank_str} danger={r.most_dangerous_runout}'
    )
