"""Tests for cbet_fold_stat_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.cbet_fold_stat_guide import (
    analyze_cbet_fold_stat, CbetFoldResult, cbet_fold_one_liner,
    _fold_cat, _be_fold_pct, _cbet_bluff_ev, _bluff_recommendation,
)

def _cfs(**kw):
    defaults = dict(fold_to_cbet=0.50, cbet_bb=5.0, pot_bb=10.0, cbet_size_fraction=0.50)
    defaults.update(kw)
    return analyze_cbet_fold_stat(**defaults)

def test_returns_result():
    assert isinstance(_cfs(), CbetFoldResult)

def test_fold_cat_very_low():
    assert _fold_cat(0.20) == 'very_low'

def test_fold_cat_low():
    assert _fold_cat(0.35) == 'low'

def test_fold_cat_standard():
    assert _fold_cat(0.48) == 'standard'

def test_fold_cat_high():
    assert _fold_cat(0.60) == 'high'

def test_fold_cat_very_high():
    assert _fold_cat(0.75) == 'very_high'

def test_be_fold_pct_half_pot():
    be = _be_fold_pct(0.50)
    assert abs(be - 0.333) < 0.01

def test_be_fold_pct_pot_size():
    be = _be_fold_pct(1.0)
    assert abs(be - 0.50) < 0.01

def test_bluff_ev_positive_high_fold():
    ev = _cbet_bluff_ev(0.70, 5.0, 10.0)
    assert ev > 0

def test_bluff_ev_negative_low_fold():
    ev = _cbet_bluff_ev(0.20, 5.0, 10.0)
    assert ev < 0

def test_recommendation_no_bluff_very_low():
    assert _bluff_recommendation('very_low') == 'NO_BLUFF'

def test_recommendation_heavy_bluff_very_high():
    assert _bluff_recommendation('very_high') == 'BLUFF_HEAVILY'

def test_verdict_equals_recommendation():
    r = _cfs()
    assert r.verdict == r.bluff_recommendation

def test_tips_at_least_two():
    r = _cfs()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _cfs()
    s = cbet_fold_one_liner(r)
    assert '[FCBET' in s
    assert 'cat=' in s
    assert 'bluff=' in s

def test_stored_fold_to_cbet():
    r = _cfs(fold_to_cbet=0.65)
    assert r.fold_to_cbet == 0.65

def test_reasoning_not_empty():
    r = _cfs()
    assert len(r.reasoning) > 10

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
