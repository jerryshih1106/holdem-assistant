"""Tests for steal_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.steal_frequency_guide import (
    analyze_steal_frequency, StealFrequencyResult, sfg_one_liner,
    _fold_category, _stack_depth_category, _optimal_steal_freq, _steal_status,
    BASELINE_STEAL_FREQ, VILLAIN_BB_STEAL_MODIFIER, BB_FOLD_TO_STEAL_ADJUSTMENT,
)


def _sfg(**kw):
    defaults = dict(
        position='btn', bb_fold_to_steal=0.60, sb_fold_to_steal=0.55,
        stack_bb=100.0, villain_bb_type='reg', actual_steal_freq=0.50,
    )
    defaults.update(kw)
    return analyze_steal_frequency(**defaults)


def test_returns_result():
    assert isinstance(_sfg(), StealFrequencyResult)


def test_btn_baseline_higher_than_co():
    assert BASELINE_STEAL_FREQ['btn'] > BASELINE_STEAL_FREQ['co']


def test_sb_baseline_higher_than_hj():
    assert BASELINE_STEAL_FREQ['sb'] > BASELINE_STEAL_FREQ['hj']


def test_high_f2s_increases_optimal():
    high = _optimal_steal_freq('btn', 0.80, 0.70, 100.0, 'reg')
    low  = _optimal_steal_freq('btn', 0.30, 0.30, 100.0, 'reg')
    assert high > low


def test_nit_bb_increases_freq():
    nit  = _optimal_steal_freq('btn', 0.60, 0.55, 100.0, 'nit')
    lag  = _optimal_steal_freq('btn', 0.60, 0.55, 100.0, 'lag')
    assert nit > lag


def test_short_stack_reduces_freq():
    deep  = _optimal_steal_freq('btn', 0.60, 0.55, 100.0, 'reg')
    short = _optimal_steal_freq('btn', 0.60, 0.55, 15.0, 'reg')
    assert deep > short


def test_fold_category_very_high():
    assert _fold_category(0.80) == 'very_high'


def test_fold_category_very_low():
    assert _fold_category(0.25) == 'very_low'


def test_stack_deep():
    assert _stack_depth_category(100.0) == 'deep'


def test_stack_short():
    assert _stack_depth_category(15.0) == 'short'


def test_over_stealing_detected():
    status = _steal_status(0.80, 0.50)
    assert 'OVER' in status


def test_under_stealing_detected():
    status = _steal_status(0.20, 0.55)
    assert 'UNDER' in status


def test_ok_status():
    status = _steal_status(0.50, 0.50)
    assert status == 'STEAL_FREQUENCY_OK'


def test_optimal_capped():
    r = _sfg(bb_fold_to_steal=1.0, villain_bb_type='nit')
    assert r.optimal_steal_freq <= 0.75


def test_sizing_stored():
    r = _sfg(position='btn')
    assert 2.0 <= r.recommended_sizing_bb <= 4.0


def test_tips_populated():
    r = _sfg()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _sfg()
    line = sfg_one_liner(r)
    assert '[STEAL' in line and 'optimal=' in line


def test_nit_tip_present():
    r = _sfg(villain_bb_type='nit')
    assert any('NIT' in t for t in r.tips)


def test_lag_tip_present():
    r = _sfg(villain_bb_type='lag')
    assert any('LAG' in t for t in r.tips)


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
