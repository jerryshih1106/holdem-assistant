"""Tests for steal_stat_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.steal_stat_guide import (
    analyze_steal_stat, StealStatResult, steal_stat_one_liner,
    _steal_profile, _fold_to_steal_category, _counter_strategy,
)

def _ss(**kw):
    defaults = dict(steal_pct=0.42, fold_to_steal=0.70)
    defaults.update(kw)
    return analyze_steal_stat(**defaults)

def test_returns_result():
    assert isinstance(_ss(), StealStatResult)

def test_steal_profile_nit():
    assert _steal_profile(0.20) == 'nit'

def test_steal_profile_tag():
    assert _steal_profile(0.40) == 'tag'

def test_steal_profile_lag():
    assert _steal_profile(0.60) == 'lag'

def test_steal_profile_maniac():
    assert _steal_profile(0.80) == 'maniac'

def test_fold_cat_very_low():
    assert _fold_to_steal_category(0.40) == 'very_low'

def test_fold_cat_standard():
    assert _fold_to_steal_category(0.68) == 'standard'

def test_fold_cat_very_high():
    assert _fold_to_steal_category(0.90) == 'very_high'

def test_counter_nit():
    c = _counter_strategy('nit', 'standard')
    assert 'nit' in c.lower() or 'strong' in c.lower()

def test_counter_maniac_over_fold():
    c = _counter_strategy('maniac', 'high')
    assert 'maniac' in c.lower() or '3-bet' in c.lower()

def test_tips_at_least_two():
    r = _ss()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _ss()
    s = steal_stat_one_liner(r)
    assert '[STEAL' in s
    assert 'profile=' in s
    assert 'counter=' in s

def test_stored_values():
    r = _ss(steal_pct=0.55, fold_to_steal=0.65)
    assert r.steal_pct == 0.55
    assert r.fold_to_steal == 0.65

def test_verdict_not_empty():
    r = _ss()
    assert len(r.verdict) > 0

def test_reasoning_contains_profile():
    r = _ss()
    assert r.steal_profile in r.reasoning

def test_over_fold_tip_triggered():
    r = _ss(steal_pct=0.42, fold_to_steal=0.85)
    fold_tips = [t for t in r.tips if 'fold' in t.lower() or 'defend' in t.lower()]
    assert len(fold_tips) >= 1

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
