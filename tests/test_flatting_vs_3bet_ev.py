"""Tests for poker/flatting_vs_3bet_ev.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.flatting_vs_3bet_ev import compare_flat_3bet, Flat3BetResult, f3b_one_liner


def _f3b(**kw):
    defaults = dict(
        hero_hand_rank_pct=0.87,    # AQs level
        hero_is_ip=True,
        villain_open_bb=2.5,
        villain_open_pct=0.44,
        villain_fold_to_3b=0.55,
        villain_4bet_pct=0.08,
        effective_stack_bb=100.0,
        nut_potential=0.50,
        domination_risk=0.25,
    )
    defaults.update(kw)
    return compare_flat_3bet(**defaults)


def test_returns_correct_type():
    r = _f3b()
    assert isinstance(r, Flat3BetResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _f3b()
    fields = [
        'hero_hand_rank_pct', 'hero_is_ip',
        'villain_open_bb', 'villain_open_pct', 'villain_fold_to_3b',
        'villain_4bet_pct', 'effective_stack_bb', 'nut_potential', 'domination_risk',
        'threeb_size_bb', 'ev_3bet', 'eq_in_3bet_pot', 'threeb_fold_equity_bb',
        'call_cost_bb', 'ev_flat', 'eq_in_srp',
        'ev_difference', 'recommendation', 'action_reason', 'confidence',
        'threeb_range_note', 'fold_equity_threshold', 'breakeven_fold_pct',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_aa_3bets_value():
    """AA should always 3-bet for value."""
    r = _f3b(hero_hand_rank_pct=0.99)
    assert r.recommendation == '3bet_value', f'AA should 3bet_value: {r.recommendation}'
    print(f'AA: {r.recommendation}')


def test_kk_3bets_value():
    """KK should 3-bet for value."""
    r = _f3b(hero_hand_rank_pct=0.98)
    assert r.recommendation == '3bet_value', f'KK should 3bet_value: {r.recommendation}'
    print(f'KK: {r.recommendation}')


def test_threeb_size_ip_smaller_than_oop():
    """IP 3-bet size (3x) should be smaller than OOP (3.5x)."""
    r_ip = _f3b(hero_is_ip=True)
    r_oop = _f3b(hero_is_ip=False)
    assert r_ip.threeb_size_bb < r_oop.threeb_size_bb, \
        f'IP 3b size {r_ip.threeb_size_bb} should < OOP {r_oop.threeb_size_bb}'
    print(f'3b size: IP={r_ip.threeb_size_bb:.1f}BB OOP={r_oop.threeb_size_bb:.1f}BB')


def test_threeb_size_larger_than_open():
    """3-bet must be larger than the open."""
    r = _f3b()
    assert r.threeb_size_bb > r.villain_open_bb, \
        f'3b {r.threeb_size_bb} should > open {r.villain_open_bb}'
    print(f'3b={r.threeb_size_bb:.1f}BB > open={r.villain_open_bb:.1f}BB')


def test_ev_difference_is_3bet_minus_flat():
    """ev_difference = ev_3bet - ev_flat."""
    r = _f3b()
    expected = round(r.ev_3bet - r.ev_flat, 2)
    assert abs(r.ev_difference - expected) < 0.01, \
        f'Diff: {r.ev_difference:.2f} vs computed {expected:.2f}'
    print(f'EV diff: {r.ev_difference:+.2f}BB')


def test_fold_equity_formula():
    """threeb_fold_equity = fold_pct * (open + 1.5)."""
    r = _f3b(villain_open_bb=2.5, villain_fold_to_3b=0.60)
    expected = 0.60 * (2.5 + 1.5)
    assert abs(r.threeb_fold_equity_bb - expected) < 0.10, \
        f'Fold eq: {r.threeb_fold_equity_bb:.2f} vs {expected:.2f}'
    print(f'Fold equity: {r.threeb_fold_equity_bb:.2f}BB')


def test_high_fold_favors_3bet():
    """High villain fold-to-3b should favor 3-bet."""
    r_low_fold = _f3b(villain_fold_to_3b=0.25)
    r_high_fold = _f3b(villain_fold_to_3b=0.80)
    assert r_high_fold.ev_3bet > r_low_fold.ev_3bet, \
        f'High fold EV {r_high_fold.ev_3bet:.2f} should > low fold {r_low_fold.ev_3bet:.2f}'
    print(f'3-bet EV: low_fold={r_low_fold.ev_3bet:+.2f}BB high_fold={r_high_fold.ev_3bet:+.2f}BB')


def test_ip_flat_better_than_oop_flat():
    """IP flatting should have higher EV than OOP flatting."""
    r_ip = _f3b(hero_is_ip=True, hero_hand_rank_pct=0.75)
    r_oop = _f3b(hero_is_ip=False, hero_hand_rank_pct=0.75)
    assert r_ip.ev_flat > r_oop.ev_flat, \
        f'IP flat EV {r_ip.ev_flat:+.2f} should > OOP {r_oop.ev_flat:+.2f}'
    print(f'Flat EV: IP={r_ip.ev_flat:+.2f}BB OOP={r_oop.ev_flat:+.2f}BB')


def test_recommendation_valid():
    valid = {'3bet_value', '3bet_bluff', 'flat', 'fold', '3bet_or_flat'}
    r = _f3b()
    assert r.recommendation in valid, f'Invalid recommendation: {r.recommendation}'
    print(f'Recommendation: {r.recommendation}')


def test_confidence_valid():
    valid = {'high', 'medium', 'low'}
    r = _f3b()
    assert r.confidence in valid, f'Invalid confidence: {r.confidence}'
    print(f'Confidence: {r.confidence}')


def test_tips_not_empty():
    r = _f3b()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_equity_in_3bet_pot_positive():
    r = _f3b()
    assert 0.20 <= r.eq_in_3bet_pot <= 0.85
    print(f'Equity in 3-bet pot: {r.eq_in_3bet_pot:.0%}')


def test_equity_in_srp_positive():
    r = _f3b()
    assert 0.20 <= r.eq_in_srp <= 0.80
    print(f'Equity in SRP: {r.eq_in_srp:.0%}')


def test_fold_equity_threshold_in_range():
    r = _f3b()
    assert 0.20 <= r.fold_equity_threshold <= 0.80
    print(f'Fold equity threshold: {r.fold_equity_threshold:.0%}')


def test_deep_stack_nut_potential_bonus():
    """Deep stacks with nut potential should give higher flat EV."""
    r_deep = _f3b(effective_stack_bb=200.0, nut_potential=0.80)
    r_shallow = _f3b(effective_stack_bb=40.0, nut_potential=0.20)
    assert r_deep.ev_flat > r_shallow.ev_flat, \
        f'Deep nut EV {r_deep.ev_flat:+.2f} should > shallow {r_shallow.ev_flat:+.2f}'
    print(f'Flat EV: deep/nut={r_deep.ev_flat:+.2f}BB shallow/no-nut={r_shallow.ev_flat:+.2f}BB')


def test_high_domination_risk_lowers_flat_ev():
    """High domination risk should lower flat EV."""
    r_low_dom = _f3b(domination_risk=0.05)
    r_high_dom = _f3b(domination_risk=0.80)
    assert r_low_dom.ev_flat > r_high_dom.ev_flat, \
        f'Low dom EV {r_low_dom.ev_flat:+.2f} should > high dom {r_high_dom.ev_flat:+.2f}'
    print(f'Flat EV: low_dom={r_low_dom.ev_flat:+.2f}BB high_dom={r_high_dom.ev_flat:+.2f}BB')


def test_premium_equity_is_higher():
    """Premium hands should have higher equity in both lines."""
    r_prem = _f3b(hero_hand_rank_pct=0.97)
    r_weak = _f3b(hero_hand_rank_pct=0.50)
    assert r_prem.eq_in_3bet_pot > r_weak.eq_in_3bet_pot
    print(f'3b pot equity: premium={r_prem.eq_in_3bet_pot:.0%} weak={r_weak.eq_in_3bet_pot:.0%}')


def test_call_cost_bb():
    """Call cost = open_bb - 1.0 (BB already invested 1BB)."""
    r = _f3b(villain_open_bb=3.0)
    assert abs(r.call_cost_bb - 2.0) < 0.05, f'Call cost: {r.call_cost_bb}'
    print(f'Call cost: {r.call_cost_bb:.1f}BB')


def test_verdict_contains_recommendation():
    r = _f3b()
    rec_up = r.recommendation.upper()
    assert rec_up in r.verdict, f'Verdict should contain recommendation: {r.verdict[:60]}'
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _f3b()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _f3b()
    line = f3b_one_liner(r)
    assert 'F3B' in line and '3b_ev=' in line and 'flat_ev=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_aa_3bets_value, test_kk_3bets_value,
        test_threeb_size_ip_smaller_than_oop, test_threeb_size_larger_than_open,
        test_ev_difference_is_3bet_minus_flat, test_fold_equity_formula,
        test_high_fold_favors_3bet, test_ip_flat_better_than_oop_flat,
        test_recommendation_valid, test_confidence_valid,
        test_tips_not_empty, test_equity_in_3bet_pot_positive,
        test_equity_in_srp_positive, test_fold_equity_threshold_in_range,
        test_deep_stack_nut_potential_bonus, test_high_domination_risk_lowers_flat_ev,
        test_premium_equity_is_higher, test_call_cost_bb,
        test_verdict_contains_recommendation, test_reasoning_not_empty, test_one_liner,
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
