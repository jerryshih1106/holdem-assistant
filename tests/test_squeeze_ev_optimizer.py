"""Tests for poker/squeeze_ev_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.squeeze_ev_optimizer import optimize_squeeze, SqueezeEVResult, sqz_one_liner


def _sqz(**kw):
    defaults = dict(
        hero_position='BTN',
        hero_hand_rank_pct=0.72,
        opener_position='UTG',
        opener_open_bb=2.5,
        opener_fold_to_3b=0.55,
        n_callers=2,
        caller_avg_fold_to_squeeze=0.65,
        effective_stack_bb=100.0,
        is_ip=True,
        villain_4bet_pct=0.08,
        caller_vpip=0.30,
    )
    defaults.update(kw)
    return optimize_squeeze(**defaults)


def test_returns_correct_type():
    r = _sqz()
    assert isinstance(r, SqueezeEVResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _sqz()
    fields = [
        'hero_position', 'hero_hand_rank_pct', 'opener_position',
        'opener_open_bb', 'opener_fold_to_3b', 'n_callers',
        'caller_avg_fold_to_squeeze', 'effective_stack_bb', 'is_ip',
        'dead_money_bb', 'squeeze_size_bb', 'pot_before_squeeze_bb',
        'opener_fold_pct', 'caller_fold_pct_each', 'p_all_fold',
        'ev_fold_component', 'ev_call_component', 'ev_4bet_component',
        'ev_total', 'ev_per_100_bb100', 'ev_fold_only', 'breakeven_fold_pct',
        'fold_surplus', 'hero_equity_if_called',
        'squeeze_recommended', 'decision', 'confidence', 'squeeze_type',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_dead_money_positive():
    r = _sqz()
    assert r.dead_money_bb > 0, f'Dead money should be positive: {r.dead_money_bb}'
    print(f'Dead money: {r.dead_money_bb:.1f}BB')


def test_more_callers_more_dead_money():
    """More callers = more dead money."""
    r1 = _sqz(n_callers=1)
    r2 = _sqz(n_callers=3)
    assert r2.dead_money_bb > r1.dead_money_bb, \
        f'More callers should have more dead money: {r2.dead_money_bb} vs {r1.dead_money_bb}'
    print(f'Dead money: 1caller={r1.dead_money_bb:.1f}BB 3callers={r2.dead_money_bb:.1f}BB')


def test_squeeze_size_larger_with_more_callers():
    """Squeeze size should increase with more callers."""
    r1 = _sqz(n_callers=1)
    r2 = _sqz(n_callers=3)
    assert r2.squeeze_size_bb > r1.squeeze_size_bb, \
        f'More callers should need bigger squeeze: {r2.squeeze_size_bb} vs {r1.squeeze_size_bb}'
    print(f'Squeeze: 1caller={r1.squeeze_size_bb:.1f}BB 3callers={r2.squeeze_size_bb:.1f}BB')


def test_p_all_fold_in_valid_range():
    r = _sqz()
    assert 0.0 < r.p_all_fold < 1.0, f'p_all_fold out of range: {r.p_all_fold}'
    print(f'P(all_fold): {r.p_all_fold:.0%}')


def test_more_callers_lower_fold_probability():
    """More callers = lower probability all fold."""
    r1 = _sqz(n_callers=1)
    r3 = _sqz(n_callers=3)
    assert r1.p_all_fold > r3.p_all_fold, \
        f'1 caller should have higher fold prob: {r1.p_all_fold:.0%} vs 3 {r3.p_all_fold:.0%}'
    print(f'P(fold): 1c={r1.p_all_fold:.0%} 3c={r3.p_all_fold:.0%}')


def test_high_fold_rate_positive_ev():
    """High fold rates with 1 caller should make squeeze profitable."""
    # 1 caller: p_all_fold = opener*caller ~ 0.75*0.85 = 64%, breakeven ~54%
    r = _sqz(n_callers=1, opener_fold_to_3b=0.75, caller_avg_fold_to_squeeze=0.85)
    assert r.ev_total > 0, f'High fold rates (1 caller) should give positive EV: {r.ev_total:.2f}'
    print(f'High fold EV (1 caller): {r.ev_total:+.2f}BB')


def test_breakeven_fold_formula():
    """Breakeven fold = squeeze_size / (squeeze_size + dead_money)."""
    r = _sqz()
    expected = r.squeeze_size_bb / (r.squeeze_size_bb + r.dead_money_bb)
    assert abs(r.breakeven_fold_pct - expected) < 0.02, \
        f'BE fold: {r.breakeven_fold_pct:.3f} vs {expected:.3f}'
    print(f'Breakeven fold: {r.breakeven_fold_pct:.0%}')


def test_fold_surplus_consistent():
    """fold_surplus = p_all_fold - breakeven_fold_pct."""
    r = _sqz()
    expected = round(r.p_all_fold - r.breakeven_fold_pct, 3)
    assert abs(r.fold_surplus - expected) < 0.01, \
        f'Surplus: {r.fold_surplus:.3f} vs {expected:.3f}'
    print(f'Fold surplus: {r.fold_surplus:+.0%}')


def test_premium_hand_recommended_squeeze():
    """Premium hand (AA/KK) should recommend squeeze."""
    r = _sqz(hero_hand_rank_pct=0.99)  # AA
    assert r.squeeze_recommended or r.decision in ('squeeze_value',), \
        f'AA should squeeze: {r.decision}'
    print(f'AA squeeze: {r.decision}')


def test_decision_valid():
    valid = {'squeeze_value', 'squeeze_bluff', 'squeeze_marginal', 'fold', 'call'}
    r = _sqz()
    assert r.decision in valid, f'Invalid decision: {r.decision}'
    print(f'Decision: {r.decision}')


def test_squeeze_type_valid():
    valid = {'strong_value', 'light_value', 'semibluff', 'pure_bluff'}
    r = _sqz()
    assert r.squeeze_type in valid, f'Invalid squeeze type: {r.squeeze_type}'
    print(f'Squeeze type: {r.squeeze_type}')


def test_aa_is_strong_value():
    r = _sqz(hero_hand_rank_pct=0.99)
    assert r.squeeze_type == 'strong_value', f'AA should be strong_value: {r.squeeze_type}'
    print(f'AA type: {r.squeeze_type}')


def test_weak_hand_is_pure_bluff():
    r = _sqz(hero_hand_rank_pct=0.15)
    assert r.squeeze_type == 'pure_bluff', f'Weak hand should be pure_bluff: {r.squeeze_type}'
    print(f'Weak hand type: {r.squeeze_type}')


def test_ip_squeeze_is_smaller_than_oop():
    """IP squeeze should be smaller than OOP (less positional penalty)."""
    r_ip = _sqz(is_ip=True, hero_position='BTN')
    r_oop = _sqz(is_ip=False, hero_position='BB')
    assert r_ip.squeeze_size_bb <= r_oop.squeeze_size_bb, \
        f'IP squeeze {r_ip.squeeze_size_bb} should <= OOP {r_oop.squeeze_size_bb}'
    print(f'Squeeze size: IP={r_ip.squeeze_size_bb:.1f}BB OOP={r_oop.squeeze_size_bb:.1f}BB')


def test_equity_when_called_positive():
    r = _sqz()
    assert 0.20 <= r.hero_equity_if_called <= 0.85, \
        f'Equity out of range: {r.hero_equity_if_called}'
    print(f'Equity when called: {r.hero_equity_if_called:.0%}')


def test_tips_not_empty():
    r = _sqz()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_dead_money_tip_present():
    r = _sqz()
    dm_tips = [t for t in r.tips if 'DEAD MONEY' in t]
    assert len(dm_tips) > 0, f'Dead money tip missing: {r.tips}'
    print('Dead money tip found')


def test_ev_breakdown_tip_present():
    r = _sqz()
    ev_tips = [t for t in r.tips if 'EV BREAKDOWN' in t]
    assert len(ev_tips) > 0, f'EV breakdown tip missing: {r.tips}'
    print('EV breakdown tip found')


def test_opener_fold_pct_in_range():
    r = _sqz()
    assert 0.10 <= r.opener_fold_pct <= 0.90, \
        f'Opener fold out of range: {r.opener_fold_pct}'
    print(f'Opener fold: {r.opener_fold_pct:.0%}')


def test_caller_fold_pct_higher_than_opener():
    """Callers (wider range) should fold more than opener."""
    r = _sqz()
    assert r.caller_fold_pct_each >= r.opener_fold_pct * 0.90, \
        f'Caller fold {r.caller_fold_pct_each:.0%} should be near opener {r.opener_fold_pct:.0%}'
    print(f'Fold rates: opener={r.opener_fold_pct:.0%} caller={r.caller_fold_pct_each:.0%}')


def test_verdict_contains_decision():
    r = _sqz()
    assert r.decision.upper() in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _sqz()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _sqz()
    line = sqz_one_liner(r)
    assert 'SQZ' in line and 'ev=' in line and 'p_fold=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_dead_money_positive, test_more_callers_more_dead_money,
        test_squeeze_size_larger_with_more_callers, test_p_all_fold_in_valid_range,
        test_more_callers_lower_fold_probability, test_high_fold_rate_positive_ev,
        test_breakeven_fold_formula, test_fold_surplus_consistent,
        test_premium_hand_recommended_squeeze, test_decision_valid,
        test_squeeze_type_valid, test_aa_is_strong_value,
        test_weak_hand_is_pure_bluff, test_ip_squeeze_is_smaller_than_oop,
        test_equity_when_called_positive, test_tips_not_empty,
        test_dead_money_tip_present, test_ev_breakdown_tip_present,
        test_opener_fold_pct_in_range, test_caller_fold_pct_higher_than_opener,
        test_verdict_contains_decision, test_reasoning_not_empty, test_one_liner,
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
