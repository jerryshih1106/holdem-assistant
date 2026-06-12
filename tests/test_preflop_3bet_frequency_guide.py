"""Tests for preflop_3bet_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_3bet_frequency_guide import (
    analyze_preflop_3bet_frequency, Preflop3BetFrequencyResult, p3f_one_liner,
    _fold_to_3bet_category, _optimal_3bet_freq, _3bet_calibration_status,
    BASELINE_3BET_FREQ_VS_OPEN_POSITION, VILLAIN_TYPE_3BET_MODIFIER,
    FOLD_TO_3BET_ADJUSTMENT, VALUE_3BET_COMBOS_APPROX,
)


def _p3f(**kw):
    defaults = dict(
        open_position='btn', villain_type='reg', fold_to_3bet=0.57,
        hero_position='ip', actual_3bet_freq=0.10,
    )
    defaults.update(kw)
    return analyze_preflop_3bet_frequency(**defaults)


def test_returns_result():
    assert isinstance(_p3f(), Preflop3BetFrequencyResult)


def test_btn_baseline_higher_than_utg():
    btn = BASELINE_3BET_FREQ_VS_OPEN_POSITION['btn']
    utg = BASELINE_3BET_FREQ_VS_OPEN_POSITION['utg']
    assert btn > utg


def test_high_f2t_increases_freq():
    high_f2t = _optimal_3bet_freq('btn', 'reg', 0.80, 'ip')
    low_f2t  = _optimal_3bet_freq('btn', 'reg', 0.35, 'ip')
    assert high_f2t > low_f2t


def test_ip_higher_than_oop():
    ip  = _optimal_3bet_freq('btn', 'reg', 0.57, 'ip')
    oop = _optimal_3bet_freq('btn', 'reg', 0.57, 'oop')
    assert ip > oop


def test_nit_modifier_negative():
    assert VILLAIN_TYPE_3BET_MODIFIER['nit'] < 0


def test_fish_modifier_positive():
    assert VILLAIN_TYPE_3BET_MODIFIER['fish'] > 0


def test_fold_category_very_high():
    assert _fold_to_3bet_category(0.80) == 'very_high'


def test_fold_category_standard():
    assert _fold_to_3bet_category(0.57) == 'standard'


def test_fold_category_very_low():
    assert _fold_to_3bet_category(0.30) == 'very_low'


def test_over_3betting_detected():
    status = _3bet_calibration_status(0.25, 0.10)
    assert 'OVER' in status


def test_under_3betting_detected():
    status = _3bet_calibration_status(0.02, 0.13)
    assert 'UNDER' in status


def test_ok_status():
    status = _3bet_calibration_status(0.10, 0.10)
    assert status == '3BET_FREQUENCY_OK'


def test_optimal_capped_at_max():
    r = _p3f(fold_to_3bet=1.0, hero_position='ip', open_position='btn')
    assert r.optimal_3bet_freq <= 0.35


def test_optimal_floored_at_min():
    r = _p3f(fold_to_3bet=0.0, hero_position='oop', open_position='utg')
    assert r.optimal_3bet_freq >= 0.01


def test_bluff_combos_nonnegative():
    r = _p3f()
    assert r.bluff_combos_needed >= 0


def test_value_combos_stored():
    r = _p3f()
    assert r.value_combos_approx == VALUE_3BET_COMBOS_APPROX


def test_tips_populated():
    r = _p3f()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _p3f()
    line = p3f_one_liner(r)
    assert '[3BF' in line and 'optimal=' in line


def test_lag_tip_present():
    r = _p3f(villain_type='lag')
    assert any('LAG' in t for t in r.tips)


def test_nit_tip_present():
    r = _p3f(villain_type='nit')
    assert any('NIT' in t for t in r.tips)


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
