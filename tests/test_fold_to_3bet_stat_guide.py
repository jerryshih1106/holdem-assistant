"""Tests for fold_to_3bet_stat_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.fold_to_3bet_stat_guide import (
    analyze_fold_to_3bet, FoldTo3BetResult, fold_to_3bet_one_liner,
    _fold_to_3bet_category, _bluff_3bet_ev, _optimal_3bet_range,
)

def _f3b(**kw):
    defaults = dict(fold_to_3bet=0.60, bluff_size_bb=9.0, pot_bb=3.5)
    defaults.update(kw)
    return analyze_fold_to_3bet(**defaults)

def test_returns_result():
    assert isinstance(_f3b(), FoldTo3BetResult)

def test_category_very_low():
    assert _fold_to_3bet_category(0.30) == 'very_low'

def test_category_low():
    assert _fold_to_3bet_category(0.45) == 'low'

def test_category_standard():
    assert _fold_to_3bet_category(0.57) == 'standard'

def test_category_high():
    assert _fold_to_3bet_category(0.70) == 'high'

def test_category_very_high():
    assert _fold_to_3bet_category(0.80) == 'very_high'

def test_bluff_ev_positive_when_fold_high():
    ev = _bluff_3bet_ev(0.80, 9.0, 3.5)
    assert ev > 0

def test_bluff_ev_negative_when_fold_low():
    ev = _bluff_3bet_ev(0.20, 9.0, 3.5)
    assert ev < 0

def test_optimal_range_very_low_value_only():
    r = _optimal_3bet_range('very_low')
    assert 'QQ' in r or 'value' in r.lower() or 'only' in r.lower()

def test_optimal_range_very_high_wide():
    r = _optimal_3bet_range('very_high')
    assert 'bluff' in r.lower() or 'wide' in r.lower() or 'connector' in r.lower()

def test_exploit_maps_correctly():
    r = _f3b(fold_to_3bet=0.30)
    assert r.exploit == 'VALUE_ONLY'

def test_exploit_heavy_bluff_at_high_fold():
    r = _f3b(fold_to_3bet=0.80)
    assert r.exploit == 'HEAVY_BLUFF'

def test_verdict_equals_exploit():
    r = _f3b()
    assert r.verdict == r.exploit

def test_tips_at_least_two():
    r = _f3b()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _f3b()
    s = fold_to_3bet_one_liner(r)
    assert '[F3B' in s
    assert 'cat=' in s
    assert 'exploit=' in s
    assert 'bluff_ev=' in s

def test_reasoning_not_empty():
    r = _f3b()
    assert len(r.reasoning) > 10

def test_stored_fields():
    r = _f3b(fold_to_3bet=0.70, bluff_size_bb=10.0, pot_bb=4.0)
    assert r.fold_to_3bet == 0.70
    assert r.bluff_size_bb == 10.0

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
