"""Tests for check_call_line_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.check_call_line_guide import (
    analyze_check_call_line, CheckCallLineResult, ccl_one_liner,
    _mdf, _streets_to_call, _transition_trigger,
    BASE_CHECK_CALL_STREETS, HAND_SDV,
)


def _ccl(**kw):
    defaults = dict(
        hand_category='top_pair_gk', villain_type='reg', street='flop',
        spr=5.0, pot_bb=20.0, n_streets_called=0, villain_bet_frac=None,
    )
    defaults.update(kw)
    return analyze_check_call_line(**defaults)


def test_returns_result():
    assert isinstance(_ccl(), CheckCallLineResult)


def test_mdf_halfpot():
    assert abs(_mdf(0.50) - (1.0/1.5)) < 0.01


def test_mdf_fullpot():
    assert abs(_mdf(1.00) - 0.50) < 0.01


def test_nuts_calls_3_streets():
    n = _streets_to_call('nuts', 'reg', 5.0)
    assert n == 3


def test_air_calls_0_streets():
    n = _streets_to_call('air', 'reg', 5.0)
    assert n == 0


def test_lag_adds_street():
    lag = _streets_to_call('middle_pair', 'lag', 5.0)
    reg = _streets_to_call('middle_pair', 'reg', 5.0)
    assert lag >= reg


def test_nit_reduces_street():
    nit = _streets_to_call('top_pair_gk', 'nit', 5.0)
    reg = _streets_to_call('top_pair_gk', 'reg', 5.0)
    assert nit <= reg


def test_low_spr_reduces_to_1():
    n = _streets_to_call('top_pair_gk', 'reg', 1.5)
    assert n <= 1


def test_draw_river_transition():
    t = _transition_trigger('flush_draw', 'river', 'reg', 1)
    assert t == 'SWITCH_TO_CHECK_FOLD_MISS'


def test_strong_hand_long_check_transition():
    t = _transition_trigger('nuts', 'turn', 'reg', 2)
    assert t == 'CONSIDER_LEAD_OR_RAISE'


def test_mdf_stored():
    r = _ccl()
    assert 0 < r.mdf < 1


def test_sdv_stored():
    r = _ccl()
    assert 0 < r.sdv < 1


def test_streets_in_range():
    r = _ccl()
    assert 0 <= r.streets_to_call <= 3


def test_tips_populated():
    r = _ccl()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _ccl()
    line = ccl_one_liner(r)
    assert '[CCL' in line and 'MDF=' in line


def test_lag_tip_present():
    r = _ccl(villain_type='lag')
    assert any('LAG' in t for t in r.tips)


def test_nit_tip_present():
    r = _ccl(villain_type='nit')
    assert any('NIT' in t for t in r.tips)


def test_sdv_table_valid():
    for h, s in HAND_SDV.items():
        assert 0 <= s <= 1


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
