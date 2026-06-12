"""Tests for winrate_confidence_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.winrate_confidence_guide import (
    analyze_winrate_confidence, WinrateConfidenceResult, winrate_confidence_one_liner,
    _sample_category, _standard_error, _confidence_interval, _is_positive_confirmed,
    _hands_needed,
)

def _wcg(**kw):
    defaults = dict(n_hands=10000, winrate_bb100=5.0, game_type='nl_cash', confidence_level=95)
    defaults.update(kw)
    return analyze_winrate_confidence(**defaults)

def test_returns_result():
    assert isinstance(_wcg(), WinrateConfidenceResult)

def test_sample_category_tiny():
    assert _sample_category(1000) == 'tiny'

def test_sample_category_small():
    assert _sample_category(10000) == 'small'

def test_sample_category_medium():
    assert _sample_category(30000) == 'medium'

def test_sample_category_large():
    assert _sample_category(75000) == 'large'

def test_sample_category_huge():
    assert _sample_category(200000) == 'huge'

def test_standard_error_decreases_with_hands():
    se1 = _standard_error(100.0, 1000)
    se2 = _standard_error(100.0, 10000)
    assert se1 > se2

def test_ci_symmetry():
    lo, hi = _confidence_interval(5.0, 10.0, 1.96)
    assert abs((hi - lo) / 2 - 10.0 * 1.96) < 0.01

def test_positive_confirmed_when_ci_lower_positive():
    assert _is_positive_confirmed(0.1) is True

def test_not_confirmed_when_ci_lower_negative():
    assert _is_positive_confirmed(-1.0) is False

def test_hands_needed_large_winrate():
    n = _hands_needed(10.0, 100.0, 1.96)
    assert n > 0

def test_hands_needed_zero_winrate_returns_large():
    n = _hands_needed(0.0, 100.0, 1.96)
    assert n >= 999999

def test_verdict_positive_confirmed_large_sample():
    r = _wcg(n_hands=100000, winrate_bb100=8.0)
    assert r.is_positive_confirmed is True
    assert r.verdict == 'positive_confirmed'

def test_verdict_uncertain_small_sample():
    r = _wcg(n_hands=1000, winrate_bb100=5.0)
    assert r.verdict == 'uncertain'

def test_verdict_negative_confirmed():
    r = _wcg(n_hands=150000, winrate_bb100=-8.0)
    assert r.verdict == 'negative_confirmed'

def test_ci_lower_less_than_ci_upper():
    r = _wcg()
    assert r.ci_lower < r.ci_upper

def test_tips_not_empty():
    r = _wcg()
    assert len(r.tips) >= 2

def test_one_liner_format():
    r = _wcg()
    s = winrate_confidence_one_liner(r)
    assert '[WCG' in s
    assert 'CI=' in s
    assert 'confirmed=' in s

def test_mtt_wider_ci():
    r_nl = _wcg(game_type='nl_cash', n_hands=10000)
    r_mtt = _wcg(game_type='mtt', n_hands=10000)
    assert r_mtt.ci_upper - r_mtt.ci_lower > r_nl.ci_upper - r_nl.ci_lower

def test_99_ci_wider_than_95():
    r95 = _wcg(confidence_level=95)
    r99 = _wcg(confidence_level=99)
    assert (r99.ci_upper - r99.ci_lower) > (r95.ci_upper - r95.ci_lower)

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
