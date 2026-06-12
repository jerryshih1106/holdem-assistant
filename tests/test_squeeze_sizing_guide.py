"""Tests for squeeze_sizing_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.squeeze_sizing_guide import (
    analyze_squeeze_sizing, SqueezeSizingResult, ssq_one_liner,
    _squeeze_size_bb, _spr_if_called, _squeeze_action,
    BASE_SQUEEZE_OPEN_MULTIPLIER, CALLER_DEAD_MONEY_BB, JAM_THRESHOLD_RATIO,
)


def _ssq(**kw):
    defaults = dict(open_bb=3.0, n_callers=1, position='ip', effective_stack_bb=100.0, villain_type='reg')
    defaults.update(kw)
    return analyze_squeeze_sizing(**defaults)


def test_returns_result():
    assert isinstance(_ssq(), SqueezeSizingResult)


def test_more_callers_bigger_squeeze():
    one = _squeeze_size_bb(3.0, 1, 'ip', 100.0, 'reg')
    two = _squeeze_size_bb(3.0, 2, 'ip', 100.0, 'reg')
    assert two > one


def test_oop_bigger_than_ip():
    ip  = _squeeze_size_bb(3.0, 1, 'ip',  100.0, 'reg')
    oop = _squeeze_size_bb(3.0, 1, 'oop', 100.0, 'reg')
    assert oop > ip


def test_larger_open_bigger_squeeze():
    small = _squeeze_size_bb(2.0, 1, 'ip', 100.0, 'reg')
    large = _squeeze_size_bb(4.0, 1, 'ip', 100.0, 'reg')
    assert large > small


def test_nit_bigger_squeeze():
    nit = _squeeze_size_bb(3.0, 1, 'ip', 100.0, 'nit')
    reg = _squeeze_size_bb(3.0, 1, 'ip', 100.0, 'reg')
    assert nit > reg


def test_spr_positive():
    spr = _spr_if_called(10.0, 8.0, 100.0)
    assert spr > 0


def test_jam_threshold_detected():
    action = _squeeze_action(40.0, 100.0)
    assert action == 'JAM_PREFERRED'


def test_standard_squeeze():
    action = _squeeze_action(10.0, 100.0)
    assert action == 'STANDARD_SQUEEZE'


def test_squeeze_capped_at_40pct_stack():
    r = _ssq(n_callers=5, effective_stack_bb=50.0)
    assert r.optimal_squeeze_bb <= 50.0 * 0.40


def test_pot_before_stored():
    r = _ssq(open_bb=3.0, n_callers=1)
    assert r.pot_before_squeeze > 0


def test_jam_threshold_bb_stored():
    r = _ssq(effective_stack_bb=100.0)
    assert abs(r.jam_threshold_bb - 100.0 * JAM_THRESHOLD_RATIO) < 1.0


def test_tips_populated():
    r = _ssq()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _ssq()
    line = ssq_one_liner(r)
    assert '[SQ' in line and 'squeeze=' in line


def test_two_caller_tip():
    r = _ssq(n_callers=2)
    assert any('caller' in t.lower() for t in r.tips)


def test_nit_tip_present():
    r = _ssq(villain_type='nit')
    assert any('NIT' in t or 'nit' in t.lower() for t in r.tips)


def test_lag_tip_present():
    r = _ssq(villain_type='lag')
    assert any('LAG' in t or '4-bet' in t.lower() for t in r.tips)


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
