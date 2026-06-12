"""Tests for poker/mrating.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.mrating import calculate_m, m_from_bb, zone_advice, MRating


def test_m_formula():
    """M = stack / cost_per_orbit = stack / (BB + SB + ante*players)."""
    # cost_per_orbit = 100 + 50 + 10*6 = 210
    r = calculate_m(stack=1200, big_blind=100, small_blind=50, ante=10, players=6)
    expected_m = 1200 / 210
    assert abs(r.m - expected_m) < 0.01, \
        f'M should = stack/orbit_cost {expected_m:.2f}: {r.m:.2f}'
    print(f'M: {r.m:.2f} (expected {expected_m:.2f})')


def test_result_has_required_fields():
    """MRating should have all expected fields."""
    r = calculate_m(stack=2000, big_blind=100, small_blind=50, players=6)
    required = ['m', 'm_effective', 'zone', 'zone_color', 'strategy',
                'summary', 'cost_per_orbit', 'push_threshold']
    for field in required:
        assert hasattr(r, field), f'MRating missing field: {field}'
    print('All fields present')


def test_short_stack_low_m():
    """Very short stack should have low M (< 5)."""
    r = calculate_m(stack=300, big_blind=100, small_blind=50, ante=10, players=6)
    assert r.m < 5.0, f'Short stack M should be < 5: {r.m:.2f}'
    print(f'Short stack M: {r.m:.2f}')


def test_deep_stack_high_m():
    """Deep stack should have high M (> 20)."""
    r = calculate_m(stack=5000, big_blind=100, small_blind=50, ante=0, players=6)
    assert r.m > 20.0, f'Deep stack M should be > 20: {r.m:.2f}'
    print(f'Deep stack M: {r.m:.2f}')


def test_larger_stack_larger_m():
    """Doubling stack should double M."""
    r1 = calculate_m(stack=1000, big_blind=100, small_blind=50, ante=0, players=6)
    r2 = calculate_m(stack=2000, big_blind=100, small_blind=50, ante=0, players=6)
    assert abs(r2.m - 2 * r1.m) < 0.1, \
        f'Double stack should double M: {r1.m:.2f} -> {r2.m:.2f}'
    print(f'M doubles: {r1.m:.2f} -> {r2.m:.2f}')


def test_zone_is_nonempty_string():
    """zone should be a non-empty string."""
    r = calculate_m(stack=1200, big_blind=100, small_blind=50, ante=10, players=6)
    assert isinstance(r.zone, str) and len(r.zone) > 0, \
        f'zone should be non-empty string: {repr(r.zone)}'
    print(f'zone: {r.zone}')


def test_m_from_bb_formula():
    """m_from_bb(bb, players) should approximate M from big blinds."""
    result = m_from_bb(10.0, players=6)
    # M ~ stack_bb / players (simplified; actual orbit cost / BB > 1)
    assert result > 0, f'm_from_bb should be positive: {result}'
    assert result <= 10.0, f'm_from_bb(10bb, 6p) should <= 10bb: {result}'
    print(f'm_from_bb(10bb, 6p): {result:.2f}')


def test_zone_advice_has_required_keys():
    """zone_advice should return dict with standard keys."""
    za = zone_advice(5.0)
    required = {'zone', 'color', 'open_range', 'three_bet', 'postflop', 'avoid'}
    for k in required:
        assert k in za, f'zone_advice missing key: {k}'
    print(f'zone_advice keys: {list(za.keys())}')


def test_zone_advice_emergency_vs_safe():
    """Low M zone_advice should differ from high M zone_advice."""
    za_low  = zone_advice(2.0)
    za_high = zone_advice(25.0)
    assert za_low['zone'] != za_high['zone'], \
        f'Low M and high M should have different zones: {za_low["zone"]} vs {za_high["zone"]}'
    print(f'zone M=2: {za_low["zone"]} | M=25: {za_high["zone"]}')


def test_cost_per_orbit_correct():
    """cost_per_orbit = BB + SB + ante * players."""
    r = calculate_m(stack=1000, big_blind=100, small_blind=50, ante=10, players=6)
    expected = 100 + 50 + 10 * 6
    assert r.cost_per_orbit == expected, \
        f'cost_per_orbit should = {expected}: {r.cost_per_orbit}'
    print(f'cost_per_orbit: {r.cost_per_orbit} (expected {expected})')


if __name__ == '__main__':
    tests = [
        test_m_formula,
        test_result_has_required_fields,
        test_short_stack_low_m,
        test_deep_stack_high_m,
        test_larger_stack_larger_m,
        test_zone_is_nonempty_string,
        test_m_from_bb_formula,
        test_zone_advice_has_required_keys,
        test_zone_advice_emergency_vs_safe,
        test_cost_per_orbit_correct,
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
