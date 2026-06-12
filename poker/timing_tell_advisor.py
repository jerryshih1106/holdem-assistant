"""
Timing Tell Advisor (timing_tell_advisor.py)

In online poker, action speed is a reliable tell. Unlike live poker physical tells,
online timing tells are consistent and exploitable:

VILLAIN TIMING TELLS:
  quick_check (<1s):  Usually air (auto-check) OR very strong (setting up trap)
                      RARELY medium strength (middle hands usually take a beat to decide)
  slow_check (4-8s):  Often medium strength debating bet vs check
  quick_call (<2s):   Often prepared to call (drew to a hand?) or calling station
  slow_call (6-15s):  Often marginal hand, pondering folding
  quick_raise (<1s):  Often very strong (premiums raise fast) or scripted aggression
  slow_raise (5-15s): Often strong hand sizing decision or semi-bluff deciding
  quick_fold (<1s):   Often air (auto-fold) or out-of-range hand
  slow_fold (4-10s):  Often considered calling, has something, gave up

HERO TIMING STRATEGY:
  Consistent timing: Prevents opponent from reading your speed as a tell
  Mix speeds: Occasionally slow down with strong hands (prevent insta-raise tell)
  Auto-actions are visible: Click quickly on fold/check in same spot every time?
                             Opponent can detect auto-action patterns

CAUTION:
  Timing tells are NOT definitive. They indicate tendencies, not certainties.
  A good player may deliberately vary timing to exploit those who read timing.
  Use timing as ONE factor in a multi-factor read, not the sole basis.

Usage:
    from poker.timing_tell_advisor import analyze_timing_tell, TimingTellResult, timing_one_liner

    result = analyze_timing_tell(
        action_taken='call',
        time_taken_sec=8.5,
        street='flop',
        villain_vpip=0.35,
        villain_af=2.0,
        pot_bb=15.0,
        bet_bb=7.5,
        is_facing_bet=True,
        villain_baseline_avg_time_sec=3.5,
    )
    print(timing_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# ── Timing categories ─────────────────────────────────────────────────────────

def _categorize_time(sec: float) -> str:
    if sec < 1.5:  return 'insta'
    if sec < 3.5:  return 'quick'
    if sec < 7.0:  return 'normal'
    if sec < 15.0: return 'slow'
    return 'tank'


def _relative_speed(time_sec: float, baseline_sec: float) -> str:
    """Relative to villain's own baseline timing."""
    if baseline_sec <= 0:
        return _categorize_time(time_sec)
    ratio = time_sec / baseline_sec
    if ratio < 0.4:   return 'much_faster'
    if ratio < 0.75:  return 'faster'
    if ratio < 1.4:   return 'normal'
    if ratio < 2.0:   return 'slower'
    return 'much_slower'


# ── Interpretation tables ─────────────────────────────────────────────────────

