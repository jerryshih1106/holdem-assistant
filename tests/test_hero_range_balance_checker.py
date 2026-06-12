"""Tests for hero_range_balance_checker.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hero_range_balance_checker import (
    check_range_balance, RangeBalanceResult, rbc_one_liner,
    _alpha, _balanced_bluff_pct, _balance_score, _imbalance_type,
)


def _rbc(**kw):
    defaults = dict(bet_size_frac=0.67, bluff_combos=8, value_combos=15, street='river', position='ip')
    defaults.update(kw)
    return check_range_balance(**defaults)


def test_returns_range_balance_result():
    assert isinstance(_rbc(), RangeBalanceResult)


def test_alpha_formula():
    a = _alpha(0.67)
    assert abs(a - 0.67/1.67) < 0.001


def test_alpha_half_pot():
    a = _alpha(0.50)
    assert abs(a - 1/3) < 0.001


def test_balanced_bluff_pct_matches_alpha():
    pct = _balanced_bluff_pct(0.67)
    assert abs(pct - _alpha(0.67)) < 0.001


def test_balance_score_perfect():
    alpha = _alpha(0.67)
    score = _balance_score(alpha, alpha)
    assert score == 10.0


def test_balance_score_severe_imbalance():
    score = _balance_score(0.80, 0.40)
    assert score < 5.0


def test_imbalance_too_bluff_heavy():
    imb = _imbalance_type(0.65, 0.40)
    assert 'bluff_heavy' in imb


def test_imbalance_too_value_heavy():
    imb = _imbalance_type(0.10, 0.40)
    assert 'value_heavy' in imb


def test_imbalance_balanced():
    imb = _imbalance_type(0.40, 0.40)
    assert imb == 'balanced'


def test_actual_bluff_pct_computed():
    r = _rbc(bluff_combos=8, value_combos=12)
    assert abs(r.actual_bluff_pct - 8/20) < 0.01


def test_balance_score_stored():
    r = _rbc()
    assert 0 <= r.balance_score <= 10


def test_extra_bluff_when_value_heavy():
    r = _rbc(bluff_combos=2, value_combos=20)
    assert r.extra_bluff_combos_needed > 0


def test_extra_value_when_bluff_heavy():
    r = _rbc(bluff_combos=20, value_combos=5)
    assert r.extra_value_combos_needed > 0


def test_tips_populated():
    r = _rbc()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rbc()
    line = rbc_one_liner(r)
    assert '[RBC' in line
    assert 'score=' in line


def test_larger_bet_needs_more_bluffs():
    # Larger bet -> higher alpha -> more bluffs needed
    alpha_small = _alpha(0.50)
    alpha_large = _alpha(1.0)
    assert alpha_large > alpha_small


def test_total_combos_correct():
    r = _rbc(bluff_combos=5, value_combos=10)
    assert r.total_combos == 15


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
