"""
Postflop Line Credibility Advisor (postflop_line_credibility.py)

In poker, a "line" is the sequence of actions taken throughout a hand
(preflop + each postflop street). The line tells a story about what range
hero is representing. A credible line is one that a thinking villain
believes is consistent with the hands hero claims to have.

KEY CONCEPT: Range Consistency
  When hero bets, villain asks: "Which hands in hero's range bet here?"
  If hero's line is inconsistent with their represented range, a
  thinking villain will:
    - Call more with marginal hands (if hero's line looks bluffy)
    - Fold more (if hero's line looks very strong)
    - Bluff raise (if hero seems to be making a suspicious bluff)

Examples of CREDIBLE lines:
  PFR bets flop, bets turn, bets river = "Triple barrel with strong hand or bluff"
    → Credible because PFR has many nutted hands on all textures

  Caller checks flop, probe-bets turn = "Missed the flop, connected on turn"
    → Credible because callers' ranges connect differently on turn cards

  PFR bets flop, checks turn, bets river = "pot control with medium hand"
    → Credible: checking turn = medium-strength; river bet = value or bluff

Examples of SUSPICIOUS lines:
  Check flop → Large bet river (with no turn action) = "Backdoor connect"
    → Suspicious: why didn't hero value-bet flop if strong?

  Call 3-bet → Bet huge flop OOP = "Donk representing nutted hand"
    → Suspicious: GTO callers rarely donk. Villain suspects a draw or oddly weak hand.

  C-bet flop → Check turn → Overbet river = "Delayed aggression spike"
    → Suspicious: the pattern suggests hero missed the turn (air) then felt desperate on river

Credibility Score (0-1):
  0.0-0.3: Very suspicious — villain should call wide / raise more
  0.3-0.5: Somewhat suspicious — villain adjusts toward more calls
  0.5-0.7: Credible — villain has to respect the range
  0.7-0.9: Very credible — villain tends to fold at high rates
  0.9-1.0: Almost perfectly consistent — extremely hard to play against

Usage:
    from poker.postflop_line_credibility import analyze_line_credibility
    from poker.postflop_line_credibility import LineCredibilityResult, line_credibility_one_liner

    result = analyze_line_credibility(
        preflop_role='pfr',
        flop_action='cbet',
        turn_action='check',
        river_action='bet_large',
        hero_hand_class='top_pair',
        board_type='medium',
        hero_pos='IP',
        villain_response='called_flop',
        villain_af=2.0,
        villain_vpip=0.30,
    )
    print(result.credibility_score, result.perceived_range)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Action codes:
_VALID_PREFLOP = {'pfr', 'caller_open', 'caller_3bet', '3bettor', 'coldcall'}
_VALID_FLOP    = {'cbet', 'check', 'check_call', 'check_raise', 'donk', 'bet_large', 'bet_small', 'fold'}
_VALID_TURN    = {'bet', 'check', 'check_call', 'check_raise', 'probe', 'barrel', 'bet_large', 'bet_small', 'fold', 'none'}
_VALID_RIVER   = {'bet', 'check', 'check_call', 'check_raise', 'bet_large', 'bet_small', 'overbet', 'fold', 'none'}


def _canonicalize(action: str) -> str:
    """Normalize action strings."""
    a = action.lower().strip()
    if a in ('bet', 'barrel', 'probe'):
        return 'bet'
    if a in ('bet_large',):
        return 'bet_large'
    if a in ('bet_small',):
        return 'bet_small'
    if a in ('overbet',):
        return 'overbet'
    if a in ('check',):
        return 'check'
    if a in ('check_call',):
        return 'check_call'
    if a in ('check_raise',):
        return 'check_raise'
    if a in ('cbet',):
        return 'cbet'
    if a in ('donk',):
        return 'donk'
    return a


def _base_credibility(
    preflop_role: str,
    flop_action: str,
    turn_action: str,
    river_action: str,
) -> tuple:
    """
    Base credibility score from action sequence.
    Returns (score, perceived_range, pattern_name).
    """
    f = _canonicalize(flop_action)
    t = _canonicalize(turn_action)
    r = _canonicalize(river_action)

    # PFR patterns
    if preflop_role == 'pfr':
        # Triple barrel: classic value or polarized bluff
        if f in ('cbet', 'bet') and t in ('bet', 'barrel', 'bet_large') and r in ('bet', 'bet_large', 'overbet'):
            return (0.75, 'strong_value or polarized_bluff', 'triple_barrel')
        # C-bet, check, give-up
        if f in ('cbet', 'bet') and t == 'check' and r == 'check':
            return (0.70, 'medium_strength or missed_draw', 'cbet_check_check')
        # C-bet, check, bet river = suspicious delay
        if f in ('cbet', 'bet') and t == 'check' and r in ('bet', 'bet_large'):
            return (0.52, 'medium_value or slow_play or delayed_bluff', 'cbet_check_bet')
        # Check, bet turn (delayed cbet)
        if f == 'check' and t in ('bet',) and r in ('bet', 'check'):
            return (0.65, 'medium_value or turned_strong', 'check_bet')
        # Check, check: classic weak/medium hand
        if f == 'check' and t == 'check':
            return (0.55, 'weak_to_medium (checked twice)', 'double_check')
        # C-bet, call, overbet river
        if f in ('cbet', 'bet') and t in ('check_call', 'check') and r == 'overbet':
            return (0.35, 'suspicious bluff (size jump)', 'cbet_check_overbet')
        # Check-raise on flop
        if f == 'check_raise':
            return (0.78, 'strong_hand or draw (cr implies strength)', 'check_raise_flop')
        # Donk bet
        if f == 'donk':
            return (0.40, 'polarized but unusual (donk = rare)', 'donk_pfr')

    # Caller patterns
    if preflop_role in ('caller_open', 'coldcall'):
        # Check, check turn probe bet
        if f in ('check', 'check_call') and t in ('bet', 'probe'):
            return (0.68, 'turned_value or float_stab', 'check_probe')
        # Check, check, bet river
        if f == 'check' and t == 'check' and r in ('bet', 'bet_large'):
            return (0.48, 'backdoor_connect or missed_draw_bluff', 'check_check_bet')
        # Check-raise flop as caller
        if f == 'check_raise':
            return (0.72, 'strong_value or semi_bluff (unexpected aggression)', 'caller_cr')
        # Call flop, call turn, call river
        if f == 'check_call' and t == 'check_call' and r == 'check_call':
            return (0.65, 'bluff_catcher or made_hand', 'triple_call')
        # Check, check, check: passive line
        if f == 'check' and t == 'check' and r == 'check':
            return (0.60, 'weak_showdown_value', 'triple_check')

    # 3-bettor patterns
    if preflop_role == '3bettor':
        # C-bet, double barrel, triple barrel
        if f in ('cbet', 'bet') and t in ('bet', 'barrel') and r in ('bet', 'bet_large'):
            return (0.80, 'very_strong or committed_bluff', 'triple_barrel_3b')
        # C-bet, check, overbet
        if f in ('cbet', 'bet') and t == 'check' and r == 'overbet':
            return (0.38, 'suspicious_delayed_bluff', '3b_cbet_check_overbet')
        # Donk out of position
        if f == 'donk':
            return (0.35, 'unusual donk from 3bettor (suspicious)', 'donk_3bettor')

    # Default: moderate credibility for any line
    return (0.55, 'unclear range', 'generic')


def _hand_consistency_adjustment(
    base_score: float,
    hero_hand_class: str,
    pattern_name: str,
    perceived_range: str,
) -> float:
    """
    Adjust credibility based on how well hero's actual hand fits the pattern.
    Higher score = line is more consistent with hero's actual hand.
    """
    hand_rank = {
        'air': 0, 'trash': 0, 'marginal': 1, 'bottom_pair': 1,
        'middle_pair': 2, 'draw': 2, 'speculative': 2,
        'top_pair': 4, 'medium': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'strong': 7,
        'set': 8, 'straight': 8, 'flush': 8, 'premium': 9, 'nuts': 9,
    }.get(hero_hand_class.lower(), 4)

    # Strong hands on aggressive lines = very credible
    if 'triple_barrel' in pattern_name and hand_rank >= 8:
        return min(0.98, base_score + 0.20)
    if 'triple_barrel' in pattern_name and hand_rank <= 1:
        return base_score + 0.05  # bluff triple barrel also credible if deliberate
    if 'triple_barrel' in pattern_name and 2 <= hand_rank <= 5:
        return max(0.30, base_score - 0.15)  # medium hand triple barreling = suspicious

    # Delayed aggression on weak hand = suspicious
    if pattern_name in ('cbet_check_bet', '3b_cbet_check_overbet') and hand_rank <= 2:
        return max(0.25, base_score - 0.15)  # weak hand doing delayed bluff = suspicious

    # Check-raise with strong hand = highly credible
    if 'check_raise' in pattern_name and hand_rank >= 6:
        return min(0.95, base_score + 0.15)

    # Donk bet with weak hand = very suspicious
    if 'donk' in pattern_name and hand_rank <= 3:
        return max(0.20, base_score - 0.20)

    # Passive line (triple check) with strong hand = very suspicious (slow-played)
    if 'triple_check' in pattern_name and hand_rank >= 7:
        return max(0.30, base_score - 0.20)  # why didn't you bet your set?

    return base_score


def _villain_perception(credibility_score: float) -> str:
    """What does a thinking villain think of this line?"""
    if credibility_score >= 0.85:
        return 'Villain gives full credit — likely to fold most hands except strong holdings.'
    if credibility_score >= 0.70:
        return 'Villain respects your range — will call with medium+ hands, fold to big sizes.'
    if credibility_score >= 0.55:
        return 'Villain is uncertain — will call at pot odds, may look for an excuse to fold.'
    if credibility_score >= 0.40:
        return 'Villain is suspicious — likely to call wider, possibly raise as bluff-catch.'
    return 'Villain is very suspicious — likely to call down wide or raise you off your hand.'


def _action_advice(
    credibility_score: float,
    hero_hand_class: str,
    river_action: str,
) -> str:
    """Strategic advice based on line credibility."""
    rank = {
        'air': 0, 'trash': 0, 'bottom_pair': 1, 'marginal': 1,
        'middle_pair': 2, 'draw': 2, 'top_pair': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'set': 8, 'nuts': 9, 'premium': 9,
    }.get(hero_hand_class.lower(), 4)
    r = _canonicalize(river_action)

    if credibility_score >= 0.70 and rank >= 6:
        return 'Continue as planned: your line is highly credible. Villain will pay off or fold correctly.'
    if credibility_score >= 0.70 and rank <= 2:
        return 'Good bluff line! Your line looks strong. Fire a credible bet size and villain should fold.'
    if credibility_score < 0.45 and rank <= 2:
        return 'WARNING: Suspicious bluff line. Villain will likely call. Consider checking instead.'
    if credibility_score < 0.45 and rank >= 5:
        return 'Your strong hand looks bluffy. Villain may call down thin — this is a silver lining but exploit by betting larger.'
    if 0.45 <= credibility_score < 0.65 and r not in ('none', 'check', 'fold'):
        return 'Moderate credibility. Use a medium size to maintain balance. Avoid extremes (overbet or block bet).'
    return 'Credible line. Play your hand according to its strength.'


@dataclass
class LineCredibilityResult:
    """Assessment of hero's betting line credibility."""
    preflop_role: str
    flop_action: str
    turn_action: str
    river_action: str
    hero_hand_class: str
    board_type: str
    hero_pos: str
    villain_response: str
    villain_af: float
    villain_vpip: float

    # Analysis
    pattern_name: str            # 'triple_barrel', 'cbet_check_bet', etc.
    perceived_range: str         # what villain thinks hero has
    credibility_score: float     # 0-1: how credible this line is
    villain_perception: str      # natural language description
    hand_consistency: float      # how well hero's hand fits the line

    # Advice
    action_advice: str
    should_adjust_line: bool     # if True, hero should consider a different line
    bluff_success_estimate: float  # P(villain folds) if hero bluffs

    tips: List[str] = field(default_factory=list)


