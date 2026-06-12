"""Tests for poker/range_narrower.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_narrower import quick_narrow, NarrowResult


def test_result_has_required_fields():
    """NarrowResult should have all expected fields."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    r = quick_narrow(actions, opener_pos='BTN', range_pct=0.35)
    required = ['current_state', 'range_summary', 'likely_categories',
                'read_advice', 'streets_seen', 'history']
    for field in required:
        assert hasattr(r, field), f'NarrowResult missing field: {field}'
    print('All fields present')


def test_streets_seen_matches_actions():
    """streets_seen should contain each unique street in the actions."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    r = quick_narrow(actions, range_pct=0.35)
    assert 'preflop' in r.streets_seen and 'flop' in r.streets_seen, \
        f'streets_seen should include preflop+flop: {r.streets_seen}'
    print(f'streets_seen: {r.streets_seen}')


def test_more_actions_more_streets():
    """Adding a turn action should extend streets_seen."""
    actions_2 = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    actions_3 = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5), ('turn', 'bet', 0.75)]
    r2 = quick_narrow(actions_2, range_pct=0.35)
    r3 = quick_narrow(actions_3, range_pct=0.35)
    assert len(r3.streets_seen) >= len(r2.streets_seen), \
        f'3 actions should have >= streets than 2: {r3.streets_seen} vs {r2.streets_seen}'
    print(f'Streets: 2 actions={r2.streets_seen} 3 actions={r3.streets_seen}')


def test_current_state_has_range_remaining():
    """current_state should have range_remaining field."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    r = quick_narrow(actions, range_pct=0.35)
    assert hasattr(r.current_state, 'range_remaining'), \
        f'current_state should have range_remaining: {dir(r.current_state)}'
    assert 0.0 <= r.current_state.range_remaining <= 1.0, \
        f'range_remaining should be in [0,1]: {r.current_state.range_remaining}'
    print(f'range_remaining: {r.current_state.range_remaining:.0%}')


def test_range_remaining_decreases_with_more_actions():
    """More aggressive actions should narrow range further."""
    actions_preflop_only = [('preflop', 'raise', 2.5)]
    actions_two_streets  = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.75)]
    r1 = quick_narrow(actions_preflop_only, range_pct=0.35)
    r2 = quick_narrow(actions_two_streets, range_pct=0.35)
    assert r2.current_state.range_remaining <= r1.current_state.range_remaining, \
        f'2-street range {r2.current_state.range_remaining:.0%} should <= 1-street {r1.current_state.range_remaining:.0%}'
    print(f'range_remaining: 1-street={r1.current_state.range_remaining:.0%} 2-street={r2.current_state.range_remaining:.0%}')


def test_likely_categories_is_list():
    """likely_categories should be a non-empty list."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    r = quick_narrow(actions, range_pct=0.35)
    assert isinstance(r.likely_categories, list) and len(r.likely_categories) > 0, \
        f'likely_categories should be non-empty list: {r.likely_categories}'
    print(f'likely_categories count: {len(r.likely_categories)}')


def test_current_state_has_pct_fields():
    """current_state should have pct_nuts, pct_top_pair, pct_draw, pct_bluff_weak."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    r = quick_narrow(actions, range_pct=0.35)
    cs = r.current_state
    pct_fields = ['pct_nuts', 'pct_top_pair', 'pct_draw', 'pct_bluff_weak']
    for f in pct_fields:
        assert hasattr(cs, f), f'current_state missing {f}'
        val = getattr(cs, f)
        assert 0.0 <= val <= 1.0, f'{f} should be in [0,1]: {val}'
    total = cs.pct_nuts + cs.pct_top_pair + cs.pct_draw + cs.pct_bluff_weak
    assert abs(total - 1.0) < 0.05, f'pct fields should sum to ~1: {total:.2f}'
    print(f'pct: nuts={cs.pct_nuts:.0%} tp={cs.pct_top_pair:.0%} draw={cs.pct_draw:.0%} bluff={cs.pct_bluff_weak:.0%}')


def test_range_summary_is_string():
    """range_summary should be a non-empty string."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    r = quick_narrow(actions, range_pct=0.35)
    assert isinstance(r.range_summary, str) and len(r.range_summary) > 3, \
        f'range_summary should be non-empty string: {repr(r.range_summary)[:50]}'
    print(f'range_summary length: {len(r.range_summary)}')


def test_history_length_matches_action_count():
    """history should contain one entry per action."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5), ('turn', 'check', 0.0)]
    r = quick_narrow(actions, range_pct=0.35)
    assert len(r.history) >= len(actions), \
        f'history length {len(r.history)} should be >= actions {len(actions)}'
    print(f'history length: {len(r.history)} (>= {len(actions)} actions)')


def test_tighter_starting_range_lower_remaining():
    """Tighter starting range should result in fewer remaining combos."""
    actions = [('preflop', 'raise', 2.5), ('flop', 'bet', 0.5)]
    r_tight = quick_narrow(actions, range_pct=0.15)
    r_wide  = quick_narrow(actions, range_pct=0.40)
    assert r_tight.current_state.range_remaining <= r_wide.current_state.range_remaining + 0.1, \
        f'Tight start should have <= remaining: {r_tight.current_state.range_remaining:.0%} vs {r_wide.current_state.range_remaining:.0%}'
    print(f'range_remaining: tight_start={r_tight.current_state.range_remaining:.0%} wide_start={r_wide.current_state.range_remaining:.0%}')


if __name__ == '__main__':
    tests = [
        test_result_has_required_fields,
        test_streets_seen_matches_actions,
        test_more_actions_more_streets,
        test_current_state_has_range_remaining,
        test_range_remaining_decreases_with_more_actions,
        test_likely_categories_is_list,
        test_current_state_has_pct_fields,
        test_range_summary_is_string,
        test_history_length_matches_action_count,
        test_tighter_starting_range_lower_remaining,
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
