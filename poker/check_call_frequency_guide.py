"""
Check-Call Frequency Guide (check_call_frequency_guide.py)

Guides when to use the check-call line vs check-fold or donk-bet.
The check-call line is a PASSIVE defensive line that:
  - Protects hero's checking range (shows check-call isn't always weak)
  - Controls pot size (no check-raise commitment)
  - Keeps villain's bluffs in range
  - Traps aggressive villains

CHECK-CALL THEORY:
  GTO requires hero to check-call at a specific frequency to prevent
  villain from bluffing freely. If hero always check-folds except with
  very strong hands, villain can bet 100% as a bluff.

  CHECK-CALL SITUATIONS:
  1. BLUFF CATCHERS: Hands good enough to call but not raise
     (second pair, weak top pair, middle pair)
  2. TRAPPING: Slow-play strong hands vs aggressive villains
  3. POT CONTROL: Top pair on wet/dangerous boards
  4. RANGE PROTECTION: Keep check range balanced vs check-raise range

  CHECK-CALL vs DONK:
  OOP players shouldn't check-call too much without a reason.
  IP players should check-call more (position advantage + pot control).

  AVOID CHECK-CALL WHEN:
  - Hands have strong SDV and villain is passive (bet for value instead)
  - Turn/river brick arrives (give up marginal hands)
  - SPR < 2 and hand is good enough to check-raise/shove

DISTINCT FROM:
  calldown_advisor.py:          Multi-street calldown strategy
  facing_cbet_advisor.py:       Facing a c-bet (check-raise vs call)
  THIS MODULE:                  When to use check-call LINE specifically;
                                frequency guidance for different hand types;
                                balance between check-call/check-raise/check-fold

Usage:
    from poker.check_call_frequency_guide import guide_check_call, CheckCallGuide, ccg_one_liner

    result = guide_check_call(
        hero_hand_category='middle_pair',
        street='flop',
        hero_position='oop',
        villain_af=2.5,
        villain_cbet_pct=0.65,
        board_texture='semi_wet',
        hero_equity=0.38,
        spr=5.0,
        pot_bb=20.0,
    )
    print(ccg_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Base check-call frequency by hand category (how often to check-call vs check-fold or check-raise)
BASE_CHECK_CALL_FREQ = {
    'set':             0.25,   # mostly check-raise or bet; rarely pure check-call
    'two_pair':        0.30,
    'overpair':        0.35,
    'top_pair':        0.40,
    'top_pair_weak_k': 0.50,
    'middle_pair':     0.55,
    'bottom_pair':     0.45,
    'weak_pair':       0.40,
    'flush_draw':      0.30,   # prefer check-raise or donk
    'straight_draw':   0.30,
    'combo_draw':      0.20,   # mostly check-raise
    'gutshot':         0.45,
    'overcards':       0.35,
    'air':             0.05,   # almost never check-call with air
    'bluff_catcher':   0.70,   # purpose of this hand
}

# When to check-raise vs check-call (higher = prefer check-raise)
CHECK_RAISE_PREFERENCE = {
    'set':         0.70,
    'two_pair':    0.55,
    'combo_draw':  0.60,
    'flush_draw':  0.45,
}


def _adjusted_cc_freq(
    hero_hand_category: str,
    villain_af: float,
    hero_position: str,
    board_texture: str,
    spr: float,
) -> float:
    base = BASE_CHECK_CALL_FREQ.get(hero_hand_category, 0.40)

    # High AF → villain bets a lot → check-call more (let them bluff)
    if villain_af >= 3.0:
        base += 0.10
    elif villain_af <= 1.5:
        base -= 0.10   # passive villain; just bet or fold

    # OOP players need more check-calls than IP
    if hero_position in ('oop', 'bb', 'sb'):
        base += 0.05
    else:
        base -= 0.05   # IP can check-raise more effectively

    # Wet board: draws are live; opponent's range is stronger
    if board_texture in ('wet', 'monotone'):
        if hero_hand_category in ('top_pair', 'overpair'):
            base += 0.08   # protect against going too fast with TP on wet board

    # Low SPR: check-call less (commit or fold)
    if spr < 2.5:
        base -= 0.15

    return round(min(0.90, max(0.0, base)), 3)


def _check_call_line(
    hero_hand_category: str,
    villain_af: float,
    hero_position: str,
    board_texture: str,
    spr: float,
    cc_freq: float,
    villain_cbet_pct: float,
) -> tuple:
    """(recommended_line: str, reason: str)"""
    # Strong hands: check-raise vs aggressive villains
    if hero_hand_category in ('set', 'two_pair') and villain_af >= 2.5:
        return 'check_raise', f'Strong hand vs aggressive villain (AF={villain_af:.1f}): check-raise for value and protection.'

    # Low SDV: check-fold
    if hero_hand_category in ('air', 'overcards') and villain_cbet_pct >= 0.50:
        return 'check_fold', f'Low SDV hand ({hero_hand_category}): check-fold vs regular c-bets.'

    # Mid-strength: check-call
    if hero_hand_category in ('middle_pair', 'bottom_pair', 'top_pair_weak_k', 'bluff_catcher'):
        if villain_af >= 2.0:
            return 'check_call', f'Bluff catcher vs aggressive villain: check-call at {cc_freq:.0%} frequency.'
        else:
            return 'check_call_or_fold', 'Mid-strength hand vs passive villain: check-call or fold depending on specific action.'

    # Draws: check-call or check-raise
    if hero_hand_category in ('flush_draw', 'straight_draw'):
        if hero_position == 'oop' and villain_af >= 2.5:
            return 'check_call', 'OOP draw vs aggressive: check-call to see cheap card.'
        else:
            return 'check_or_semi_bluff', 'Draw: mix check-call and check-raise for balance.'

    # Default
    if cc_freq >= 0.50:
        return 'check_call', f'Solid check-call frequency ({cc_freq:.0%}).'
    elif cc_freq >= 0.25:
        return 'check_call_mix', f'Mix check-call and check-fold ({cc_freq:.0%} CC rate).'
    else:
        return 'check_fold', 'Low check-call frequency; mostly check-fold.'


@dataclass
class CheckCallGuide:
    # Inputs
    hero_hand_category: str
    street: str
    hero_position: str
    villain_af: float
    villain_cbet_pct: float
    board_texture: str
    hero_equity: float
    spr: float
    pot_bb: float

    # Analysis
    check_call_frequency: float   # how often to check-call with this hand type
    recommended_line: str         # 'check_call' / 'check_raise' / 'check_fold' / 'check_call_mix'
    line_reasoning: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def guide_check_call(
    hero_hand_category: str = 'middle_pair',
    street: str = 'flop',
    hero_position: str = 'oop',
    villain_af: float = 2.5,
    villain_cbet_pct: float = 0.65,
    board_texture: str = 'semi_wet',
    hero_equity: float = 0.38,
    spr: float = 5.0,
    pot_bb: float = 20.0,
) -> CheckCallGuide:
    """
    Guide on when to use check-call line vs alternatives.

    Args:
        hero_hand_category:  Current hand category
        street:              'flop' / 'turn' / 'river'
        hero_position:       'ip' / 'oop'
        villain_af:          Villain's AF
        villain_cbet_pct:    Villain's c-bet frequency
        board_texture:       'dry' / 'semi_wet' / 'wet' / 'monotone' / 'paired'
        hero_equity:         Hero's equity
        spr:                 Stack-to-pot ratio
        pot_bb:              Current pot

    Returns:
        CheckCallGuide
    """
    cc_freq = _adjusted_cc_freq(hero_hand_category, villain_af, hero_position,
                                  board_texture, spr)
    line, reason = _check_call_line(hero_hand_category, villain_af, hero_position,
                                     board_texture, spr, cc_freq, villain_cbet_pct)

    verdict = (
        f'[CCG {hero_hand_category}|{street}|{hero_position}] '
        f'{line.upper()} ({cc_freq:.0%} cc_freq) | '
        f'eq={hero_equity:.0%} spr={spr:.1f}'
    )

    reasoning = (
        f'Check-call guide: {hero_hand_category} on {board_texture} {street}. '
        f'Position={hero_position}. AF={villain_af:.1f} cbet={villain_cbet_pct:.0%}. '
        f'CC_freq={cc_freq:.0%}. SPR={spr:.1f}. '
        f'Line={line}.'
    )

    tips = [reason]

    tips.append(
        f'CHECK-CALL FREQUENCY: Use check-call {cc_freq:.0%} of the time with {hero_hand_category} '
        f'on {board_texture} {street} as {hero_position.upper()}. '
        f'Rest of range: check-raise (strong hands/draws) or check-fold (weak hands).'
    )

    if villain_af >= 3.0:
        tips.append(
            f'AGGRESSIVE VILLAIN (AF={villain_af:.1f}): Check-call more to trap. '
            f'Villain will bet frequently with bluffs + value. '
            f'Let them continue betting; raise on later streets or at showdown.'
        )

    if villain_cbet_pct >= 0.70:
        tips.append(
            f'HIGH C-BET VILLAIN ({villain_cbet_pct:.0%}): Many c-bets are bluffs. '
            f'Widen check-call range -- you need to defend against frequent betting. '
            f'MDF requires defending {1 - 0.50 * villain_cbet_pct:.0%}+ of range.'
        )

    if hero_position == 'ip' and board_texture in ('dry', 'semi_wet'):
        tips.append(
            f'IP CHECK-CALL: Checking in position allows you to control pot size. '
            f'If villain checks back turn, you can bet river for value. '
            f'IP check-calls protect your checking range and set up delayed bets.'
        )

    if spr < 2.5:
        tips.append(
            f'LOW SPR ({spr:.1f}): Check-calling becomes less optimal at low SPR. '
            f'Either check-raise (commit) or check-fold. '
            f'Pure check-call with intent to fold turn/river wastes money at low SPR.'
        )

    if street == 'river':
        tips.append(
            f'RIVER CHECK-CALL: Pure bluff-catch situation. '
            f'No more streets -- call only if you beat enough of villain\'s betting range. '
            f'With {hero_hand_category}: check-call if villain bluff frequency > alpha (break-even).'
        )

    return CheckCallGuide(
        hero_hand_category=hero_hand_category,
        street=street,
        hero_position=hero_position,
        villain_af=villain_af,
        villain_cbet_pct=villain_cbet_pct,
        board_texture=board_texture,
        hero_equity=hero_equity,
        spr=spr,
        pot_bb=pot_bb,
        check_call_frequency=cc_freq,
        recommended_line=line,
        line_reasoning=reason,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ccg_one_liner(r: CheckCallGuide) -> str:
    return (
        f'[CCG {r.hero_hand_category}|{r.street}|{r.hero_position}] '
        f'{r.recommended_line.upper()} ({r.check_call_frequency:.0%}) | '
        f'eq={r.hero_equity:.0%} spr={r.spr:.1f}'
    )
