"""Tests for poker/icm_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.icm_advisor import calc_bubble_advice, bubble_summary, quick_bubble, icm_equity, BubbleAdvice


def test_result_has_required_fields():
    """BubbleAdvice should have all expected fields."""
    r = calc_bubble_advice(spots_from_money=1, hero_stack_bb=20, avg_stack_bb=40, total_players=9)
    required = ['icm_pressure', 'priority_action', 'range_tighten_pct',
                'call_threshold', 'equity_premium', 'hero_rank', 'spots_from_money',
                'avg_stack_bb', 'hero_stack_bb', 'advice']
    for field in required:
        assert hasattr(r, field), f'BubbleAdvice missing field: {field}'
    print('All fields present')


def test_bubble_spot_high_icm_pressure():
    """1 spot from money should produce maximum ICM pressure (1.0)."""
    r = calc_bubble_advice(spots_from_money=1, hero_stack_bb=15, avg_stack_bb=40, total_players=9)
    assert r.icm_pressure >= 0.8, \
        f'1 spot from money should have high ICM pressure: {r.icm_pressure}'
    print(f'1 spot ICM pressure: {r.icm_pressure}')


def test_far_from_money_lower_pressure():
    """3+ spots from money should have lower ICM pressure than 1 spot."""
    r_near = calc_bubble_advice(spots_from_money=1, hero_stack_bb=20, avg_stack_bb=40)
    r_far  = calc_bubble_advice(spots_from_money=4, hero_stack_bb=20, avg_stack_bb=40)
    assert r_far.icm_pressure <= r_near.icm_pressure, \
        f'Far ({r_far.icm_pressure}) should <= near ({r_near.icm_pressure}) pressure'
    print(f'ICM pressure: 1 spot={r_near.icm_pressure} 4 spots={r_far.icm_pressure}')


def test_survive_priority_near_bubble():
    """Short stack near bubble should prioritize survive."""
    r = calc_bubble_advice(spots_from_money=1, hero_stack_bb=8, avg_stack_bb=40)
    assert r.priority_action in ('survive', 'fold'), \
        f'Short stack near bubble should survive/fold: {r.priority_action}'
    print(f'Short stack bubble priority: {r.priority_action}')


def test_call_threshold_in_range():
    """call_threshold should be a float in (0, 1)."""
    r = calc_bubble_advice(spots_from_money=1, hero_stack_bb=20, avg_stack_bb=40)
    assert 0.0 < r.call_threshold <= 1.0, \
        f'call_threshold should be in (0,1]: {r.call_threshold}'
    print(f'call_threshold: {r.call_threshold:.0%}')


def test_short_stack_needs_premium_to_call():
    """Short stack near bubble should require higher equity to call."""
    r = calc_bubble_advice(spots_from_money=1, hero_stack_bb=10, avg_stack_bb=50)
    # call_threshold > 0.5 means need better than coinflip to call all-in
    assert r.call_threshold > 0.5, \
        f'Short stack bubble call_threshold should be > 50%: {r.call_threshold:.0%}'
    print(f'Short stack call_threshold: {r.call_threshold:.0%}')


def test_range_tighten_pct_in_range():
    """range_tighten_pct should be a float in [0, 1]."""
    r = calc_bubble_advice(spots_from_money=1, hero_stack_bb=20, avg_stack_bb=40)
    assert 0.0 <= r.range_tighten_pct <= 1.0, \
        f'range_tighten_pct should be in [0,1]: {r.range_tighten_pct}'
    print(f'range_tighten_pct: {r.range_tighten_pct:.0%}')


def test_bubble_summary_returns_string():
    """bubble_summary should return a non-empty string."""
    r = calc_bubble_advice(spots_from_money=1, hero_stack_bb=20, avg_stack_bb=40)
    s = bubble_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'bubble_summary should be non-empty: {repr(s)[:50]}'
    print(f'bubble_summary length: {len(s)}')


def test_quick_bubble_returns_string():
    """quick_bubble should return a non-empty string."""
    s = quick_bubble(spots=1, stack_bb=15, avg_bb=40)
    assert isinstance(s, str) and len(s) > 5, \
        f'quick_bubble should be non-empty string: {repr(s)[:50]}'
    print(f'quick_bubble length: {len(s)}')


def test_icm_equity_sums_to_prize_pool():
    """icm_equity from icm_advisor should sum to total prizes."""
    stacks = [4000, 3000, 2000, 1000]
    prizes = [0.50, 0.30, 0.20]
    eq = icm_equity(stacks, prizes)
    assert abs(sum(eq) - sum(prizes)) < 0.01, \
        f'ICM equity sum {sum(eq):.3f} should = prize pool {sum(prizes):.3f}'
    print(f'ICM equity sum: {sum(eq):.3f} (prize pool {sum(prizes):.3f})')


if __name__ == '__main__':
    tests = [
        test_result_has_required_fields,
        test_bubble_spot_high_icm_pressure,
        test_far_from_money_lower_pressure,
        test_survive_priority_near_bubble,
        test_call_threshold_in_range,
        test_short_stack_needs_premium_to_call,
        test_range_tighten_pct_in_range,
        test_bubble_summary_returns_string,
        test_quick_bubble_returns_string,
        test_icm_equity_sums_to_prize_pool,
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
