"""
Hand Class Strategy Advisor (hand_class_strategy_advisor.py)

Translates a hand's STRATEGIC CLASS (category of strength) directly into
the optimal betting/checking strategy, without needing to derive it from
scratch each time.

HAND CLASSES:
  nuts             : Nut flush, nut straight, top set (cannot lose)
  strong_value     : Second set, top-two pair, flush, straight
  top_pair         : Top pair with good kicker (TPTK, TPGK)
  medium_pair      : Middle pair or top pair with weak kicker
  weak_pair        : Bottom pair, underpair to board
  bluff_catcher    : Hand that beats bluffs but loses to value (middle pair vs range)
  air              : Total miss -- no pair, no draw
  nut_draw         : Nut flush draw, OESD with good equity (>30% to improve)
  combo_draw       : Flush draw + pair, open-ended + backdoor flush (>50% equity)
  weak_draw        : Gutshot, backdoor draws (<15% equity)
  overpair         : Pocket pair above all board cards
  set              : Three of a kind using pocket pair

STRATEGY MATRIX:
  Street x Position x Hand Class -> (bet_fraction, action, reasoning)

Usage:
    from poker.hand_class_strategy_advisor import advise_hand_class, HandClassAdvice, hca_one_liner

    advice = advise_hand_class(
        hand_class='top_pair',
        hero_position='IP',
        villain_type='fish',
        street='flop',
        pot_bb=6.0,
        spr=8.0,
    )
    print(hca_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# --------------------------------------------------------------------------
# Strategy table: (hand_class, street, hero_position) -> (bet_fraction, primary_action, logic)
# --------------------------------------------------------------------------

_BET_FRACS = {
    # (hand_class, street, position): (fraction_of_pot, action_label, short_logic)
    ('nuts',         'flop',  'IP'):   (0.50, 'VALUE_BET', 'Bet 1/2 pot: build pot, induce raises, protect equity.'),
    ('nuts',         'flop',  'OOP'):  (0.40, 'VALUE_BET_SMALLFREQ', 'Bet small or check-raise: give villain rope to bluff.'),
    ('nuts',         'turn',  'IP'):   (0.70, 'VALUE_BET', 'Bet 2/3 pot: extract value on deeper street.'),
    ('nuts',         'turn',  'OOP'):  (0.60, 'VALUE_BET', 'Bet 2/3 pot: force decisions with nutted hands.'),
    ('nuts',         'river', 'IP'):   (1.00, 'OVERBET', 'Polarize: overbet (0.8-1.5x) for maximum value or check-raise.'),
    ('nuts',         'river', 'OOP'):  (0.80, 'VALUE_BET', 'Large river bet: extract from bluff catchers.'),

    ('strong_value', 'flop',  'IP'):   (0.50, 'VALUE_BET', 'Bet 1/2 pot: straightforward value, protect draws.'),
    ('strong_value', 'flop',  'OOP'):  (0.40, 'BET_OR_CHECK', 'Small bet or check: see turn safely, avoid bloating vs reraises.'),
    ('strong_value', 'turn',  'IP'):   (0.65, 'VALUE_BET', 'Bet 2/3 pot: strong turn value extraction.'),
    ('strong_value', 'turn',  'OOP'):  (0.55, 'VALUE_BET', 'Bet 1/2-2/3: value bet, avoid check-raise bluffs against you.'),
    ('strong_value', 'river', 'IP'):   (0.75, 'VALUE_BET', 'Bet 3/4 pot for value; sizing matters vs bluff catchers.'),
    ('strong_value', 'river', 'OOP'):  (0.65, 'VALUE_BET', 'Bet 2/3 pot: thin value with some bluff blocker combos.'),

    ('overpair',     'flop',  'IP'):   (0.50, 'VALUE_BET', 'Bet 1/2 pot: overpair wants to build pot and protect vs draws.'),
    ('overpair',     'flop',  'OOP'):  (0.40, 'VALUE_BET', 'Small-medium bet OOP: fold equity + value vs draws.'),
    ('overpair',     'turn',  'IP'):   (0.65, 'VALUE_BET', 'Barrel turn: overpair remains ahead of draws/top pair.'),
    ('overpair',     'turn',  'OOP'):  (0.55, 'VALUE_OR_CHECK', 'Bet or check-call OOP: pot control vs draws.'),
    ('overpair',     'river', 'IP'):   (0.70, 'VALUE_BET', 'Value bet 2/3: overpair is value hand, bet for extraction.'),
    ('overpair',     'river', 'OOP'):  (0.55, 'CHECK_CALL', 'Check-call OOP river: induce bluffs, avoid bloat.'),

    ('set',          'flop',  'IP'):   (0.33, 'SLOWPLAY_OR_BET', 'Mix: slowplay ~30% (trap) or small bet 1/3 to build pot.'),
    ('set',          'flop',  'OOP'):  (0.40, 'VALUE_BET', 'Bet: protect vs draws and start building pot OOP.'),
    ('set',          'turn',  'IP'):   (0.80, 'VALUE_BET', 'Bet large: set on turn should build pot aggressively.'),
    ('set',          'turn',  'OOP'):  (0.70, 'VALUE_BET', 'Bet 2/3+ OOP: do not allow free cards with set.'),
    ('set',          'river', 'IP'):   (1.10, 'OVERBET', 'Overbet or check-raise: extract max from straights/flushes.'),
    ('set',          'river', 'OOP'):  (0.85, 'VALUE_BET', 'Large river value: jam or bet big with set.'),

    ('top_pair',     'flop',  'IP'):   (0.45, 'VALUE_BET', 'Bet 40-50%: standard TPTK/TPGK flop strategy.'),
    ('top_pair',     'flop',  'OOP'):  (0.35, 'BET_OR_CHECK', 'Bet small or check: pot control OOP with top pair.'),
    ('top_pair',     'turn',  'IP'):   (0.55, 'VALUE_BET', 'Barrel turn: top pair is value hand, extract vs weaker pairs.'),
    ('top_pair',     'turn',  'OOP'):  (0.45, 'BET_OR_CHECK_CALL', 'Bet or check-call OOP: caution vs raises.'),
    ('top_pair',     'river', 'IP'):   (0.55, 'VALUE_BET', 'Value bet 1/2-2/3: TPTK gets value from second pairs.'),
    ('top_pair',     'river', 'OOP'):  (0.45, 'CHECK_CALL', 'Check-call: induce bluffs vs wide villain, bluffcatch.'),

    ('medium_pair',  'flop',  'IP'):   (0.30, 'SMALL_BET_OR_CHECK', 'Small bet or check: pot control, board dependent.'),
    ('medium_pair',  'flop',  'OOP'):  (0.00, 'CHECK',  'Check OOP: medium pair OOP is not strong enough to bet-fold.'),
    ('medium_pair',  'turn',  'IP'):   (0.00, 'CHECK_BACK', 'Check back: take pot control on the turn with medium pair.'),
    ('medium_pair',  'turn',  'OOP'):  (0.00, 'CHECK_CALL', 'Check-call or fold turn depending on villain bet size.'),
    ('medium_pair',  'river', 'IP'):   (0.00, 'CHECK_BACK', 'Check back river: medium pair is a bluff catcher, not value.'),
    ('medium_pair',  'river', 'OOP'):  (0.00, 'CHECK_CALL', 'Check-call vs small/medium bets; fold to large overbets.'),

    ('weak_pair',    'flop',  'IP'):   (0.00, 'CHECK_BACK', 'Check back: weak pair is not a value hand, take free card.'),
    ('weak_pair',    'flop',  'OOP'):  (0.00, 'CHECK_FOLD', 'Check and fold vs bet: weak pair vs range is losing.'),
    ('weak_pair',    'turn',  'IP'):   (0.00, 'CHECK_BACK', 'Check back turn: weak pair cannot call vs large bets.'),
    ('weak_pair',    'turn',  'OOP'):  (0.00, 'CHECK_FOLD', 'Fold to aggression: weak pair cannot continue vs range.'),
    ('weak_pair',    'river', 'IP'):   (0.00, 'CHECK_BACK', 'Check back river: bluff catcher vs only bluffs; thin.'),
    ('weak_pair',    'river', 'OOP'):  (0.00, 'CHECK_FOLD', 'Fold: weak pair vs river bet loses to all value, beats few bluffs.'),

    ('bluff_catcher','flop',  'IP'):   (0.00, 'CHECK_BACK', 'Check back: let villain bluff into you. Do not build pot.'),
    ('bluff_catcher','flop',  'OOP'):  (0.00, 'CHECK_CALL', 'Check-call: bluff catchers call vs range, do not bet.'),
    ('bluff_catcher','turn',  'IP'):   (0.00, 'CHECK_BACK', 'Check back turn: continue to let villain bluff.'),
    ('bluff_catcher','turn',  'OOP'):  (0.00, 'CHECK_CALL', 'Check-call turn: bluff catcher vs range with equity.'),
    ('bluff_catcher','river', 'IP'):   (0.00, 'CHECK_CALL', 'Check-call river: call villain''s bluffs. Don''t bet (villain folds worse).'),
    ('bluff_catcher','river', 'OOP'):  (0.00, 'CHECK_CALL', 'Check-call vs bet. Never raise: villain calls worse only with value.'),

    ('air',          'flop',  'IP'):   (0.35, 'BLUFF_CBET', 'Can c-bet 1/3 as bluff: fold equity on flop. Use board advantage.'),
    ('air',          'flop',  'OOP'):  (0.00, 'CHECK', 'Check: difficult to bluff profitably OOP. Check and reevaluate.'),
    ('air',          'turn',  'IP'):   (0.55, 'DOUBLE_BARREL', 'Barrel turn as bluff: only with draws/equity or board changes.'),
    ('air',          'turn',  'OOP'):  (0.00, 'CHECK_FOLD', 'Check-fold OOP with air: cannot profitably bluff without equity.'),
    ('air',          'river', 'IP'):   (0.80, 'BLUFF_RIVER', 'River bluff: only if fold equity is high (villain''s range is bluff catchers).'),
    ('air',          'river', 'OOP'):  (0.00, 'CHECK_FOLD', 'Check-fold air on river OOP: very difficult to bluff OOP.'),

    ('nut_draw',     'flop',  'IP'):   (0.45, 'BET_OR_CALL', 'Semi-bluff or call: nut draw IP has strong equity and fold equity.'),
    ('nut_draw',     'flop',  'OOP'):  (0.40, 'BET_OR_CHECK_CALL', 'Check-raise or call: protect nut draw equity OOP.'),
    ('nut_draw',     'turn',  'IP'):   (0.65, 'SEMI_BLUFF', 'Semi-bluff turn: increase fold equity before missing river.'),
    ('nut_draw',     'turn',  'OOP'):  (0.55, 'SEMI_BLUFF_OR_CALL', 'Bet as semi-bluff or call: balance vs villain range.'),
    ('nut_draw',     'river', 'IP'):   (0.75, 'BET_IF_HIT_ELSE_FOLD', 'Value bet if hit, fold if miss (usually): draws missed is air.'),
    ('nut_draw',     'river', 'OOP'):  (0.60, 'BET_IF_HIT_ELSE_FOLD', 'Bet value if hit; check-fold if missed.'),

    ('combo_draw',   'flop',  'IP'):   (0.55, 'SEMI_BLUFF', 'Semi-bluff 1/2 pot+: combo draw is equity-positive with large fold eq.'),
    ('combo_draw',   'flop',  'OOP'):  (0.50, 'SEMI_BLUFF_OR_CHECK_RAISE', 'Check-raise or bet: combo draw OOP should be aggressive.'),
    ('combo_draw',   'turn',  'IP'):   (0.75, 'SEMI_BLUFF_JAM', 'Bet/jam turn: combo draws IP on turn have pot equity to shove.'),
    ('combo_draw',   'turn',  'OOP'):  (0.65, 'SEMI_BLUFF', 'Bet aggressively OOP with combo draw: fold equity + equity combine.'),
    ('combo_draw',   'river', 'IP'):   (0.90, 'BET_IF_HIT_ELSE_BLUFF', 'Hit=value bet large; miss=consider bluff (blockers help).'),
    ('combo_draw',   'river', 'OOP'):  (0.70, 'BET_IF_HIT', 'Value bet large if hit; check-fold if missed (hard to bluff OOP).'),

    ('weak_draw',    'flop',  'IP'):   (0.00, 'CHECK_OR_SMALL_CALL', 'Check back or call small: weak draw has insufficient equity to bluff.'),
    ('weak_draw',    'flop',  'OOP'):  (0.00, 'CHECK_CALL', 'Check-call: take cheap card with gutshot/backdoor.'),
    ('weak_draw',    'turn',  'IP'):   (0.00, 'CHECK_FOLD', 'Check-fold turn if missed: weak draw is too thin to continue.'),
    ('weak_draw',    'turn',  'OOP'):  (0.00, 'CHECK_FOLD', 'Check-fold OOP with weak draw: pot odds rarely justify.'),
    ('weak_draw',    'river', 'IP'):   (0.65, 'BLUFF_IF_BLOCKERS', 'Bluff if you have blockers + opponent is capped; else check-fold.'),
    ('weak_draw',    'river', 'OOP'):  (0.00, 'CHECK_FOLD', 'Check-fold missed weak draw on river OOP.'),
}

_VILLAIN_ADJUST = {
    'fish':            {'bet_frac_mult': 1.15, 'note': 'vs Fish: value bet thicker, less semi-bluffing, more value extraction.'},
    'calling_station': {'bet_frac_mult': 1.20, 'note': 'vs Calling Station: only value bet, NO bluffs -- they never fold.'},
    'nit':             {'bet_frac_mult': 0.85, 'note': 'vs Nit: size down, fold equity is low for bluffs; thin value is safer.'},
    'tag':             {'bet_frac_mult': 1.00, 'note': 'vs TAG: standard GTO-adjacent sizing works.'},
    'lag':             {'bet_frac_mult': 0.90, 'note': 'vs LAG: tighten up, check more (they bluff freely), trap with strong hands.'},
    'unknown':         {'bet_frac_mult': 1.00, 'note': 'vs Unknown: use standard sizing until reads develop.'},
}

_SPR_ADJUST = {
    # Low SPR: simpler decisions, more commitment
    'low':    'Low SPR (<4): hands like top pair+ commit full stack; sets/strong hands go broke.',
    'medium': 'Medium SPR (4-13): optimal for two-pairs and sets; avoid bluffing too big.',
    'high':   'High SPR (>13): overpairs lose value; draws gain value; pot-control is critical.',
}

_VALID_CLASSES = {
    'nuts', 'strong_value', 'top_pair', 'medium_pair', 'weak_pair',
    'bluff_catcher', 'air', 'nut_draw', 'combo_draw', 'weak_draw',
    'overpair', 'set',
}


def _spr_label(spr: float) -> str:
    if spr < 4:
        return 'low'
    if spr < 13:
        return 'medium'
    return 'high'


def _lookup_strategy(hand_class: str, street: str, position: str) -> Tuple[float, str, str]:
    key = (hand_class, street, position)
    if key in _BET_FRACS:
        return _BET_FRACS[key]
    # fallback: same class + river + IP
    fallback = (0.0, 'CHECK', 'No specific strategy found; default to pot control.')
    return fallback


def _generate_tips(
    hand_class: str, hero_position: str, villain_type: str,
    street: str, spr: float, bet_fraction: float, action: str,
) -> List[str]:
    tips = []
    spr_label = _spr_label(spr)
    v_adj = _VILLAIN_ADJUST.get(villain_type, _VILLAIN_ADJUST['unknown'])

    # Hand class specific tips
    if hand_class == 'nuts':
        if villain_type in ('fish', 'calling_station'):
            tips.append(
                f'NUT HAND vs {villain_type.upper()}: Bet for VALUE every street. '
                f'They will call down with worse. Do NOT slowplay -- extract maximum.'
            )
        else:
            tips.append(
                f'NUT HAND: Mix slowplays ({("30% on flop IP" if hero_position=="IP" else "20% OOP")})'
                f' to keep range uncapped. On {street}, lean toward betting {bet_fraction:.0%} pot.'
            )

    elif hand_class in ('set', 'strong_value'):
        tips.append(
            f'{hand_class.upper()} on {street}: Build the pot. '
            f'Target is ~70-80% of stack in pot by river. '
            f'Geometric sizing: flop=1/3, turn=2/3, river=1.0x pot.'
        )

    elif hand_class == 'top_pair':
        if street == 'river':
            tips.append(
                f'TPTK River: Value bet vs calling stations. Check-call vs unknowns (induce bluffs). '
                f'Fold vs large overbets (1.5x+) from nits.'
            )
        else:
            tips.append(
                f'TOP PAIR {hero_position}: Bet for value vs draws and weaker pairs. '
                f'Size up on wet/connected boards to protect equity.'
            )

    elif hand_class in ('medium_pair', 'weak_pair', 'bluff_catcher'):
        tips.append(
            f'{hand_class.upper()}: THIS IS A BLUFF CATCHER, NOT A VALUE HAND. '
            f'Do NOT bet for value -- villain only calls with better. '
            f'Check and call vs reasonable-sized bets to catch bluffs.'
        )

    elif hand_class == 'air':
        if villain_type in ('fish', 'calling_station'):
            tips.append(
                f'AIR vs {villain_type.upper()}: DO NOT BLUFF. They will call down. '
                f'Check-fold and wait for a real hand.'
            )
        else:
            tips.append(
                f'AIR BLUFF: Only continue if fold equity is sufficient. '
                f'Board advantage + blockers to villain value range are required. '
                f'Sizing: 1/3 pot on flop, 2/3 on turn, 3/4 on river.'
            )

    elif hand_class in ('nut_draw', 'combo_draw'):
        tips.append(
            f'{hand_class.upper()}: Semi-bluff with strong equity hands. '
            f'Outs to nuts = fold equity on top of draw equity. '
            f'On {street}: {action}. '
            f'If called, reassess on next street with updated equity.'
        )

    elif hand_class == 'weak_draw':
        tips.append(
            f'WEAK DRAW ({street}): Insufficient equity to semi-bluff profitably. '
            f'Only continue if getting pot odds (implied odds on wet boards). '
            f'Fold to large bets; call only vs small/medium bets.'
        )

    # SPR tip
    tips.append(f'SPR={spr:.1f} ({spr_label}): {_SPR_ADJUST[spr_label]}')

    # Villain-specific tip
    tips.append(v_adj['note'])

    return tips


@dataclass
class HandClassAdvice:
    # Inputs
    hand_class: str
    hero_position: str         # 'IP', 'OOP'
    villain_type: str
    street: str                # 'flop', 'turn', 'river'
    pot_bb: float
    spr: float                 # effective stack-to-pot ratio

    # Strategy output
    primary_action: str        # e.g., 'VALUE_BET', 'CHECK_CALL', 'SEMI_BLUFF'
    bet_fraction: float        # fraction of pot to bet (0 = check)
    bet_size_bb: float         # concrete bet size in BB
    action_logic: str          # brief reasoning

    # Adjustments
    villain_adj_note: str      # villain-specific sizing note
    spr_note: str              # SPR context

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_hand_class(
    hand_class: str = 'top_pair',
    hero_position: str = 'IP',
    villain_type: str = 'unknown',
    street: str = 'flop',
    pot_bb: float = 6.0,
    spr: float = 8.0,
) -> HandClassAdvice:
    """
    Advise on how to play a hand based on its strategic class.

    Args:
        hand_class:      Strategic class of the hand. One of:
                         nuts, strong_value, overpair, set, top_pair, medium_pair,
                         weak_pair, bluff_catcher, air, nut_draw, combo_draw, weak_draw
        hero_position:   'IP' (in position) or 'OOP' (out of position)
        villain_type:    'fish', 'calling_station', 'nit', 'tag', 'lag', 'unknown'
        street:          'flop', 'turn', or 'river'
        pot_bb:          Current pot size in BB
        spr:             Effective stack-to-pot ratio (stack / pot)

    Returns:
        HandClassAdvice
    """
    if hand_class not in _VALID_CLASSES:
        hand_class = 'top_pair'    # safe default

    bet_frac, action, logic = _lookup_strategy(hand_class, street, hero_position)

    v_adj = _VILLAIN_ADJUST.get(villain_type, _VILLAIN_ADJUST['unknown'])

    # Adjust bet fraction for villain type (but not for non-bet actions)
    if bet_frac > 0:
        bet_frac_adj = round(bet_frac * v_adj['bet_frac_mult'], 2)
        # Cap at 1.5x pot
        bet_frac_adj = min(1.5, bet_frac_adj)
    else:
        bet_frac_adj = 0.0

    bet_size_bb = round(pot_bb * bet_frac_adj, 1)

    spr_label = _spr_label(spr)
    spr_note = _SPR_ADJUST[spr_label]

    # Low SPR overrides: commit strong hands
    if spr < 3 and hand_class in ('nuts', 'set', 'strong_value', 'overpair', 'combo_draw'):
        action = 'JAM_COMMIT'
        bet_size_bb = pot_bb    # pot-sized bet -> likely all-in at low SPR
        logic = f'Low SPR ({spr:.1f}): commit with {hand_class}. Get all the chips in.'

    # High SPR overrides: don't stack off with thin hands
    if spr > 15 and hand_class in ('top_pair', 'overpair') and street == 'flop':
        action = 'POT_CONTROL'
        bet_frac_adj = min(bet_frac_adj, 0.33)
        bet_size_bb = round(pot_bb * bet_frac_adj, 1)
        logic = f'High SPR ({spr:.1f}): pot control with {hand_class} -- avoid stacking off vs 2pair+/sets.'

    reasoning = (
        f'{hand_class.upper()} {hero_position} on {street}: '
        f'pot={pot_bb:.1f}BB SPR={spr:.1f}. '
        f'Strategy: {action} at {bet_frac_adj:.0%} pot = {bet_size_bb:.1f}BB. '
        f'Villain type: {villain_type}.'
    )

    verdict = (
        f'[{hand_class.upper()}|{hero_position}|{street}] '
        f'{action} | '
        f'bet={bet_size_bb:.1f}BB ({bet_frac_adj:.0%} pot) | '
        f'{logic[:60]}'
    )

    tips = _generate_tips(
        hand_class, hero_position, villain_type, street, spr, bet_frac_adj, action
    )

    return HandClassAdvice(
        hand_class=hand_class,
        hero_position=hero_position,
        villain_type=villain_type,
        street=street,
        pot_bb=round(pot_bb, 1),
        spr=round(spr, 1),
        primary_action=action,
        bet_fraction=bet_frac_adj,
        bet_size_bb=bet_size_bb,
        action_logic=logic,
        villain_adj_note=v_adj['note'],
        spr_note=spr_note,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hca_one_liner(r: HandClassAdvice) -> str:
    return (
        f'[HCA {r.hand_class.upper()}|{r.hero_position}|{r.street}] '
        f'{r.primary_action} | '
        f'bet={r.bet_size_bb:.1f}BB ({r.bet_fraction:.0%}pot) spr={r.spr:.1f} | '
        f'vs_{r.villain_type}'
    )
