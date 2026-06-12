"""Tests for vpip_pfr_ratio_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.vpip_pfr_ratio_guide import (
    analyze_vpip_pfr_ratio, VpipPfrRatioResult, vpip_pfr_ratio_one_liner,
    _classify_player_type, _pfr_vpip_ratio, _exploit_recommendation,
)

def _vpr(**kw):
    defaults = dict(vpip=0.24, pfr=0.18)
    defaults.update(kw)
    return analyze_vpip_pfr_ratio(**defaults)

def test_returns_result():
    assert isinstance(_vpr(), VpipPfrRatioResult)

def test_ratio_zero_vpip_safe():
    r = _pfr_vpip_ratio(0.0, 0.0)
    assert r == 0.0

def test_ratio_calculation():
    r = _pfr_vpip_ratio(0.18, 0.24)
    assert abs(r - 0.75) < 0.01

def test_classify_nit():
    t = _classify_player_type(0.12, 0.10)
    assert t == 'nit'

def test_classify_tag():
    t = _classify_player_type(0.22, 0.17)
    assert t == 'tag'

def test_classify_lag():
    t = _classify_player_type(0.35, 0.25)
    assert t == 'lag'

def test_classify_calling_station():
    t = _classify_player_type(0.50, 0.10)
    assert t == 'calling_station'

def test_classify_maniac():
    t = _classify_player_type(0.60, 0.55)
    assert t == 'maniac'

def test_exploit_nit_contains_fold():
    advice = _exploit_recommendation('nit')
    assert '3-bet' in advice or 'fold' in advice.lower()

def test_exploit_calling_station_no_bluff():
    advice = _exploit_recommendation('calling_station')
    assert 'bluff' in advice.lower()

def test_tips_not_empty():
    r = _vpr()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _vpr()
    s = vpip_pfr_ratio_one_liner(r)
    assert '[VPR' in s
    assert 'ratio=' in s
    assert 'type=' in s

def test_verdict_equals_type():
    r = _vpr(vpip=0.12, pfr=0.10)
    assert r.verdict == r.player_type_estimate

def test_fish_high_vpip_low_pfr():
    r = _vpr(vpip=0.45, pfr=0.08)
    assert r.player_type_estimate in ('fish', 'calling_station')

def test_reasoning_not_empty():
    r = _vpr()
    assert len(r.reasoning) > 0

def test_vpip_pfr_stored():
    r = _vpr(vpip=0.30, pfr=0.20)
    assert r.vpip == 0.30
    assert r.pfr == 0.20

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
