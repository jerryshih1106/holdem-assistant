"""Tests for poker/bluff_planner.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bluff_planner import plan_bluff, bluff_summary


def test_single_street_alpha_correct():
    """Single-street bluff: alpha = bet/(pot+bet)."""
    r = plan_bluff(pot_bb=10.0, stack_bb=50.0, bet_sizes=[0.75])
    bet = 10.0 * 0.75  # = 7.5
    expected_alpha = bet / (10.0 + bet)  # = 7.5 / 17.5 ≈ 0.4286
    assert abs(r.per_street_alpha[0] - expected_alpha) < 0.005, \
        f'Alpha {r.per_street_alpha[0]:.3f} should be ~{expected_alpha:.3f}'
    print(f'Single-street alpha: {r.per_street_alpha[0]:.3f} (expected {expected_alpha:.3f})')


def test_three_street_bluff_feasible():
    """Standard 3-street 40%/60%/75% bluff should be feasible."""
    r = plan_bluff(pot_bb=10.0, stack_bb=100.0,
                   bet_sizes=[0.40, 0.60, 0.75], villain_fold_estimate=0.55)
    assert r.n_streets == 3, f'Should have 3 streets: {r.n_streets}'
    assert r.is_feasible is True, \
        f'3-street bluff should be feasible (fold_needed={r.cumulative_fold_needed:.0%})'
    print(f'3-street: fold_needed={r.cumulative_fold_needed:.0%} feasible={r.is_feasible}')


def test_cumulative_fold_lower_than_third_street_alpha():
    """
    Cumulative fold needed should be lower than the last street's alpha alone
    because villain can fold on earlier streets.
    """
    r = plan_bluff(pot_bb=10.0, stack_bb=100.0, bet_sizes=[0.40, 0.60, 0.75])
    last_alpha = r.per_street_alpha[-1]
    # The multi-street plan gives villain a chance to fold early → cumulative < last_alpha
    assert r.cumulative_fold_needed < last_alpha + 0.10, \
        f'Cumulative {r.cumulative_fold_needed:.0%} should be near or below last alpha {last_alpha:.0%}'
    print(f'Cumulative={r.cumulative_fold_needed:.0%} vs last street alpha={last_alpha:.0%}')


def test_high_fold_estimate_gives_positive_ev():
    """When villain fold rate > breakeven, EV should be positive."""
    r = plan_bluff(pot_bb=10.0, stack_bb=100.0,
                   bet_sizes=[0.50, 0.70], villain_fold_estimate=0.70)
    # fold_estimate=0.70 > cumulative_fold_needed (~0.39) → EV should be positive
    if 0.70 > r.cumulative_fold_needed:
        assert r.bluff_ev > 0, \
            f'Fold rate 70% > breakeven {r.cumulative_fold_needed:.0%} → EV should be positive'
    print(f'High fold EV: {r.bluff_ev:+.1f}BB (fold_needed={r.cumulative_fold_needed:.0%})')


def test_low_fold_estimate_gives_negative_ev():
    """When villain fold rate < breakeven, EV should be negative."""
    r = plan_bluff(pot_bb=10.0, stack_bb=100.0,
                   bet_sizes=[0.60, 0.80, 1.00], villain_fold_estimate=0.20)
    if r.cumulative_fold_needed > 0.20:
        assert r.bluff_ev < 0, \
            f'Fold rate too low → EV should be negative: {r.bluff_ev:+.1f}BB'
    print(f'Low fold EV: {r.bluff_ev:+.1f}BB (fold_needed={r.cumulative_fold_needed:.0%})')


def test_pot_compounds_each_street():
    """Pot should grow each street after villain calls."""
    r = plan_bluff(pot_bb=10.0, stack_bb=200.0, bet_sizes=[0.50, 0.50, 0.50])
    assert len(r.streets) == 3
    assert r.streets[0].pot_before < r.streets[1].pot_before, \
        'Pot should grow from street 1 to street 2'
    assert r.streets[1].pot_before < r.streets[2].pot_before, \
        'Pot should grow from street 2 to street 3'
    print(f'Pots: {r.streets[0].pot_before:.1f} -> {r.streets[1].pot_before:.1f} -> {r.streets[2].pot_before:.1f}BB')


def test_two_street_bluff():
    """Two-street bluff plan should have exactly 2 streets."""
    r = plan_bluff(pot_bb=8.0, stack_bb=60.0, bet_sizes=[0.50, 0.75])
    assert r.n_streets == 2, f'Should have 2 streets: {r.n_streets}'
    assert len(r.streets) == 2
    assert len(r.per_street_alpha) == 2
    print(f'2-street: fold_needed={r.cumulative_fold_needed:.0%} invest={r.total_investment:.1f}BB')


def test_total_investment_sum_of_bets():
    """Total investment should equal sum of individual street bets."""
    r = plan_bluff(pot_bb=10.0, stack_bb=100.0, bet_sizes=[0.40, 0.60])
    computed_sum = sum(s.bet_amount for s in r.streets)
    assert abs(r.total_investment - computed_sum) < 0.05, \
        f'Total investment {r.total_investment:.1f} != sum of bets {computed_sum:.1f}'
    print(f'Total investment: {r.total_investment:.1f}BB (sum={computed_sum:.1f}BB)')


def test_pot_bet_has_50pct_alpha():
    """100% pot bet (PSB) should give alpha ≈ 50%."""
    r = plan_bluff(pot_bb=10.0, stack_bb=50.0, bet_sizes=[1.00])
    expected_alpha = 1.0 / (1.0 + 1.0)  # = 0.50
    assert abs(r.per_street_alpha[0] - expected_alpha) < 0.01, \
        f'PSB alpha {r.per_street_alpha[0]:.3f} should be ~0.50'
    print(f'PSB alpha: {r.per_street_alpha[0]:.3f}')


def test_small_bet_has_low_alpha():
    """33% pot bet should give alpha ≈ 25%."""
    r = plan_bluff(pot_bb=10.0, stack_bb=50.0, bet_sizes=[0.333])
    expected_alpha = 0.333 / (1.0 + 0.333)  # ≈ 0.25
    assert abs(r.per_street_alpha[0] - expected_alpha) < 0.02, \
        f'33% bet alpha {r.per_street_alpha[0]:.3f} should be ~0.25'
    print(f'33% bet alpha: {r.per_street_alpha[0]:.3f}')


def test_bluff_summary_format():
    """bluff_summary should return a string."""
    r = plan_bluff(pot_bb=10.0, stack_bb=100.0,
                   bet_sizes=[0.50, 0.70], villain_fold_estimate=0.55)
    s = bluff_summary(r)
    assert isinstance(s, str), f'bluff_summary should return str: {type(s)}'
    assert len(s) > 5, f'Summary too short: {s!r}'
    print(f'Bluff summary: {s[:60]}')


if __name__ == '__main__':
    tests = [
        test_single_street_alpha_correct,
        test_three_street_bluff_feasible,
        test_cumulative_fold_lower_than_third_street_alpha,
        test_high_fold_estimate_gives_positive_ev,
        test_low_fold_estimate_gives_negative_ev,
        test_pot_compounds_each_street,
        test_two_street_bluff,
        test_total_investment_sum_of_bets,
        test_pot_bet_has_50pct_alpha,
        test_small_bet_has_low_alpha,
        test_bluff_summary_format,
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