# (action, timing_category) → (hand_strength_estimate, confidence, interpretation)
_TELL_TABLE = {
    ('check', 'insta'):  ('polarized', 0.55,
        'Insta-check: either air (auto-check) or very strong trap. '
        'Rarely middle strength. Probe with a bet to define their hand.'),
    ('check', 'quick'):  ('air_or_medium', 0.50,
        'Quick check: slightly weak, but could be setting up check-raise. '
        'Moderate signal. Consider betting.'),
    ('check', 'normal'): ('medium', 0.45,
        'Normal-speed check: neutral signal. Could be any hand type.'),
    ('check', 'slow'):   ('medium_strong', 0.55,
        'Slow check: deliberating between bet and check. '
        'Often has a medium-strength hand. Check-raise risk is elevated.'),
    ('check', 'tank'):   ('strong', 0.60,
        'Long tank then check: very likely setting up a check-raise trap. '
        'Do NOT bet if you intend to fold to a raise.'),

    ('call', 'insta'):   ('medium_plus_draw', 0.60,
        'Insta-call: often had decided to call before action (draw or strong hand). '
        'Rarely a bluff catcher — villain knew they were calling. '
        'Continue applying pressure on later streets.'),
    ('call', 'quick'):   ('medium_draw', 0.55,
        'Quick call: moderate strength or draw. '
        'Consider: did the board connect with their preflop range?'),
    ('call', 'normal'):  ('medium', 0.45,
        'Normal-speed call: neutral. Could be anything from marginal pair to draw.'),
    ('call', 'slow'):    ('marginal', 0.60,
        'Slow call: villain considered folding. Likely a marginal hand or bluff catcher. '
        'Apply pressure on next street — villain is NOT comfortable.'),
    ('call', 'tank'):    ('very_marginal', 0.65,
        'Tank then call: villain nearly folded. Very marginal hand. '
        'Fire on next street — they are on a tough call and may fold to more pressure.'),

    ('raise', 'insta'):  ('strong_or_bluff', 0.55,
        'Insta-raise: either a premium hand (auto-raise) or a pre-planned bluff. '
        'Polarized range. Call/4-bet with strong hands; fold marginal hands.'),
    ('raise', 'quick'):  ('strong', 0.60,
        'Quick raise: often strong — strong hands raise quickly to build pot. '
        'Value-heavy range. Tighten your calling range.'),
    ('raise', 'normal'): ('medium_strong', 0.50,
        'Normal raise speed: could be balanced. No strong inference.'),
    ('raise', 'slow'):   ('value_strong', 0.65,
        'Slow raise: villain took time to size their raise. '
        'Often means a strong made hand making a sizing decision. '
        'Respect this raise — consider folding middle-strength hands.'),
    ('raise', 'tank'):   ('very_strong', 0.70,
        'Tank then raise: villain deliberated, then chose to escalate. '
        'Usually a very strong hand. Fold everything except premium hands.'),

    ('fold', 'insta'):   ('air', 0.70,
        'Insta-fold: clear air. Villain had nothing. '
        'Note: villain may be auto-folding from outside their range — a tight player signal.'),
    ('fold', 'quick'):   ('weak', 0.60,
        'Quick fold: clearly did not want to continue. Weaker hand.'),
    ('fold', 'normal'):  ('neutral', 0.40,
        'Normal fold speed: no strong inference.'),
    ('fold', 'slow'):    ('medium', 0.60,
        'Slow fold: villain had something but gave up. '
        'Likely 2nd pair or weak draw. Note: they DO call sometimes.'),
    ('fold', 'tank'):    ('strong_fold', 0.65,
        'Tank then fold: villain had a real hand but was priced out or bluffed off. '
        'They are capable of folding strong hands — adjust bluff frequency upward.'),
}


def _exploit_based_on_tell(action: str, timing: str, hand_strength: str) -> str:
    """Generate exploitation strategy from timing tell interpretation."""
    if action == 'check':
        if timing in ('insta', 'quick') and hand_strength in ('air_or_medium', 'polarized'):
            return 'Bet for value or to bluff. If check-raised, may be a trap — re-evaluate.'
        if timing in ('slow', 'tank'):
            return 'Check behind — check-raise risk is high. Extract value later.'
        return 'Normal bet/check based on hand strength.'
    if action == 'call':
        if timing in ('insta', 'quick'):
            return 'Villain is prepared to continue. Do not bluff future streets. Value bet strong hands.'
        if timing in ('slow', 'tank'):
            return 'Villain is marginal. Fire again on next street to fold them out.'
        return 'Normal street analysis applies.'
    if action == 'raise':
        if timing in ('insta', 'quick'):
            return 'Respect the raise — lean towards folding unless strong. If bluffing back, risk is high.'
        if timing in ('slow', 'tank'):
            return 'Strong hand raise. Fold everything except nuts/near-nuts. Do not bluff.'
        return 'Treat as normal raise — use pot odds + equity.'
    if action == 'fold':
        if timing in ('slow', 'tank'):
            return 'Villain does fold strong hands. Increase bluff frequency vs this villain.'
        return 'Note: villain folded. Adjust future bluff frequency accordingly.'
    return 'Standard analysis.'


