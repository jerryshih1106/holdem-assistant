"""Tests for check_raise_stat_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.check_raise_stat_guide import (
    analyze_check_raise_stat, CheckRaiseStatResult, check_raise_stat_one_liner,
    _cr_profile, _exploit_strategy, _board_cr_adjustment,
)

def _crs(**kw):
    defaults = dict(cr_pct=0.05, board_texture='dry')
    defaults.update(kw)
    return analyze_check_raise_stat(**defaults)

def test_returns_result():
    assert isinstance(_crs(), CheckRaiseStatResult)

def test_profile_nit():
    assert _cr_profile(0.01) == 'nit'

def test_profile_standard():
    assert _cr_profile(0.05) == 'standard'

def test_profile_trappy():
    assert _cr_profile(0.10) == 'trappy'

def test_profile_aggressive():
    assert _cr_profile(0.15) == 'aggressive'

def test_exploit_nit():
    assert _exploit_strategy('nit').startswith('Bet')

def test_exploit_aggressive_value_only():
    s = _exploit_strategy('aggressive')
    assert 'value' in s.lower()

def test_board_adjustment_wet():
    a = _board_cr_adjustment('wet')
    assert 'wet' in a.lower() or 'draw' in a.lower()

def test_board_adjustment_dry():
    a = _board_cr_adjustment('dry')
    assert 'dry' in a.lower() or 'made' in a.lower() or 'strong' in a.lower()

def test_board_adjustment_unknown():
    a = _board_cr_adjustment('unknown_texture')
    assert len(a) > 0

def test_verdict_equals_exploit():
    r = _crs()
    assert r.verdict == r.exploit

def test_tips_at_least_two():
    r = _crs()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _crs()
    s = check_raise_stat_one_liner(r)
    assert '[CRS' in s
    assert 'profile=' in s
    assert 'exploit=' in s

def test_stored_cr_pct():
    r = _crs(cr_pct=0.09)
    assert r.cr_pct == 0.09

def test_high_cr_tip():
    r = _crs(cr_pct=0.13)
    hi_tips = [t for t in r.tips if 'high' in t.lower() or 'check behind' in t.lower()]
    assert len(hi_tips) >= 1

def test_reasoning_contains_profile():
    r = _crs()
    assert r.cr_profile in r.reasoning

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
