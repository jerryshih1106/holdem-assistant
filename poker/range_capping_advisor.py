"""
Range Capping Advisor (range_capping_advisor.py)

A "capped" range is one that has been STRIPPED of strong hands by prior action.
When villain can DEDUCE that hero cannot have strong hands, they can exploit hero
mercilessly by raising/betting, knowing hero cannot have the nuts.

WHEN RANGES GET CAPPED:
  1. Check back the flop as preflop aggressor: range is capped (AA/KK would bet)
  2. Call a flop raise OOP: capped (raising hands would 3-bet or fold)
  3. Check the turn after betting flop: capped (strong hands would barrel)
  4. Call turn bet OOP: capped (raises would be for value or as draws)

WHY CAPPING IS DANGEROUS:
  - Opponent can over-bet or bluff freely knowing hero cannot have nuts
  - Hero's check-raises are not credible
  - Villain extracts maximum with thin value

HOW TO "UNCAP" (PROTECT) YOUR RANGE:
  - Mix in some slow-plays with strong hands in early streets
  - Occasionally check-raise strong hands on flop
  - Balance your checking range to include some sets/two-pairs
  - Example: check back 20% of AA on the flop IP to keep range uncapped

CAPPING SCORE (0-10):
  0-3: Range appears uncapped (credible strong hands present)
  4-6: Moderately capped (some strength removed)
  7-9: Significantly capped (villain can exploit)
  10:  Completely capped (hero cannot have strong hands)

Usage:
    from poker.range_capping_advisor import analyze_range_capping, RangeCappingAdvice, capping_one_liner

    advice = analyze_range_capping(
        hero_position='IP',
        hero_preflop_role='caller',
        flop_action='check_back',
        turn_action='bet',
        villain_action='raise',
        street='turn',
        board_texture='dry',
    )
    print(capping_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List, Dict


# --------------------------------------------------------------------------
# Capping signals per action sequence
# --------------------------------------------------------------------------

# (preflop_role, position, street_action) -> (capping_contribution, reason)
_CAPPING_SIGNALS: Dict = {
    # Preflop aggressor checking back IP
    ('aggressor', 'IP', 'flop', 'check_back'):    (4, 'Aggressor checks flop IP: nutted hands usually bet for protection/value.'),
    ('aggressor', 'OOP', 'flop', 'check_back'):   (2, 'Aggressor checks flop OOP: less suspicious, some traps check OOP.'),
    # Preflop caller IP checking back
    ('caller', 'IP', 'flop', 'check_back'):       (2, 'Caller checks back IP: less capping effect, sets are in range.'),
    ('caller', 'OOP', 'flop', 'check_back'):      (1, 'Caller checks OOP flop: normal, traps are common here.'),
    # Calling a raise
    ('aggressor', 'IP', 'flop', 'call_raise'):    (5, 'Aggressor calls flop raise IP: re-raising range is gone, capped significantly.'),
    ('aggressor', 'OOP', 'flop', 'call_raise'):   (6, 'Aggressor calls flop raise OOP: very capped -- check-raises typically slow-play strong hands.'),
    ('caller', 'IP', 'flop', 'call_raise'):       (3, 'Caller calls flop raise IP: moderately capped, but some sets/draws call.'),
    # Turn actions
    ('aggressor', 'IP', 'turn', 'check_back'):    (3, 'Aggressor checks turn IP after betting flop: strong hands usually barrel.'),
    ('caller', 'OOP', 'turn', 'check_call'):      (4, 'Caller check-calls turn OOP: very strong hands check-raise.'),
    # River actions
    ('aggressor', 'IP', 'river', 'check_back'):   (2, 'Checking river IP: can include value hands looking for check-raise.'),
    ('caller', 'OOP', 'river', 'check_call'):     (5, 'Calling river OOP: strong hands would typically check-raise.'),
    # Defensive actions
    ('any', 'any', 'any', 'bet'):                 (-1, 'Betting: range appears uncapped (bluffs + value in range).'),
    ('any', 'any', 'any', 'raise'):               (-2, 'Raising: strong hand signal, range is NOT capped.'),
    ('any', 'any', 'any', 'check_raise'):         (-3, 'Check-raising: very credible for strong hands, range uncapped.'),
}

# Board texture affects capping interpretation
_BOARD_CAPPING_MOD = {
    'dry':        -1,   # on dry boards, even checking is less suspicious (more traps)
    'wet':        +1,   # wet boards: not betting with draws/value is more suspicious
    'paired':     -1,   # paired boards: more checking makes sense
    'monotone':   +2,   # monotone: not betting is more suspicious (have flush or nothing)
    'connected':  +1,   # connected: draws should bet, so checking is capping
    'neutral':    0,
}

# Villain can exploit when score >= 5
_EXPLOIT_RISK = {
    (0, 3):   ('low', 'Range appears balanced. Villain cannot exploit freely.'),
    (4, 6):   ('moderate', 'Moderate capping. Villain may probe with over-bets.'),
    (7, 9):   ('high', 'Significant capping. Villain will bluff/overbet aggressively.'),
    (10, 99): ('critical', 'Completely capped. Villain has near-infinite bluffing license.'),
}

def _get_exploit_risk(score: int):
    for (lo, hi), (risk, desc) in _EXPLOIT_RISK.items():
        if lo <= score <= hi:
            return risk, desc
    return 'unknown', 'Unknown risk level.'


def _build_uncapping_tips(
    role: str, position: str, action: str, board: str, capping_score: int
) -> List[str]:
    """Generate specific tips for uncapping the range."""
    tips = []
    if capping_score >= 5:
        tips.append(
            f'UNCAP YOUR RANGE: Mix slow-plays into your checking range. '
            f'On {board} boards, check back {20 if board == "dry" else 30}% of your nut hands '
            f'(e.g., top set, two pair) to maintain range balance.'
        )
    if action == 'check_back' and role == 'aggressor' and position == 'IP':
        tips.append(
            f'PROTECT IP CHECKING RANGE: Always include some strong hands when checking IP as aggressor. '
            f'Rule: check back ~15% of top pair / 30% of sets. This makes villain "pay to probe" your range.'
        )
    if action == 'call_raise' and position == 'OOP':
        tips.append(
            f'OOP RAISE-CALL RANGE: Your range is very capped by calling flop raises OOP. '
            f'Consider check-raising more (not just calling) with strong hands. '
            f'A mixed strategy: check-raise 50%+ of sets/two-pairs, call 50%.'
        )
    return tips


@dataclass
class RangeCappingAdvice:
    # Inputs
    hero_position: str
    hero_preflop_role: str      # 'aggressor', 'caller'
    flop_action: str
    turn_action: str
    villain_action: str
    street: str
    board_texture: str

    # Analysis
    capping_score: int          # 0-10 (0=uncapped, 10=completely capped)
    capping_signals: List[str]  # list of reasons
    exploit_risk_level: str     # 'low', 'moderate', 'high', 'critical'
    exploit_risk_desc: str

    # Specific exploits villain can make
    villain_exploits: List[str]

    # Recommendations
    uncapping_frequency: float  # fraction of strong hands to slow-play for balance
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_range_capping(
    hero_position: str = 'IP',
    hero_preflop_role: str = 'aggressor',
    flop_action: str = 'check_back',
    turn_action: str = 'check',
    villain_action: str = 'bet',
    street: str = 'turn',
    board_texture: str = 'dry',
) -> RangeCappingAdvice:
    """
    Analyze how "capped" hero's range is based on the action sequence.

    Args:
        hero_position:       'IP' or 'OOP'
        hero_preflop_role:   'aggressor' (3-bettor, raiser) or 'caller'
        flop_action:         Hero's flop action: 'bet', 'check_back', 'call_bet', 'call_raise',
                             'raise', 'check_raise', 'check'
        turn_action:         Hero's turn action: 'bet', 'check_back', 'call_bet', 'check', 'check_call'
        villain_action:      What villain is doing: 'bet', 'raise', 'check', 'probe'
        street:              Current street: 'flop', 'turn', 'river'
        board_texture:       'dry', 'wet', 'paired', 'monotone', 'connected', 'neutral'

    Returns:
        RangeCappingAdvice
    """
    score = 0
    signals = []

    # Look up flop action
    key_flop = (hero_preflop_role, hero_position, 'flop', flop_action)
    key_flop_any = ('any', 'any', 'any', flop_action)
    flop_entry = _CAPPING_SIGNALS.get(key_flop, _CAPPING_SIGNALS.get(key_flop_any))
    if flop_entry:
        contrib, reason = flop_entry
        score += contrib
        signals.append(f'Flop ({flop_action}): {reason} [+{contrib}]')

    # Look up turn action
    key_turn = (hero_preflop_role, hero_position, 'turn', turn_action)
    key_turn_any = ('any', 'any', 'any', turn_action)
    turn_entry = _CAPPING_SIGNALS.get(key_turn, _CAPPING_SIGNALS.get(key_turn_any))
    if turn_entry:
        contrib, reason = turn_entry
        score += contrib
        signals.append(f'Turn ({turn_action}): {reason} [+{contrib}]')

    # Board texture modifier
    board_mod = _BOARD_CAPPING_MOD.get(board_texture, 0)
    if board_mod != 0:
        score += board_mod
        signals.append(f'Board ({board_texture}): modifier {board_mod:+d}')

    # Villain action modifier: if villain probes/overbets, they might sense capping
    if villain_action in ('raise', 'bet', 'probe'):
        score = min(10, score)  # villains betting into capped range amplifies danger

    score = max(0, min(10, score))

    exploit_risk, exploit_desc = _get_exploit_risk(score)

    # What villain can do given this capping level
    villain_exploits = []
    if score >= 4:
        villain_exploits.append('Overbet bluff (hero cannot raise with nuts -- too capped)')
    if score >= 5:
        villain_exploits.append('Probe bet with air (hero check-folds medium hands)')
    if score >= 7:
        villain_exploits.append('Jam the river (hero trapped in call/fold, cannot re-raise for value)')
        villain_exploits.append('Barrel every street (hero has no raising equity)')
    if score >= 9:
        villain_exploits.append('Bet any two cards: hero is pot-controlled into passivity')

    uncapping_freq = min(0.40, max(0.0, (score - 3) * 0.05))

    reasoning = (
        f'Range capping analysis: {hero_preflop_role} {hero_position}. '
        f'Flop: {flop_action}. Turn: {turn_action}. Board: {board_texture}. '
        f'Capping score: {score}/10. Risk: {exploit_risk}. '
        f'Signals: {"; ".join(s[:50] for s in signals)}.'
    )

    verdict = (
        f'CAPPING SCORE: {score}/10 ({exploit_risk.upper()} RISK). '
        f'{exploit_desc} '
        f'Uncap by slow-playing {uncapping_freq:.0%} of strong hands.'
    )

    tips = _build_uncapping_tips(
        hero_preflop_role, hero_position, flop_action, board_texture, score
    )

    if score >= 7:
        tips.insert(0,
            f'CRITICAL CAPPING: Score={score}/10. Villain can bluff you off almost any hand. '
            f'Solution: IMMEDIATELY start slow-playing {uncapping_freq:.0%} of your nutted hands '
            f'to rebalance this range in future similar spots.'
        )

    if villain_action in ('raise', 'probe') and score >= 5:
        tips.append(
            f'VILLAIN IS EXPLOITING: They are betting/raising INTO your capped range. '
            f'They sense weakness. Only continue with top of range (sets, two-pair+). '
            f'Folding medium hands here is correct -- they likely have it or have range advantage.'
        )

    if not tips:
        tips.append(
            f'Capping score={score}/10 ({exploit_risk}). Range appears {("balanced" if score < 4 else "moderately capped")}. '
            f'Continue standard strategy.'
        )

    return RangeCappingAdvice(
        hero_position=hero_position,
        hero_preflop_role=hero_preflop_role,
        flop_action=flop_action,
        turn_action=turn_action,
        villain_action=villain_action,
        street=street,
        board_texture=board_texture,
        capping_score=score,
        capping_signals=signals,
        exploit_risk_level=exploit_risk,
        exploit_risk_desc=exploit_desc,
        villain_exploits=villain_exploits,
        uncapping_frequency=round(uncapping_freq, 3),
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def capping_one_liner(r: RangeCappingAdvice) -> str:
    return (
        f'[RANGE_CAP {r.hero_preflop_role.upper()}|{r.hero_position}|{r.street}] '
        f'score={r.capping_score}/10 risk={r.exploit_risk_level.upper()} | '
        f'uncap_freq={r.uncapping_frequency:.0%} | '
        f'{r.exploit_risk_desc[:50]}...' if len(r.exploit_risk_desc) > 50
        else f'[RANGE_CAP {r.hero_preflop_role.upper()}|{r.hero_position}|{r.street}] '
        f'score={r.capping_score}/10 risk={r.exploit_risk_level.upper()} | '
        f'uncap_freq={r.uncapping_frequency:.0%} | '
        f'{r.exploit_risk_desc}'
    )
