"""Tests for poker/multiway.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway import analyze_multiway, multiway_equity_adjustment


def test_2opp_cbet_not_recommended_low_equity():
    """2-opponent pot with 60% equity should NOT recommend c-bet (need ~62%+)."""
    r = analyze_multiway(num_opponents=2, pot_bb=15.0, equity=0.60,
                         in_position=True, street='flop')
    assert r.cbet_recommended is False, \
        f'60% equity 2-opp should NOT cbet: {r.cbet_recommended}'
    assert r.recommended_action in ('check', 'check_call', 'fold'), \
        f'Should suggest passive action: {r.recommended_action}'
    print(f'2-opp 60% eq: cbet={r.cbet_recommended} action={r.recommended_action}')


def test_strong_equity_may_cbet_multiway():
    """Strong equity (75%+) should allow c-bet even multiway."""
    r = analyze_multiway(num_opponents=2, pot_bb=15.0, equity=0.80,
                         in_position=True, street='flop')
    assert r.cbet_freq > 0, \
        f'Strong hand should have cbet_freq > 0: {r.cbet_freq:.0%}'
    print(f'2-opp 80% eq: cbet_recommended={r.cbet_recommended} freq={r.cbet_freq:.0%}')


def test_more_opponents_reduces_fold_equity():
    """More opponents → lower combined fold equity."""
    r2 = analyze_multiway(num_opponents=2, pot_bb=15.0, equity=0.60,
                          in_position=True, per_opp_fold_rate=0.52)
    r3 = analyze_multiway(num_opponents=3, pot_bb=15.0, equity=0.60,
                          in_position=True, per_opp_fold_rate=0.52)
    assert r3.fold_equity < r2.fold_equity, \
        f'3-opp fold_eq {r3.fold_equity:.0%} should < 2-opp {r2.fold_equity:.0%}'
    print(f'Fold equity: 2-opp={r2.fold_equity:.0%}  3-opp={r3.fold_equity:.0%}')


def test_bluff_not_allowed_low_fold_equity():
    """Low fold equity (multiple opponents) should disallow bluffing."""
    r = analyze_multiway(num_opponents=3, pot_bb=15.0, equity=0.30,
                         in_position=True, per_opp_fold_rate=0.40)
    assert r.bluff_allowed is False, \
        f'Low fold equity multiway should not allow bluff: {r.bluff_allowed}'
    print(f'3-opp low equity: bluff_allowed={r.bluff_allowed}')


def test_equity_adjustment_decreases_with_more_opponents():
    """Adjusted equity should drop as opponent count rises."""
    eq_1 = multiway_equity_adjustment(0.60, 1)
    eq_2 = multiway_equity_adjustment(0.60, 2)
    eq_3 = multiway_equity_adjustment(0.60, 3)
    assert eq_1 >= eq_2 >= eq_3, \
        f'Equity should decrease with more opp: {eq_1:.2f}>={eq_2:.2f}>={eq_3:.2f}'
    print(f'Adj equity: 1-opp={eq_1:.2f}  2-opp={eq_2:.2f}  3-opp={eq_3:.2f}')


def test_equity_adjustment_below_raw():
    """Adjusted equity should be <= raw equity (multiway penalty)."""
    raw = 0.60
    adj = multiway_equity_adjustment(raw, 2)
    assert adj <= raw, f'Adjusted equity {adj:.2f} should <= raw {raw:.2f}'
    print(f'Raw={raw:.0%} adj={adj:.0%} (multiway penalty)')


def test_fold_equity_needed_below_1():
    """fold_equity_needed should be between 0 and 1."""
    r = analyze_multiway(num_opponents=2, pot_bb=15.0, equity=0.55,
                         bet_size_pct=0.50)
    assert 0.0 < r.fold_equity_needed < 1.0, \
        f'fold_equity_needed out of bounds: {r.fold_equity_needed}'
    print(f'Fold equity needed: {r.fold_equity_needed:.0%}')


def test_value_equity_min_above_50pct():
    """value_equity_min in multiway should be above 50% (needs premium)."""
    r = analyze_multiway(num_opponents=2, pot_bb=15.0, equity=0.60)
    assert r.value_equity_min > 0.50, \
        f'Multiway value threshold should be > 50%: {r.value_equity_min:.0%}'
    print(f'Value equity min: {r.value_equity_min:.0%}')


def test_tips_is_list():
    """tips should be a list."""
    r = analyze_multiway(num_opponents=2, pot_bb=15.0, equity=0.60)
    assert isinstance(r.tips, list), f'tips should be list: {type(r.tips)}'
    print(f'Tips count: {len(r.tips)}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = analyze_multiway(num_opponents=2, pot_bb=15.0, equity=0.60)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 3
    print(f'Reasoning: {r.reasoning[:50]}')


if __name__ == '__main__':
    tests = [
        test_2opp_cbet_not_recommended_low_equity,
        test_strong_equity_may_cbet_multiway,
        test_more_opponents_reduces_fold_equity,
        test_bluff_not_allowed_low_fold_equity,
        test_equity_adjustment_decreases_with_more_opponents,
        test_equity_adjustment_below_raw,
        test_fold_equity_needed_below_1,
        test_value_equity_min_above_50pct,
        test_tips_is_list,
        test_reasoning_is_string,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
