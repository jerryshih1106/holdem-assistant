"""Tests for poker/winrate_stats.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.winrate_stats import calculate_winrate_stats, winrate_stats_summary


def test_zero_hands_returns_safe_result():
    """Zero hands → safe result without division by zero."""
    r = calculate_winrate_stats(hands=0, ev_per_100=0.0)
    assert r.hands == 0
    assert r.reliability == 'very_low'
    print(f'Zero hands: {r.summary_zh}')


def test_small_sample_is_uncertain():
    """Small sample (50 hands) → very uncertain, CI is huge."""
    r = calculate_winrate_stats(hands=50, ev_per_100=-30.0)
    assert r.reliability in ('very_low', 'low'), f'Small sample should be low reliability: {r.reliability}'
    assert r.ci_half_width > 30.0, f'CI half-width should be >30 for small sample: {r.ci_half_width}'
    assert r.verdict == 'uncertain', f'Small sample should be uncertain: {r.verdict}'
    print(f'50 hands, -30 BB/100: CI=[{r.ci_lower:.0f},{r.ci_upper:.0f}]  verdict={r.verdict}')


def test_normal_downswing_is_normal_variance():
    """Common downswing (-20 BB/100 over 200 hands) should be within normal variance."""
    r = calculate_winrate_stats(hands=200, ev_per_100=-20.0)
    assert r.in_normal_variance, \
        f'-20 BB/100 over 200 hands should be normal variance: CI=[{r.ci_lower:.0f},{r.ci_upper:.0f}]'
    assert not r.is_clearly_losing, 'Small sample downswing should not be clearly losing'
    print(f'Downswing check: CI=[{r.ci_lower:.0f},{r.ci_upper:.0f}]  normal={r.in_normal_variance}')


def test_large_sample_clearly_winning():
    """Very strong winrate over large sample → clearly winning.
    Note: 6-max NLHE σ≈82 BB/100, so need ~20k hands at +20BB/100 for CI lower > +5.
    """
    r = calculate_winrate_stats(hands=20000, ev_per_100=20.0)
    assert r.is_clearly_winning, \
        f'+20 BB/100 over 20000 hands should be clearly winning: CI=[{r.ci_lower:.0f},{r.ci_upper:.0f}]'
    assert r.verdict == 'winning'
    print(f'20000 hands +20BB/100: CI=[{r.ci_lower:.0f},{r.ci_upper:.0f}]  verdict={r.verdict}')


def test_large_sample_clearly_losing():
    """Consistent losing rate over large sample → clearly losing.
    Note: need ~15k hands at -20BB/100 for CI upper < -5.
    """
    r = calculate_winrate_stats(hands=15000, ev_per_100=-20.0)
    assert r.is_clearly_losing, \
        f'-20 BB/100 over 15000 hands should be clearly losing: CI=[{r.ci_lower:.0f},{r.ci_upper:.0f}]'
    assert r.verdict == 'losing'
    print(f'15000 hands -20BB/100: CI=[{r.ci_lower:.0f},{r.ci_upper:.0f}]  verdict={r.verdict}')


def test_ci_narrows_with_more_hands():
    """More hands → narrower confidence interval."""
    r_small = calculate_winrate_stats(hands=100,  ev_per_100=5.0)
    r_large = calculate_winrate_stats(hands=5000, ev_per_100=5.0)
    assert r_small.ci_half_width > r_large.ci_half_width, \
        f'More hands should narrow CI: {r_small.ci_half_width:.1f} vs {r_large.ci_half_width:.1f}'
    print(f'100 hands CI half: ±{r_small.ci_half_width:.0f}  5000 hands: ±{r_large.ci_half_width:.1f}')


def test_reliability_improves_with_hands():
    """More hands → higher reliability."""
    r_50   = calculate_winrate_stats(hands=50,   ev_per_100=0)
    r_500  = calculate_winrate_stats(hands=500,  ev_per_100=0)
    r_3000 = calculate_winrate_stats(hands=3000, ev_per_100=0)
    order = {'very_low': 0, 'low': 1, 'medium': 2, 'high': 3, 'very_high': 4}
    assert order[r_50.reliability] <= order[r_500.reliability], 'Reliability should increase'
    assert order[r_500.reliability] <= order[r_3000.reliability], 'Reliability should increase more'
    print(f'50h: {r_50.reliability}  500h: {r_500.reliability}  3000h: {r_3000.reliability}')


def test_ci_is_symmetric():
    """Confidence interval should be symmetric around the observed winrate."""
    r = calculate_winrate_stats(hands=500, ev_per_100=8.0)
    actual_upper = r.ev_per_100 + r.ci_half_width
    actual_lower = r.ev_per_100 - r.ci_half_width
    assert abs(r.ci_upper - actual_upper) < 0.2, f'Upper CI mismatch: {r.ci_upper} vs {actual_upper}'
    assert abs(r.ci_lower - actual_lower) < 0.2, f'Lower CI mismatch: {r.ci_lower} vs {actual_lower}'
    print(f'CI symmetric: {r.ev_per_100}±{r.ci_half_width}  [{r.ci_lower:.0f},{r.ci_upper:.0f}]')


def test_hu_wider_std_than_6max():
    """HU has higher standard deviation than 6-max."""
    r_hu   = calculate_winrate_stats(hands=500, ev_per_100=10.0, game_type='hu')
    r_6max = calculate_winrate_stats(hands=500, ev_per_100=10.0, game_type='6max')
    assert r_hu.ci_half_width > r_6max.ci_half_width, \
        f'HU CI should be wider: {r_hu.ci_half_width:.1f} vs {r_6max.ci_half_width:.1f}'
    print(f'HU CI: ±{r_hu.ci_half_width:.0f}  6-max CI: ±{r_6max.ci_half_width:.0f}')


def test_summary_format():
    """Summary should contain [勝率] and be ≤80 chars."""
    r = calculate_winrate_stats(hands=300, ev_per_100=5.5)
    s = winrate_stats_summary(r)
    assert '[勝率]' in s, f'Missing [勝率]: {s}'
    assert len(s) <= 80, f'Too long ({len(s)}): {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_total_ev_consistent():
    """Total EV should be consistent with per-100 and hands."""
    r = calculate_winrate_stats(hands=200, ev_per_100=10.0)
    expected = 200 * 10.0 / 100.0
    assert abs(r.total_ev_bb - expected) < 0.1, \
        f'Total EV mismatch: {r.total_ev_bb} vs {expected}'
    print(f'Total EV: {r.total_ev_bb:.1f}BB ({r.hands} hands at {r.ev_per_100:.1f}BB/100)')


if __name__ == '__main__':
    tests = [
        test_zero_hands_returns_safe_result,
        test_small_sample_is_uncertain,
        test_normal_downswing_is_normal_variance,
        test_large_sample_clearly_winning,
        test_large_sample_clearly_losing,
        test_ci_narrows_with_more_hands,
        test_reliability_improves_with_hands,
        test_ci_is_symmetric,
        test_hu_wider_std_than_6max,
        test_summary_format,
        test_total_ev_consistent,
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
