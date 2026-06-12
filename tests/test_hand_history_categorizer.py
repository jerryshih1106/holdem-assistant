"""Tests for hand_history_categorizer.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hand_history_categorizer import (
    analyze_hand_history, HandHistoryReport, HandCategoryStats, hhc_one_liner,
    _detect_leak, _bb_per_100, EXPECTED_FOLD_RATE, EXPECTED_WIN_RATE,
)


def _hhc(**kw):
    defaults = dict(hand_data=None)
    defaults.update(kw)
    return analyze_hand_history(**defaults)


def test_returns_hand_history_report():
    r = _hhc()
    assert isinstance(r, HandHistoryReport)


def test_default_data_has_stats():
    r = _hhc()
    assert len(r.hand_stats) > 0


def test_total_hands_positive():
    r = _hhc()
    assert r.total_hands > 0


def test_total_bb_net_is_float():
    r = _hhc()
    assert isinstance(r.total_bb_net, float)


def test_best_category_is_string():
    r = _hhc()
    assert isinstance(r.best_category, str)


def test_over_folding_leak_detected():
    data = {
        'top_pair': {'played': 30, 'won': 10, 'lost': 5, 'folded': 20, 'bb_net': -5.0}
    }
    leak = _detect_leak('top_pair', 30, 10, 20, -5.0)
    assert leak == 'over_folding'


def test_not_extracting_value_leak():
    # -45 over 20 hands = -2.25 per hand, below the -2.0 threshold
    leak = _detect_leak('set', 20, 15, 0, -45.0)
    assert leak == 'not_extracting_value'


def test_insufficient_sample():
    leak = _detect_leak('top_pair', 3, 2, 0, 5.0)
    assert leak == 'insufficient_sample'


def test_no_leak_good_play():
    leak = _detect_leak('top_pair', 20, 14, 5, 30.0)
    assert leak == 'no_leak'


def test_bb_per_100_formula():
    bb100 = _bb_per_100(50.0, 100)
    assert abs(bb100 - 50.0) < 0.1


def test_bb_per_100_zero_hands():
    bb100 = _bb_per_100(50.0, 0)
    assert bb100 == 0.0


def test_custom_hand_data():
    data = {
        'flush': {'played': 15, 'won': 13, 'lost': 1, 'folded': 1, 'bb_net': 60.0},
        'air':   {'played': 25, 'won': 5, 'lost': 8, 'folded': 12, 'bb_net': -20.0},
    }
    r = analyze_hand_history(hand_data=data)
    assert 'flush' in r.hand_stats
    assert 'air' in r.hand_stats


def test_best_category_is_best_bb():
    data = {
        'set':    {'played': 10, 'won': 9, 'lost': 1, 'folded': 0, 'bb_net': 90.0},
        'air':    {'played': 15, 'won': 3, 'lost': 5, 'folded': 7, 'bb_net': -25.0},
    }
    r = analyze_hand_history(hand_data=data)
    assert r.best_category == 'set'


def test_win_rate_computed():
    r = _hhc()
    for cat, s in r.hand_stats.items():
        assert 0.0 <= s.win_rate <= 1.0


def test_fold_rate_computed():
    r = _hhc()
    for cat, s in r.hand_stats.items():
        assert 0.0 <= s.fold_rate <= 1.0


def test_bb_per_100_stored():
    r = _hhc()
    for cat, s in r.hand_stats.items():
        assert isinstance(s.bb_per_100_hands, float)


def test_expected_fold_rate_stored_in_stats():
    r = _hhc()
    for cat, s in r.hand_stats.items():
        if cat in EXPECTED_FOLD_RATE:
            assert s.expected_fold_rate == EXPECTED_FOLD_RATE[cat]


def test_tips_populated():
    r = _hhc()
    assert len(r.tips) >= 1


def test_one_liner_format():
    r = _hhc()
    line = hhc_one_liner(r)
    assert '[HHC' in line
    assert 'net=' in line
    assert 'leak=' in line


def test_over_calling_detected():
    leak = _detect_leak('top_pair', 20, 5, 2, -20.0)
    assert leak in ('over_calling', 'poor_win_rate')


def test_nuts_low_fold_rate():
    expected = EXPECTED_FOLD_RATE.get('nuts', 0.02)
    assert expected <= 0.05


def test_air_high_fold_rate():
    expected = EXPECTED_FOLD_RATE.get('air', 0.68)
    assert expected >= 0.50


def test_verdict_contains_hands():
    r = _hhc()
    assert 'hands' in r.verdict.lower() or str(r.total_hands) in r.verdict


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
