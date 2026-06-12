"""Tests for session_leak_prioritizer.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.session_leak_prioritizer import (
    prioritize_leaks, SessionLeakResult, slp_one_liner,
    _compute_leak_ev_cost, _deviation_direction, _fix_advice,
    GTO_BASELINE, EV_COST_PER_PCT,
)


def _slp(**kw):
    defaults = dict(
        vpip=0.28,
        pfr=0.18,
        three_bet=0.08,
        fold_to_3bet=0.58,
        cbet_flop=0.62,
        fold_to_cbet=0.60,
        turn_cbet=0.45,
        river_cbet=0.40,
        wtsd=0.28,
        wsd=0.52,
        hands_played=5000,
    )
    defaults.update(kw)
    return prioritize_leaks(**defaults)


def test_returns_session_leak_result():
    r = _slp()
    assert isinstance(r, SessionLeakResult)


def test_ev_cost_zero_within_3pct():
    cost = _compute_leak_ev_cost('wtsd', 0.28, 0.28)
    assert cost == 0.0


def test_ev_cost_positive_outside_3pct():
    cost = _compute_leak_ev_cost('wtsd', 0.40, 0.28)  # 12% excess → cost > 0
    assert cost > 0


def test_ev_cost_increases_with_deviation():
    small = _compute_leak_ev_cost('fold_to_3bet', 0.60, 0.55)
    large = _compute_leak_ev_cost('fold_to_3bet', 0.75, 0.55)
    assert large > small


def test_deviation_direction_fold_stats():
    assert _deviation_direction('fold_to_3bet', 0.70, 0.55) == 'over_folding'
    assert _deviation_direction('fold_to_3bet', 0.40, 0.55) == 'under_folding'


def test_deviation_direction_vpip():
    assert _deviation_direction('vpip', 0.40, 0.22) == 'too_loose'
    assert _deviation_direction('vpip', 0.15, 0.22) == 'too_tight'


def test_deviation_direction_cbet():
    assert _deviation_direction('cbet_flop', 0.70, 0.58) == 'over_betting'
    assert _deviation_direction('cbet_flop', 0.40, 0.58) == 'under_betting'


def test_leaks_sorted_by_ev_cost():
    r = _slp(wtsd=0.45, fold_to_3bet=0.56)   # wtsd massively off, fold ok
    if len(r.leaks) >= 2:
        assert r.leaks[0].ev_cost_bb_100 >= r.leaks[1].ev_cost_bb_100


def test_high_wtsd_is_top_leak():
    r = _slp(wtsd=0.45)   # WTSD 45% vs 28% baseline = 17% excess
    top_names = [l.stat_name for l in r.leaks[:2]]
    assert 'wtsd' in top_names


def test_normal_stats_few_leaks():
    r = _slp(
        vpip=0.22, pfr=0.17, three_bet=0.08,
        fold_to_3bet=0.55, cbet_flop=0.58,
        fold_to_cbet=0.50, turn_cbet=0.48,
        river_cbet=0.38, wtsd=0.28, wsd=0.52,
    )
    assert len(r.leaks) == 0


def test_total_ev_cost_sum_of_leaks():
    r = _slp()
    expected = round(sum(l.ev_cost_bb_100 for l in r.leaks), 2)
    assert abs(r.total_ev_cost_bb_100 - expected) < 0.01


def test_priority_ascending():
    r = _slp(wtsd=0.40, fold_to_3bet=0.72, cbet_flop=0.30)
    for i, lk in enumerate(r.leaks):
        assert lk.priority == i + 1


def test_reliability_high_large_sample():
    r = _slp(hands_played=12000)
    assert r.reliability == 'high'


def test_reliability_medium():
    r = _slp(hands_played=4000)
    assert r.reliability == 'medium'


def test_reliability_low_small_sample():
    r = _slp(hands_played=1000)
    assert r.reliability == 'low'


def test_top_leak_stored():
    r = _slp()
    assert isinstance(r.top_leak, str) and len(r.top_leak) > 0


def test_leak_entry_has_fix_advice():
    r = _slp(wtsd=0.40)
    for lk in r.leaks:
        assert len(lk.fix_advice) > 0


def test_tips_populated():
    r = _slp(wtsd=0.40, fold_to_3bet=0.72)
    assert len(r.tips) >= 2


def test_low_sample_tip():
    r = _slp(hands_played=500)
    tips_lower = ' '.join(r.tips).lower()
    assert 'sample' in tips_lower or 'low' in tips_lower or 'reliable' in tips_lower.replace('reliability', 'reliable')


def test_no_leaks_tip():
    r = _slp(
        vpip=0.22, pfr=0.17, three_bet=0.08,
        fold_to_3bet=0.55, cbet_flop=0.58,
        fold_to_cbet=0.50, turn_cbet=0.48,
        river_cbet=0.38, wtsd=0.28, wsd=0.52,
    )
    tips_lower = ' '.join(r.tips).lower()
    assert 'no' in tips_lower or 'leak' in tips_lower


def test_one_liner_format():
    r = _slp()
    line = slp_one_liner(r)
    assert '[SLP' in line
    assert 'top=' in line
    assert 'total=' in line
    assert 'leaks=' in line


def test_one_liner_has_reliability():
    r = _slp()
    line = slp_one_liner(r)
    assert r.reliability.upper() in line


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
