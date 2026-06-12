"""Tests for af_interpretation_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.af_interpretation_guide import (
    analyze_af_interpretation, AfInterpretationResult, af_one_liner,
    _af_category, _exploit_advice, _weighted_af,
)

def _af(**kw):
    defaults = dict(flop_af=1.5, turn_af=1.8, river_af=2.0)
    defaults.update(kw)
    return analyze_af_interpretation(**defaults)

def test_returns_result():
    assert isinstance(_af(), AfInterpretationResult)

def test_category_passive():
    assert _af_category(0.5) == 'passive'

def test_category_balanced():
    assert _af_category(1.5) == 'balanced'

def test_category_aggressive():
    assert _af_category(3.0) == 'aggressive'

def test_category_very_aggressive():
    assert _af_category(5.0) == 'very_aggressive'

def test_category_maniac():
    assert _af_category(7.0) == 'maniac'

def test_weighted_af_river_weighted_more():
    w = _weighted_af(1.0, 1.0, 3.0)
    # weighted should be > simple average (1.667) because river weighted more
    simple_avg = (1.0 + 1.0 + 3.0) / 3.0
    assert w > simple_avg

def test_exploit_advice_not_empty():
    advice = _exploit_advice('passive', 'flop')
    assert len(advice) > 0

def test_exploit_river_suffix():
    advice = _exploit_advice('aggressive', 'river')
    assert 'River' in advice

def test_overall_af_stored():
    r = _af(flop_af=2.0, turn_af=2.0, river_af=2.0)
    assert abs(r.overall_af - 2.0) < 0.01

def test_verdict_equals_category():
    r = _af()
    assert r.verdict == r.af_category

def test_tips_at_least_two():
    r = _af()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _af()
    s = af_one_liner(r)
    assert '[AF' in s
    assert 'wtd=' in s
    assert 'cat=' in s

def test_passive_low_af():
    r = _af(flop_af=0.3, turn_af=0.4, river_af=0.5)
    assert r.af_category == 'passive'

def test_maniac_high_af():
    r = _af(flop_af=8.0, turn_af=9.0, river_af=10.0)
    assert r.af_category == 'maniac'

def test_reasoning_not_empty():
    r = _af()
    assert len(r.reasoning) > 10

def test_weighted_less_than_max():
    r = _af(flop_af=1.0, turn_af=2.0, river_af=4.0)
    assert r.weighted_af < 4.0

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
