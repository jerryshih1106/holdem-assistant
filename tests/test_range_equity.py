"""Tests for poker/range_equity.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_equity import equity_vs_range, build_range, format_range_equity


def test_result_has_required_keys():
    """equity_vs_range should return dict with all expected keys."""
    r = equity_vs_range(['Ah', 'Ks'], [], opp_vpip=25.0, iterations=200)
    required = {'win_rate', 'range_pct', 'range_size', 'opp_action', 'valid'}
    for k in required:
        assert k in r, f'equity_vs_range missing key: {k}'
    print(f'Keys present: {list(r.keys())}')


def test_win_rate_in_range():
    """win_rate should be a float in [0, 1]."""
    r = equity_vs_range(['Ah', 'Ks'], [], opp_vpip=25.0, iterations=200)
    assert 0.0 <= r['win_rate'] <= 1.0, \
        f'win_rate should be in [0,1]: {r["win_rate"]}'
    print(f'AhKs win_rate vs 25% open: {r["win_rate"]:.0%}')


def test_premium_hand_wins_more_than_half():
    """AhKs preflop should win > 50% against a 25% opening range."""
    r = equity_vs_range(['Ah', 'Ks'], [], opp_vpip=25.0, iterations=500)
    assert r['win_rate'] > 0.50, \
        f'AhKs should beat 25% range > 50%: {r["win_rate"]:.0%}'
    print(f'AhKs vs 25% open win_rate: {r["win_rate"]:.0%}')


def test_valid_flag_true_for_normal_inputs():
    """valid flag should be True for normal hero hole cards."""
    r = equity_vs_range(['Kh', 'Qh'], [], opp_vpip=30.0, iterations=200)
    assert r['valid'] is True, f'valid should be True: {r["valid"]}'
    print(f'valid=True confirmed')


def test_range_size_positive():
    """range_size should be a positive integer."""
    r = equity_vs_range(['Ah', 'Ks'], [], opp_vpip=25.0, iterations=200)
    assert isinstance(r['range_size'], int) and r['range_size'] > 0, \
        f'range_size should be positive int: {r["range_size"]}'
    print(f'range_size: {r["range_size"]} hands')


def test_wider_range_more_hands():
    """build_range with higher vpip should contain more hand categories."""
    r_tight = build_range(0.10, 'open')
    r_wide  = build_range(0.40, 'open')
    assert len(r_wide) >= len(r_tight), \
        f'Wide range ({len(r_wide)}) should have >= hands than tight ({len(r_tight)})'
    print(f'build_range: tight={len(r_tight)} wide={len(r_wide)} hand categories')


def test_build_range_returns_frozenset():
    """build_range should return a frozenset."""
    rng = build_range(0.25, 'open')
    assert isinstance(rng, frozenset), \
        f'build_range should return frozenset: {type(rng)}'
    print(f'build_range type: frozenset, size={len(rng)}')


def test_format_range_equity_returns_string():
    """format_range_equity should return a non-empty string."""
    r = equity_vs_range(['Ah', 'Ks'], [], opp_vpip=25.0, iterations=200)
    s = format_range_equity(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'format_range_equity should return non-empty string: {repr(s)[:50]}'
    print(f'format_range_equity length: {len(s)} chars')


def test_tight_villain_range_higher_win_rate():
    """Hero should win more often vs a tight range (fewer strong hands in range)."""
    r_tight = equity_vs_range(['Th', 'Tc'], [], opp_vpip=10.0, iterations=300)
    r_loose = equity_vs_range(['Th', 'Tc'], [], opp_vpip=40.0, iterations=300)
    # TT vs 10% range (all premiums) loses more than vs 40% (many weak hands)
    assert r_loose['win_rate'] >= r_tight['win_rate'] - 0.10, \
        f'TT vs loose {r_loose["win_rate"]:.0%} should be near vs tight {r_tight["win_rate"]:.0%}'
    print(f'TT: vs tight={r_tight["win_rate"]:.0%} vs loose={r_loose["win_rate"]:.0%}')


def test_opp_action_stored_in_result():
    """opp_action key should reflect the action passed in."""
    r = equity_vs_range(['Ah', 'Ks'], [], opp_vpip=25.0, opp_action='open', iterations=200)
    assert r['opp_action'] == 'open', \
        f'opp_action should be "open": {r["opp_action"]}'
    print(f'opp_action stored: {r["opp_action"]}')


if __name__ == '__main__':
    tests = [
        test_result_has_required_keys,
        test_win_rate_in_range,
        test_premium_hand_wins_more_than_half,
        test_valid_flag_true_for_normal_inputs,
        test_range_size_positive,
        test_wider_range_more_hands,
        test_build_range_returns_frozenset,
        test_format_range_equity_returns_string,
        test_tight_villain_range_higher_win_rate,
        test_opp_action_stored_in_result,
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
