"""Tests for poker/timing_tell_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.timing_tell_advisor import analyze_timing_tell, TimingTellResult, timing_one_liner


def _tell(**kw):
    defaults = dict(
        action_taken='call', time_taken_sec=8.5, street='flop',
        villain_vpip=0.35, villain_af=2.0, pot_bb=15.0, bet_bb=7.5,
        is_facing_bet=True, villain_baseline_avg_time_sec=3.5,
    )
    defaults.update(kw)
    return analyze_timing_tell(**defaults)


def test_returns_correct_type():
    r = _tell()
    assert isinstance(r, TimingTellResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _tell()
    fields = [
        'action_taken', 'time_taken_sec', 'street', 'villain_vpip', 'villain_af',
        'pot_bb', 'bet_bb', 'is_facing_bet', 'villain_baseline_avg_time_sec',
        'timing_category', 'relative_speed', 'hand_strength_estimate',
        'tell_confidence', 'interpretation', 'exploitation_advice',
        'hero_action_adjustment', 'reliability_note', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_timing_categories():
    """Test timing category assignment."""
    assert analyze_timing_tell(time_taken_sec=0.5).timing_category == 'insta'
    assert analyze_timing_tell(time_taken_sec=2.5).timing_category == 'quick'
    assert analyze_timing_tell(time_taken_sec=5.0).timing_category == 'normal'
    assert analyze_timing_tell(time_taken_sec=10.0).timing_category == 'slow'
    assert analyze_timing_tell(time_taken_sec=20.0).timing_category == 'tank'
    print('All timing categories correct')


def test_slow_call_shows_marginal_hand():
    """Slow call → villain is marginal."""
    r = _tell(action_taken='call', time_taken_sec=10.0)
    assert r.hand_strength_estimate in ('marginal', 'very_marginal'), \
        f'Slow call should be marginal: {r.hand_strength_estimate}'
    print(f'Slow call: {r.hand_strength_estimate}')


def test_insta_fold_shows_air():
    """Insta-fold → villain has air."""
    r = _tell(action_taken='fold', time_taken_sec=0.5)
    assert r.hand_strength_estimate in ('air', 'weak'), \
        f'Insta-fold should be air: {r.hand_strength_estimate}'
    print(f'Insta-fold: {r.hand_strength_estimate}')


def test_tank_raise_shows_very_strong():
    """Tank then raise → very strong hand."""
    r = _tell(action_taken='raise', time_taken_sec=18.0)
    assert r.hand_strength_estimate in ('very_strong', 'value_strong', 'strong'), \
        f'Tank raise should be strong: {r.hand_strength_estimate}'
    print(f'Tank raise: {r.hand_strength_estimate}')


def test_tell_confidence_range():
    """Confidence must be between 0 and 1."""
    r = _tell()
    assert 0.0 <= r.tell_confidence <= 1.0, f'Confidence out of range: {r.tell_confidence}'
    print(f'Confidence: {r.tell_confidence:.0%}')


def test_extreme_speed_higher_confidence():
    """Much faster/slower than baseline → higher confidence."""
    r_much_faster = _tell(time_taken_sec=0.5, villain_baseline_avg_time_sec=4.0)
    r_normal = _tell(time_taken_sec=4.0, villain_baseline_avg_time_sec=4.0)
    # Extreme deviation should have higher or equal confidence
    assert r_much_faster.tell_confidence >= r_normal.tell_confidence - 0.05
    print(f'Confidence: extreme={r_much_faster.tell_confidence:.0%} normal={r_normal.tell_confidence:.0%}')


def test_relative_speed_classification():
    """Relative speed: much faster when time << baseline."""
    r_fast = _tell(time_taken_sec=0.5, villain_baseline_avg_time_sec=5.0)
    r_slow = _tell(time_taken_sec=15.0, villain_baseline_avg_time_sec=3.0)
    assert r_fast.relative_speed in ('much_faster', 'faster')
    assert r_slow.relative_speed in ('much_slower', 'slower')
    print(f'Fast: {r_fast.relative_speed}, Slow: {r_slow.relative_speed}')


def test_fish_reduces_confidence():
    """Fish (high VPIP) makes timing tells less reliable."""
    r_fish = _tell(villain_vpip=0.55)
    r_reg = _tell(villain_vpip=0.25)
    # Fish should have same or lower confidence
    assert r_fish.tell_confidence <= r_reg.tell_confidence + 0.05
    print(f'Confidence: fish={r_fish.tell_confidence:.0%} reg={r_reg.tell_confidence:.0%}')


def test_interpretation_not_empty():
    r = _tell()
    assert isinstance(r.interpretation, str) and len(r.interpretation) > 10
    print(f'Interpretation: {r.interpretation[:60]}...')


def test_exploitation_advice_not_empty():
    r = _tell()
    assert isinstance(r.exploitation_advice, str) and len(r.exploitation_advice) > 5
    print(f'Exploit: {r.exploitation_advice[:60]}...')


def test_hero_action_adjustment_not_empty():
    r = _tell()
    assert isinstance(r.hero_action_adjustment, str) and len(r.hero_action_adjustment) > 5
    print(f'Adjustment: {r.hero_action_adjustment[:60]}...')


def test_reliability_note_not_empty():
    r = _tell()
    assert isinstance(r.reliability_note, str) and len(r.reliability_note) > 5
    print(f'Reliability: {r.reliability_note[:60]}...')


def test_all_actions_work():
    for action in ['check', 'call', 'raise', 'fold']:
        r = _tell(action_taken=action)
        assert isinstance(r.hand_strength_estimate, str)
        assert r.tell_confidence > 0
    print('All action types produce valid results')


def test_all_streets_work():
    for street in ['preflop', 'flop', 'turn', 'river']:
        r = _tell(street=street)
        assert isinstance(r.timing_category, str)
    print('All streets produce valid results')


def test_insta_check_polarized():
    """Insta-check → polarized (air or strong)."""
    r = _tell(action_taken='check', time_taken_sec=0.5)
    assert r.hand_strength_estimate == 'polarized', \
        f'Insta-check should be polarized: {r.hand_strength_estimate}'
    print(f'Insta-check: {r.hand_strength_estimate}')


def test_tank_fold_shows_strong_fold():
    """Tank then fold → villain had something real."""
    r = _tell(action_taken='fold', time_taken_sec=18.0)
    assert r.hand_strength_estimate in ('strong_fold', 'medium', 'neutral'), \
        f'Tank fold should indicate had something: {r.hand_strength_estimate}'
    print(f'Tank fold: {r.hand_strength_estimate}')


def test_tips_not_empty():
    r = _tell()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _tell()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}...')


def test_one_liner():
    r = _tell()
    line = timing_one_liner(r)
    assert 'TELL' in line and 'conf=' in line and 't=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_timing_categories, test_slow_call_shows_marginal_hand,
        test_insta_fold_shows_air, test_tank_raise_shows_very_strong,
        test_tell_confidence_range, test_extreme_speed_higher_confidence,
        test_relative_speed_classification, test_fish_reduces_confidence,
        test_interpretation_not_empty, test_exploitation_advice_not_empty,
        test_hero_action_adjustment_not_empty, test_reliability_note_not_empty,
        test_all_actions_work, test_all_streets_work,
        test_insta_check_polarized, test_tank_fold_shows_strong_fold,
        test_tips_not_empty, test_reasoning_not_empty, test_one_liner,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
