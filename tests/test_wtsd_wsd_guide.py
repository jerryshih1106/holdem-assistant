"""Tests for wtsd_wsd_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.wtsd_wsd_guide import (
    analyze_wtsd_wsd, WtsdWsdResult, wtsd_wsd_one_liner,
    _wtsd_category, _wsd_category, _combined_profile, _exploit_advice,
)

def _ww(**kw):
    defaults = dict(wtsd=0.26, wsd=0.50)
    defaults.update(kw)
    return analyze_wtsd_wsd(**defaults)

def test_returns_result():
    assert isinstance(_ww(), WtsdWsdResult)

def test_wtsd_low():
    assert _wtsd_category(0.15) == 'low'

def test_wtsd_standard():
    assert _wtsd_category(0.26) == 'standard'

def test_wtsd_high():
    assert _wtsd_category(0.35) == 'high'

def test_wsd_losing():
    assert _wsd_category(0.40) == 'losing'

def test_wsd_neutral():
    assert _wsd_category(0.50) == 'neutral'

def test_wsd_winning():
    assert _wsd_category(0.55) == 'winning'

def test_calling_station_profile():
    p = _combined_profile(0.35, 0.42)
    assert p == 'calling_station'

def test_nit_profile():
    p = _combined_profile(0.18, 0.55)
    assert p == 'nit'

def test_exploit_calling_station_no_bluff():
    a = _exploit_advice('high', 'losing')
    assert 'bluff' in a.lower()

def test_exploit_nit_bluff_ok():
    a = _exploit_advice('low', 'winning')
    assert '3-bet' in a or 'fold' in a.lower() or 'bluff' in a.lower()

def test_tips_at_least_two():
    r = _ww()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _ww()
    s = wtsd_wsd_one_liner(r)
    assert '[WTSD' in s
    assert 'profile=' in s

def test_verdict_equals_profile():
    r = _ww()
    assert r.verdict == r.combined_profile

def test_high_wtsd_low_wsd_is_calling_station():
    r = _ww(wtsd=0.40, wsd=0.40)
    assert r.combined_profile == 'calling_station'

def test_stored_values():
    r = _ww(wtsd=0.28, wsd=0.53)
    assert r.wtsd == 0.28
    assert r.wsd == 0.53

def test_reasoning_contains_profile():
    r = _ww()
    assert r.combined_profile in r.reasoning

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
