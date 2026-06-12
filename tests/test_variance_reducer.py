"""Tests for poker/variance_reducer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.variance_reducer import advise_variance, VarianceAdvice, variance_one_liner


def _va(**kw):
    defaults = dict(
        ev_high_var=5.0, std_dev_high_var=80.0, ev_low_var=3.0, std_dev_low_var=15.0,
        bankroll_bb=1500.0, current_stake_bb=100.0, tilt_score=0.3,
        recent_loss_bi=2.0, is_tournament=False,
    )
    defaults.update(kw)
    return advise_variance(**defaults)


def test_returns_correct_type():
    r = _va()
    assert isinstance(r, VarianceAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _va()
    fields = [
        'ev_high_var', 'std_dev_high_var', 'ev_low_var', 'std_dev_low_var',
        'bankroll_bb', 'current_stake_bb', 'tilt_score', 'recent_loss_bi',
        'is_tournament', 'buyins_at_stake', 'risk_premium_high_var',
        'risk_premium_low_var', 'risk_adjusted_ev_high_var', 'risk_adjusted_ev_low_var',
        'ev_edge_high_var', 'var_adjusted_edge', 'sharpe_ratio_high_low',
        'recommended_line', 'confidence', 'action', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_buyins_calculation():
    r = _va(bankroll_bb=2000.0, current_stake_bb=100.0)
    assert abs(r.buyins_at_stake - 20.0) < 0.5, f'Buyins: {r.buyins_at_stake}'
    print(f'Buyins: {r.buyins_at_stake}')


def test_high_var_has_higher_risk_premium():
    """High-variance line has higher risk premium than low-variance."""
    r = _va()
    assert r.risk_premium_high_var >= r.risk_premium_low_var, \
        f'High-var RP >= low-var: {r.risk_premium_high_var:.2f} vs {r.risk_premium_low_var:.2f}'
    print(f'RP: high={r.risk_premium_high_var:.2f} low={r.risk_premium_low_var:.2f}')


def test_short_bankroll_prefers_low_variance():
    """Short bankroll with marginal EV edge → prefer low-variance line."""
    # Use a small EV edge (3.3 vs 3.0) so risk premium tips the decision
    r = _va(bankroll_bb=500.0, ev_high_var=3.3, ev_low_var=3.0)  # only 5 BI, tiny edge
    assert r.recommended_line in ('low_variance', 'negligible'), \
        f'Short BR with tiny edge should prefer low-var: {r.recommended_line} (adj_edge={r.var_adjusted_edge:.2f})'
    print(f'Short BR recommendation: {r.recommended_line} (adj_edge={r.var_adjusted_edge:.2f})')


def test_deep_bankroll_prefers_high_ev():
    """Deep bankroll → prefer high-EV line even if higher variance."""
    r = _va(bankroll_bb=20000.0, ev_high_var=8.0, std_dev_high_var=60.0,
            ev_low_var=2.0, std_dev_low_var=10.0)
    assert r.recommended_line in ('high_variance', 'negligible'), \
        f'Deep BR with big EV edge should prefer high-var: {r.recommended_line}'
    print(f'Deep BR recommendation: {r.recommended_line}')


def test_tilt_penalizes_high_variance():
    """High tilt → risk premium increases for high-var line."""
    r_no_tilt = _va(tilt_score=0.0)
    r_high_tilt = _va(tilt_score=0.8)
    assert r_high_tilt.risk_premium_high_var >= r_no_tilt.risk_premium_high_var, \
        f'High tilt should have higher RP: {r_high_tilt.risk_premium_high_var:.2f} vs {r_no_tilt.risk_premium_high_var:.2f}'
    print(f'RP (high-var): no_tilt={r_no_tilt.risk_premium_high_var:.2f} high_tilt={r_high_tilt.risk_premium_high_var:.2f}')


def test_recent_losses_penalize_variance():
    """More recent losses → higher risk premium for high-var line."""
    r_no_loss = _va(recent_loss_bi=0.0)
    r_big_loss = _va(recent_loss_bi=5.0)
    assert r_big_loss.risk_premium_high_var >= r_no_loss.risk_premium_high_var, \
        f'More losses should increase RP: {r_big_loss.risk_premium_high_var:.2f} vs {r_no_loss.risk_premium_high_var:.2f}'
    print(f'RP: 0 BI loss={r_no_loss.risk_premium_high_var:.2f} 5 BI loss={r_big_loss.risk_premium_high_var:.2f}')


def test_action_is_valid():
    valid = {'choose_high_var', 'choose_low_var', 'coin_flip'}
    r = _va()
    assert r.action in valid, f'Invalid action: {r.action}'
    print(f'Action: {r.action}')


def test_recommended_line_valid():
    valid = {'high_variance', 'low_variance', 'negligible'}
    r = _va()
    assert r.recommended_line in valid, f'Invalid line: {r.recommended_line}'
    print(f'Recommended: {r.recommended_line}')


def test_confidence_valid():
    valid = {'strong', 'moderate', 'marginal'}
    r = _va()
    assert r.confidence in valid, f'Invalid confidence: {r.confidence}'
    print(f'Confidence: {r.confidence}')


def test_equal_ev_prefers_low_var():
    """When EV is equal, always prefer low-variance."""
    r = _va(ev_high_var=3.0, std_dev_high_var=80.0, ev_low_var=3.0, std_dev_low_var=15.0)
    assert r.recommended_line in ('low_variance', 'negligible'), \
        f'Equal EV should prefer low-var: {r.recommended_line}'
    print(f'Equal EV: {r.recommended_line}')


def test_huge_ev_edge_overcomes_variance():
    """Very large EV edge with enough bankroll → take high-var line."""
    r = _va(ev_high_var=20.0, std_dev_high_var=40.0, ev_low_var=1.0, std_dev_low_var=10.0,
            bankroll_bb=10000.0, tilt_score=0.0, recent_loss_bi=0.0)
    assert r.recommended_line in ('high_variance', 'negligible'), \
        f'Huge EV edge should prefer high-var: {r.recommended_line}'
    print(f'Huge EV edge: {r.recommended_line}')


def test_tournament_penalizes_high_variance():
    """Tournament mode adds extra penalty for high-variance."""
    r_cash = _va(is_tournament=False)
    r_mtt = _va(is_tournament=True)
    assert r_mtt.var_adjusted_edge <= r_cash.var_adjusted_edge + 0.01, \
        f'Tournament should reduce adj edge: {r_mtt.var_adjusted_edge:.2f} vs {r_cash.var_adjusted_edge:.2f}'
    print(f'Adj edge: cash={r_cash.var_adjusted_edge:.2f} MTT={r_mtt.var_adjusted_edge:.2f}')


def test_ev_edge_correct():
    """ev_edge = ev_high_var - ev_low_var."""
    r = _va(ev_high_var=5.0, ev_low_var=3.0)
    assert abs(r.ev_edge_high_var - 2.0) < 0.01, f'EV edge: {r.ev_edge_high_var}'
    print(f'EV edge: {r.ev_edge_high_var:+.2f}BB')


def test_risk_premiums_nonnegative():
    r = _va()
    assert r.risk_premium_high_var >= 0
    assert r.risk_premium_low_var >= 0
    print(f'RPs: high={r.risk_premium_high_var:.3f} low={r.risk_premium_low_var:.3f}')


def test_sharpe_ratio_positive():
    r = _va(ev_high_var=5.0, ev_low_var=3.0)
    assert r.sharpe_ratio_high_low >= 0
    print(f'Sharpe ratio: {r.sharpe_ratio_high_low:.2f}')


def test_tips_not_empty():
    r = _va()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_verdict_not_empty():
    r = _va()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:60]}...')


def test_reasoning_not_empty():
    r = _va()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}...')


def test_one_liner():
    r = _va()
    line = variance_one_liner(r)
    assert 'VAR' in line and 'raw_edge=' in line and 'rp_hi=' in line and 'conf=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_buyins_calculation, test_high_var_has_higher_risk_premium,
        test_short_bankroll_prefers_low_variance, test_deep_bankroll_prefers_high_ev,
        test_tilt_penalizes_high_variance, test_recent_losses_penalize_variance,
        test_action_is_valid, test_recommended_line_valid,
        test_confidence_valid, test_equal_ev_prefers_low_var,
        test_huge_ev_edge_overcomes_variance, test_tournament_penalizes_high_variance,
        test_ev_edge_correct, test_risk_premiums_nonnegative,
        test_sharpe_ratio_positive, test_tips_not_empty,
        test_verdict_not_empty, test_reasoning_not_empty, test_one_liner,
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