def analyze_line_credibility(
    preflop_role: str = 'pfr',
    flop_action: str = 'cbet',
    turn_action: str = 'check',
    river_action: str = 'bet_large',
    hero_hand_class: str = 'top_pair',
    board_type: str = 'medium',
    hero_pos: str = 'IP',
    villain_response: str = 'called_flop',
    villain_af: float = 2.0,
    villain_vpip: float = 0.30,
) -> LineCredibilityResult:
    """
    Analyze how credible hero's postflop betting line is.

    Args:
        preflop_role:     Hero's preflop role: 'pfr' / 'caller_open' / '3bettor' / 'coldcall'
        flop_action:      Hero's flop action: 'cbet'/'check'/'check_call'/'check_raise'/'donk'
        turn_action:      Hero's turn action: 'bet'/'check'/'barrel'/'probe'/'check_call'/'none'
        river_action:     Hero's river action: 'bet'/'check'/'bet_large'/'overbet'/'none'
        hero_hand_class:  Hero's actual hand strength
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        villain_response: Villain's response to hero's actions (for context)
        villain_af:       Villain's aggression factor
        villain_vpip:     Villain's VPIP

    Returns:
        LineCredibilityResult
    """
    # Base credibility from action pattern
    base_score, perceived, pattern = _base_credibility(
        preflop_role, flop_action, turn_action, river_action
    )

    # Adjust for actual hand vs pattern fit
    adj_score = _hand_consistency_adjustment(base_score, hero_hand_class, pattern, perceived)

    # Board type adjustment
    if board_type == 'wet' and pattern not in ('triple_check', 'double_check'):
        adj_score = min(0.98, adj_score + 0.05)  # wet boards = more range combos = more credible
    if board_type == 'dry' and 'bluff' in perceived.lower():
        adj_score = max(0.10, adj_score - 0.08)  # dry board bluffs = more suspicious

    # Position adjustment
    if hero_pos == 'OOP':
        if 'donk' in _canonicalize(flop_action):
            adj_score = max(0.15, adj_score - 0.10)  # donking OOP = very suspicious
        if pattern == 'check_probe':
            adj_score = min(0.98, adj_score + 0.05)  # OOP probe = natural line

    # Villain type adjustment for bluff success
    hand_rank = {
        'air': 0, 'trash': 0, 'bottom_pair': 1, 'marginal': 1,
        'middle_pair': 2, 'draw': 2, 'top_pair': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'set': 8, 'nuts': 9,
    }.get(hero_hand_class.lower(), 4)

    # Bluff success estimate: based on credibility and villain tendency
    base_fold = 0.40 + (adj_score - 0.50) * 0.30  # higher credibility = more folds
    if villain_af < 1.0:
        fold_adj = 0.15   # passive villains fold more
    elif villain_af > 3.0:
        fold_adj = -0.12  # aggressive villains call/raise more
    else:
        fold_adj = 0.0
    if villain_vpip > 0.45:
        fold_adj -= 0.10  # fish call down everything
    bluff_success = round(min(0.88, max(0.15, base_fold + fold_adj)), 2)

    adj_score = round(min(0.98, max(0.10, adj_score)), 2)
    should_adjust = adj_score < 0.50 and hand_rank <= 3  # suspicious bluff line

    # Build advice
    perception = _villain_perception(adj_score)
    advice = _action_advice(adj_score, hero_hand_class, river_action)

    # Tips
    tips = []
    if adj_score < 0.40 and hand_rank <= 3:
        tips.append(
            f'SUSPICIOUS LINE: Your {flop_action}-{turn_action}-{river_action} line '
            f'does not represent strong hands consistently. '
            f'Credibility={adj_score:.0%}. Thinking villain (AF={villain_af:.1f}) '
            f'will call frequently. Consider giving up or using a smaller bluff size.'
        )
    if adj_score > 0.80 and hand_rank >= 6:
        tips.append(
            f'GREAT LINE: {flop_action}-{turn_action}-{river_action} perfectly '
            f'represents your {hero_hand_class}. Credibility={adj_score:.0%}. '
            f'Villain has no reason to deviate from giving you full credit. '
            f'Bet for max value — they will call with worse.'
        )
    if pattern in ('cbet_check_bet', '3b_cbet_check_overbet') and hand_rank <= 2:
        tips.append(
            f'DELAYED BLUFF WARNING: C-betting flop, checking turn, then betting river '
            f'is a classic "missed draw" pattern. '
            f'Villains who track betting patterns LOVE calling this line down. '
            f'Either barrel the turn continuously, or check-fold river.'
        )
    if pattern == 'triple_barrel' and hand_rank in (3, 4, 5):
        tips.append(
            f'MEDIUM HAND TRIPLE BARREL: Triple barreling with {hero_hand_class} is often '
            f'incorrect — you want to reach showdown cheaply, not over-invest. '
            f'Consider checking turn/river to control pot size with a hand that beats bluffs.'
        )
    if perceived and 'bluff' in perceived.lower() and hand_rank >= 6:
        tips.append(
            f'YOUR STRONG HAND LOOKS BLUFFY: Pattern {pattern!r} makes villain think '
            f'you have: "{perceived}". '
            f'This means villain may hero-call with medium hands. '
            f'Exploit by sizing up on river — they call wider than normal.'
        )
    if not tips:
        tips.append(
            f'Line: {preflop_role}/{flop_action}/{turn_action}/{river_action}. '
            f'Pattern: {pattern!r}. Perceived: "{perceived}". '
            f'Credibility: {adj_score:.0%}. '
            f'{advice}'
        )

    return LineCredibilityResult(
        preflop_role=preflop_role,
        flop_action=flop_action,
        turn_action=turn_action,
        river_action=river_action,
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        hero_pos=hero_pos,
        villain_response=villain_response,
        villain_af=round(villain_af, 2),
        villain_vpip=round(villain_vpip, 3),
        pattern_name=pattern,
        perceived_range=perceived,
        credibility_score=adj_score,
        villain_perception=perception,
        hand_consistency=round(adj_score - base_score + 0.50, 2),
        action_advice=advice,
        should_adjust_line=should_adjust,
        bluff_success_estimate=bluff_success,
        tips=tips,
    )


def line_credibility_one_liner(result: LineCredibilityResult) -> str:
    return (
        f'[LC {result.preflop_role}|{result.pattern_name}] '
        f'cred={result.credibility_score:.0%} | '
        f'perceived="{result.perceived_range[:25]}" | '
        f'bluff_p={result.bluff_success_estimate:.0%}'
    )
