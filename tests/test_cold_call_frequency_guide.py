"""Tests for cold_call_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cold_call_frequency_guide import (
    analyze_cold_call_frequency, ColdCallFrequencyResult, ccf_one_liner,
    _stack_depth_cat, _optimal_cold_call_freq, _flat_or_3bet, _cold_call_status,
    BASELINE_COLD_CALL_FREQ, VILLAIN_OPEN_COLD_CALL_MODIFIER,
    THREE_BET_PREFERENCE_THRESHOLD, FLAT_PREFERENCE_THRESHOLD,
)


def _ccf(**kw):
    defaults = dict(
        position='btn', villain_type='reg', squeezers_behind=0,
        stack_bb=100.0, hand_sdv=0.50, actual_cold_call_freq=0.15,
    )
    defaults.update(kw)
    return analyze_cold_call_frequency(**defaults)


def test_returns_result():
    assert isinstance(_ccf(), ColdCallFrequencyResult)


def test_btn_baseline_higher_than_utg():
    assert BASELINE_COLD_CALL_FREQ['btn'] > BASELINE_COLD_CALL_FREQ['utg']


def test_sb_baseline_lowest_positions():
    assert BASELINE_COLD_CALL_FREQ['sb'] <= BASELINE_COLD_CALL_FREQ['utg']


def test_fish_increases_freq():
    fish = _optimal_cold_call_freq('btn', 'fish', 0, 100.0)
    nit  = _optimal_cold_call_freq('btn', 'nit', 0, 100.0)
    assert fish > nit


def test_squeezers_reduce_freq():
    no_sq = _optimal_cold_call_freq('btn', 'reg', 0, 100.0)
    sq2   = _optimal_cold_call_freq('btn', 'reg', 2, 100.0)
    assert no_sq > sq2


def test_deep_stack_higher_than_short():
    deep  = _optimal_cold_call_freq('btn', 'reg', 0, 100.0)
    short = _optimal_cold_call_freq('btn', 'reg', 0, 15.0)
    assert deep > short


def test_flat_preferred_medium_sdv():
    assert _flat_or_3bet(0.45) == 'FLAT_PREFERRED'


def test_3bet_preferred_high_sdv():
    assert _flat_or_3bet(0.85) == '3BET_PREFERRED'


def test_fold_preferred_low_sdv():
    assert _flat_or_3bet(0.15) == 'FOLD_PREFERRED'


def test_mixed_mid_sdv():
    assert _flat_or_3bet(0.65) == 'FLAT_OR_3BET_MIXED'


def test_over_flatting_detected():
    status = _cold_call_status(0.25, 0.12)
    assert 'OVER' in status


def test_under_flatting_detected():
    status = _cold_call_status(0.05, 0.17)
    assert 'UNDER' in status


def test_ok_status():
    status = _cold_call_status(0.15, 0.15)
    assert status == 'COLD_CALL_FREQ_OK'


def test_optimal_capped():
    r = _ccf(villain_type='fish', squeezers_behind=0, stack_bb=200.0)
    assert r.optimal_cold_call_freq <= 0.30


def test_optimal_floored():
    r = _ccf(villain_type='nit', squeezers_behind=3, stack_bb=15.0)
    assert r.optimal_cold_call_freq >= 0.01


def test_squeeze_tip():
    r = _ccf(squeezers_behind=2)
    assert any('SQUEEZE' in t or 'squeeze' in t.lower() for t in r.tips)


def test_tips_populated():
    r = _ccf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _ccf()
    line = ccf_one_liner(r)
    assert '[CCF' in line and 'optimal=' in line


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
