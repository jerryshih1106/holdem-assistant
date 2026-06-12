"""Tests for poker/spr_planner.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.spr_planner import analyze_spr, spr_summary


def test_spr_calculated_correctly():
    """SPR = eff_stack_bb / pot_bb."""
    r = analyze_spr(pot_bb=10.0, eff_stack_bb=80.0, hand_percentile=0.70)
    expected_spr = 80.0 / 10.0  # = 8.0
    assert abs(r.spr - expected_spr) < 0.1, \
        f'SPR should be {expected_spr:.1f}: {r.spr:.1f}'
    print(f'SPR: {r.spr:.1f} (expected {expected_spr:.1f})')


def test_low_spr_commits():
    """Low SPR (<= 2) with strong hand should recommend committing."""
    r = analyze_spr(pot_bb=40.0, eff_stack_bb=60.0, hand_percentile=0.85, n_comm=3)
    assert r.spr <= 2.0, f'SPR should be low: {r.spr:.1f}'
    assert r.spr_category in ('ultra_low', 'low', 'micro'), \
        f'Low SPR category expected: {r.spr_category}'
    print(f'Low SPR {r.spr:.1f}: commit_urgency={r.commit_urgency}')


def test_high_spr_caution():
    """High SPR (>= 13) should be classified as high and suggest caution."""
    r = analyze_spr(pot_bb=5.0, eff_stack_bb=200.0, hand_percentile=0.65, n_comm=3)
    assert r.spr >= 13.0, f'SPR should be high: {r.spr:.1f}'
    assert r.spr_category == 'high', f'High SPR category expected: {r.spr_category}'
    print(f'High SPR {r.spr:.1f}: category={r.spr_category}')


def test_spr_category_valid():
    """spr_category should be a known string."""
    r = analyze_spr(pot_bb=12.0, eff_stack_bb=80.0, hand_percentile=0.70, n_comm=3)
    valid = ('ultra_low', 'low', 'micro', 'medium', 'medium_high', 'high')
    assert r.spr_category in valid, \
        f'spr_category should be one of {valid}: {r.spr_category!r}'
    print(f'SPR category: {r.spr_category!r}')


def test_strong_hand_clears_bar():
    """Premium hand (percentile=0.92) should clear commit threshold."""
    r = analyze_spr(pot_bb=12.0, eff_stack_bb=60.0, hand_percentile=0.92, n_comm=3)
    assert r.hand_clears_bar is True, \
        f'Premium hand should clear bar: {r.hand_clears_bar}'
    print(f'Premium hand clears bar: {r.hand_clears_bar}')


def test_weak_hand_doesnt_clear_bar():
    """Weak hand (percentile=0.25) should not clear commit threshold in medium SPR."""
    r = analyze_spr(pot_bb=12.0, eff_stack_bb=80.0, hand_percentile=0.25, n_comm=3)
    assert r.hand_clears_bar is False, \
        f'Weak hand should not clear bar: {r.hand_clears_bar}'
    print(f'Weak hand clears bar: {r.hand_clears_bar}')


def test_geo_sizes_length_matches_streets():
    """geo_sizes should have one entry per remaining street."""
    r = analyze_spr(pot_bb=10.0, eff_stack_bb=80.0, hand_percentile=0.70, n_comm=3)
    assert len(r.geo_sizes) == r.streets_left, \
        f'geo_sizes len {len(r.geo_sizes)} should == streets_left {r.streets_left}'
    assert len(r.geo_sizes_bb) == r.streets_left
    print(f'Streets left: {r.streets_left}, geo_sizes: {r.geo_sizes}')


def test_geo_sizes_positive():
    """All geometric sizes should be positive fractions."""
    r = analyze_spr(pot_bb=10.0, eff_stack_bb=80.0, hand_percentile=0.75, n_comm=3)
    for i, s in enumerate(r.geo_sizes):
        assert 0 < s <= 2.0, f'geo_sizes[{i}] out of range: {s}'
    print(f'Geo sizes (pot fractions): {[f"{x:.0%}" for x in r.geo_sizes]}')


def test_breakeven_equity_between_0_and_1():
    """breakeven_equity should be between 0 and 1."""
    r = analyze_spr(pot_bb=10.0, eff_stack_bb=80.0, hand_percentile=0.70, n_comm=5)
    assert 0.0 <= r.breakeven_equity <= 1.0, \
        f'breakeven_equity out of bounds: {r.breakeven_equity}'
    print(f'Breakeven equity: {r.breakeven_equity:.0%}')


def test_tips_is_list():
    """tips should be a list."""
    r = analyze_spr(pot_bb=12.0, eff_stack_bb=80.0, hand_percentile=0.70, n_comm=3)
    assert isinstance(r.tips, list), f'tips should be list: {type(r.tips)}'
    print(f'Tips count: {len(r.tips)}')


def test_spr_summary_returns_string():
    """spr_summary should return a non-empty string."""
    r = analyze_spr(pot_bb=12.0, eff_stack_bb=80.0, hand_percentile=0.75, n_comm=3)
    s = spr_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'spr_summary should return non-empty string: {s!r}'
    print(f'SPR summary: {s[:60]}')


if __name__ == '__main__':
    tests = [
        test_spr_calculated_correctly,
        test_low_spr_commits,
        test_high_spr_caution,
        test_spr_category_valid,
        test_strong_hand_clears_bar,
        test_weak_hand_doesnt_clear_bar,
        test_geo_sizes_length_matches_streets,
        test_geo_sizes_positive,
        test_breakeven_equity_between_0_and_1,
        test_tips_is_list,
        test_spr_summary_returns_string,
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
