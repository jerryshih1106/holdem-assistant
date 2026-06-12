"""Tests for three_bet_stat_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.three_bet_stat_guide import (
    analyze_three_bet_stat, ThreeBetStatResult, three_bet_stat_one_liner,
    _3bet_profile, _position_adjust, _counter_strategy,
)

def _tbs(**kw):
    defaults = dict(three_bet_pct=0.07, position='btn')
    defaults.update(kw)
    return analyze_three_bet_stat(**defaults)

def test_returns_result():
    assert isinstance(_tbs(), ThreeBetStatResult)

def test_profile_nit():
    assert _3bet_profile(0.02) == 'nit'

def test_profile_tag():
    assert _3bet_profile(0.06) == 'tag'

def test_profile_lag():
    assert _3bet_profile(0.11) == 'lag'

def test_profile_maniac():
    assert _3bet_profile(0.18) == 'maniac'

def test_position_adjust_btn_very_low():
    ctx = _position_adjust('btn', 0.02)
    assert 'low' in ctx.lower() or 'exploitable' in ctx.lower() or 'low' in ctx.lower()

def test_position_adjust_bb_moderate():
    ctx = _position_adjust('bb', 0.09)
    assert len(ctx) > 0

def test_position_adjust_unknown_returns_message():
    ctx = _position_adjust('ep', 0.05)
    assert 'ep' in ctx.lower() or 'no' in ctx.lower() or 'benchmark' in ctx.lower()

def test_counter_nit_open_freely():
    c = _counter_strategy('nit')
    assert 'nit' in c.lower() or 'open' in c.lower() or 'monster' in c.lower()

def test_counter_maniac_trap():
    c = _counter_strategy('maniac')
    assert 'trap' in c.lower() or '4-bet' in c.lower() or 'maniac' in c.lower()

def test_tips_at_least_two():
    r = _tbs()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _tbs()
    s = three_bet_stat_one_liner(r)
    assert '[3BET' in s
    assert 'profile=' in s
    assert 'counter=' in s

def test_verdict_equals_profile():
    r = _tbs()
    assert r.verdict == r.profile

def test_stored_position():
    r = _tbs(position='sb')
    assert r.position == 'sb'

def test_reasoning_contains_pct():
    r = _tbs(three_bet_pct=0.10)
    assert '10%' in r.reasoning or '0.10' in r.reasoning

def test_high_3bet_tip():
    r = _tbs(three_bet_pct=0.15)
    hi_tips = [t for t in r.tips if '4-bet' in t or 'high' in t.lower()]
    assert len(hi_tips) >= 1

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