@dataclass
class TimingTellResult:
    """Timing tell analysis for an observed villain action."""
    action_taken: str
    time_taken_sec: float
    street: str
    villain_vpip: float
    villain_af: float
    pot_bb: float
    bet_bb: float
    is_facing_bet: bool
    villain_baseline_avg_time_sec: float

    # Analysis
    timing_category: str           # 'insta', 'quick', 'normal', 'slow', 'tank'
    relative_speed: str            # vs villain's own baseline
    hand_strength_estimate: str    # 'air', 'weak', 'medium', 'strong', 'polarized', etc.
    tell_confidence: float         # 0-1
    interpretation: str

    # Exploitation
    exploitation_advice: str
    hero_action_adjustment: str    # how to adjust hero's next action

    # Reliability
    reliability_note: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_timing_tell(
    action_taken: str = 'call',
    time_taken_sec: float = 8.5,
    street: str = 'flop',
    villain_vpip: float = 0.35,
    villain_af: float = 2.0,
    pot_bb: float = 15.0,
    bet_bb: float = 7.5,
    is_facing_bet: bool = True,
    villain_baseline_avg_time_sec: float = 3.5,
) -> TimingTellResult:
    """
    Analyze a timing tell from villain's action speed.

    Args:
        action_taken:              The action villain took ('check', 'call', 'raise', 'fold')
        time_taken_sec:            Seconds taken to act
        street:                    Current street
        villain_vpip:              Villain VPIP
        villain_af:                Villain aggression factor
        pot_bb:                    Current pot in BB
        bet_bb:                    Bet size villain was facing (0 if first to act)
        is_facing_bet:             Was villain facing a bet?
        villain_baseline_avg_time_sec: Villain's normal average time per action

    Returns:
        TimingTellResult
    """
    timing = _categorize_time(time_taken_sec)
    rel_speed = _relative_speed(time_taken_sec, villain_baseline_avg_time_sec)

    # Look up tell table
    key = (action_taken, timing)
    default = ('unknown', 0.40, 'No strong inference from timing at this speed.')
    hand_est, conf, interp = _TELL_TABLE.get(key, default)

    # Adjust confidence based on villain type
    if villain_vpip > 0.45:
        # Fish act quickly on many hands — timing less reliable
        conf = max(0.30, conf - 0.10)
    if villain_af >= 3.0:
        # LAG/aggressive players sometimes fast-raise as a scripted move
        if action_taken == 'raise' and timing == 'insta':
            conf = max(0.35, conf - 0.10)

    # Also adjust for relative speed
    if rel_speed in ('much_faster', 'much_slower'):
        conf = min(0.85, conf + 0.10)  # extreme deviation is more reliable

    exploit = _exploit_based_on_tell(action_taken, timing, hand_est)

    # Hero action adjustment
    adj_map = {
        'strong':        'Respect: tighten calling range, fold marginal hands.',
        'very_strong':   'Fold all but nuts/near-nuts. Do not bluff.',
        'medium':        'Standard play based on hand strength.',
        'air':           'Consider hero calling range wider (villain often has air).',
        'polarized':     'Bet with medium hands to define; check-raise risk exists with strong hands.',
        'marginal':      'Apply pressure next street — villain is not committed.',
        'very_marginal': 'Fire again. Villain nearly folded and may fold to more bets.',
        'air_or_medium': 'Bet most hands as a probe. Check-raise risk is low.',
        'medium_plus_draw': 'Value bet — villain will continue. Do not bluff.',
        'medium_strong': 'Cautious. Do not bluff. Extract value if strong.',
        'value_strong':  'Very cautious. Fold unless premium.',
        'strong_fold':   'Villain CAN fold strong hands. Increase bluff frequency.',
        'strong_or_bluff': 'Mixed range — use blockers/board to decide.',
        'medium_draw':   'Continue applying pressure. Villain on a draw.',
        'neutral':       'No adjustment required.',
        'unknown':       'No adjustment. Default strategy.',
    }
    hero_adj = adj_map.get(hand_est, 'Standard play.')

    # Reliability note
    if villain_baseline_avg_time_sec <= 0:
        rel_note = (
            'No baseline available. Timing tells are ABSOLUTE (based on raw seconds). '
            'More reliable if you have villain baseline timing data.'
        )
    elif rel_speed in ('much_faster', 'much_slower'):
        rel_note = (
            f'RELIABLE: This action ({time_taken_sec:.1f}s) is significantly '
            f'{"faster" if rel_speed == "much_faster" else "slower"} than '
            f"villain's baseline ({villain_baseline_avg_time_sec:.1f}s). "
            f'Deviation signals are more reliable.'
        )
    else:
        rel_note = (
            f'MODERATE: This action speed ({time_taken_sec:.1f}s) is '
            f'{rel_speed} vs villain baseline ({villain_baseline_avg_time_sec:.1f}s). '
            f'Use with other reads.'
        )

    reasoning = (
        f'{action_taken.upper()} in {time_taken_sec:.1f}s on {street}. '
        f'Category: {timing}. Relative speed: {rel_speed}. '
        f'Estimated hand: {hand_est} (confidence={conf:.0%}). '
        f'Villain: VPIP={villain_vpip:.0%}, AF={villain_af:.1f}. '
        f'Pot={pot_bb:.1f}BB, bet={bet_bb:.1f}BB.'
    )

    tips = []
    if timing == 'tank':
        tips.append(
            f'TANK ACTION: Villain took {time_taken_sec:.0f}s — far above normal. '
            f'This is the most reliable timing tell. '
            f'Tank→raise: very strong. Tank→call: very marginal. Tank→fold: had something. '
            f'Confidence: HIGH. Adjust strategy accordingly.'
        )
    if villain_vpip > 0.45:
        tips.append(
            f'FISH CAVEAT: High VPIP ({villain_vpip:.0%}) makes timing tells less reliable. '
            f'Fish often insta-call without careful thought. '
            f'Do not over-weight timing tells vs this player.'
        )
    if action_taken == 'call' and timing in ('slow', 'tank') and street in ('turn', 'river'):
        tips.append(
            f'PRESSURED CALL: Villain is on the ropes. '
            f'They nearly folded but called. Fire again on next street. '
            f'This pattern (slow call → fire again) is highly profitable.'
        )
    if action_taken == 'raise' and timing == 'insta':
        tips.append(
            f'INSTA-RAISE NOTE: Could be auto-raise script (strong) or deliberate fast bluff. '
            f'Consider: is this villain aggressive by default (AF={villain_af:.1f})? '
            f'High AF = might be scripted bluff. '
            f'Use board texture + range to calibrate.'
        )
    if not tips:
        tips.append(
            f'{timing.upper()} {action_taken}: estimated strength={hand_est} '
            f'(conf={conf:.0%}). {exploit}'
        )

    return TimingTellResult(
        action_taken=action_taken,
        time_taken_sec=round(time_taken_sec, 2),
        street=street,
        villain_vpip=round(villain_vpip, 3),
        villain_af=round(villain_af, 2),
        pot_bb=round(pot_bb, 1),
        bet_bb=round(bet_bb, 1),
        is_facing_bet=is_facing_bet,
        villain_baseline_avg_time_sec=round(villain_baseline_avg_time_sec, 2),
        timing_category=timing,
        relative_speed=rel_speed,
        hand_strength_estimate=hand_est,
        tell_confidence=round(conf, 2),
        interpretation=interp,
        exploitation_advice=exploit,
        hero_action_adjustment=hero_adj,
        reliability_note=rel_note,
        reasoning=reasoning,
        tips=tips,
    )


def timing_one_liner(r: TimingTellResult) -> str:
    return (
        f'[TELL {r.action_taken.upper()}@{r.timing_category}|{r.street}] '
        f'{r.hand_strength_estimate.upper()} | '
        f't={r.time_taken_sec:.1f}s({r.relative_speed}) conf={r.tell_confidence:.0%} | '
        f'{r.exploitation_advice[:50]}...'
    )
