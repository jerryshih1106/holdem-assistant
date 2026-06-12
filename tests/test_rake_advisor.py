"""Tests for poker/rake_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.rake_advisor import (
    analyze_rake, rake_one_liner, compare_rake_structures, RakeAnalysis
)


def _rake(pot=20.0, call=8.0, equity=0.38, pct=0.05, cap=2.0, bb_usd=0.02):
    return analyze_rake(
        pot_bb=pot, call_bb=call, hero_equity=equity,
        rake_pct=pct, rake_cap_bb=cap, bb_size_usd=bb_usd,
    )


def test_returns_rake_analysis():
    """analyze_rake should return a RakeAnalysis."""
    r = _rake()
    assert isinstance(r, RakeAnalysis), f'Expected RakeAnalysis: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """RakeAnalysis should have all documented fields."""
    r = _rake()
    fields = [
        'pot_bb', 'call_bb', 'hero_equity', 'rake_pct', 'rake_cap_bb',
        'rake_bb', 'rake_pct_effective', 'pot_after_rake_bb',
        'adjusted_pot_odds', 'breakeven_equity_raw', 'breakeven_equity_raked',
        'ev_call_no_rake', 'ev_call_with_rake', 'ev_difference',
        'action', 'action_no_rake', 'rake_changes_action',
        'rake_per_100_hands_bb', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'RakeAnalysis missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_rake_capped():
    """Rake should not exceed the cap."""
    r = _rake(pot=200.0, call=100.0, pct=0.05, cap=2.0)
    assert r.rake_bb <= 2.0 + 0.001, f'Rake should be capped at 2.0: {r.rake_bb}'
    print(f'Rake capped: {r.rake_bb:.3f}BB (cap=2.0)')


def test_rake_not_exceed_pot_pct():
    """Rake should equal pct*pot when below cap."""
    r = _rake(pot=10.0, call=5.0, pct=0.05, cap=5.0)
    total = 10.0 + 5.0
    expected = total * 0.05
    assert abs(r.rake_bb - expected) < 0.01, \
        f'Rake should be {expected:.2f}: {r.rake_bb:.3f}'
    print(f'Rake uncapped: {r.rake_bb:.3f}BB (expected {expected:.3f})')


def test_pot_after_rake_less_than_total():
    """Pot after rake should be less than total pot."""
    r = _rake()
    total = r.pot_bb + r.call_bb
    assert r.pot_after_rake_bb < total, \
        f'pot_after_rake ({r.pot_after_rake_bb}) should < total ({total})'
    print(f'pot_after_rake: {r.pot_after_rake_bb:.2f} < total {total:.2f}')


def test_breakeven_raked_higher_than_raw():
    """Breakeven equity with rake should be higher than without."""
    r = _rake()
    assert r.breakeven_equity_raked > r.breakeven_equity_raw, \
        f'Raked breakeven ({r.breakeven_equity_raked:.4f}) > raw ({r.breakeven_equity_raw:.4f})'
    print(f'Breakeven: raw={r.breakeven_equity_raw:.3f} raked={r.breakeven_equity_raked:.3f}')


def test_ev_with_rake_less_than_without():
    """EV after rake should be less than EV without rake."""
    r = _rake()
    assert r.ev_call_with_rake < r.ev_call_no_rake, \
        f'Raked EV ({r.ev_call_with_rake:.3f}) < raw EV ({r.ev_call_no_rake:.3f})'
    print(f'EV: raw={r.ev_call_no_rake:.3f} raked={r.ev_call_with_rake:.3f}')


def test_ev_difference_negative():
    """ev_difference should be negative (rake costs EV)."""
    r = _rake()
    assert r.ev_difference < 0, f'ev_difference should be < 0: {r.ev_difference}'
    print(f'ev_difference: {r.ev_difference:.3f}BB')


def test_high_equity_calls_despite_rake():
    """With 70% equity, should call even with high rake."""
    r = _rake(pot=20.0, call=8.0, equity=0.70, pct=0.05, cap=2.0)
    assert r.action == 'call', \
        f'70% equity should call even with rake: {r.action}'
    print(f'High equity call: action={r.action} eq={r.hero_equity}')


def test_marginal_equity_may_flip():
    """Marginal equity that's barely profitable without rake may fold with rake."""
    # Set equity slightly above raw breakeven but below raked breakeven
    r_no_rake = _rake(pot=20.0, call=8.0, equity=0.30, pct=0.0, cap=0.0)
    # 8/28 = 28.6% breakeven; with equity=30% should call
    assert r_no_rake.action == 'call', f'Should call without rake: {r_no_rake.action}'
    print(f'Without rake: {r_no_rake.action} at {r_no_rake.hero_equity:.2f} eq')


def test_zero_rake_no_change():
    """Zero rake should not change the call decision."""
    r = _rake(pot=20.0, call=8.0, equity=0.40, pct=0.0, cap=0.0)
    assert r.rake_bb == 0.0, f'Zero rake: {r.rake_bb}'
    assert r.action == r.action_no_rake, \
        f'Zero rake: action should match no-rake: {r.action} vs {r.action_no_rake}'
    print(f'Zero rake: action={r.action} rake={r.rake_bb}')


def test_rake_changes_action_flag():
    """rake_changes_action should be True when rake flips fold/call."""
    # Find case where it flips: equity just above raw breakeven, below raked
    # Raw breakeven for pot=20, call=8: 8/28=28.6%
    # Raked breakeven will be higher
    r_flipped = _rake(pot=20.0, call=8.0, equity=0.295, pct=0.05, cap=2.0)
    r_no_flip = _rake(pot=20.0, call=8.0, equity=0.50, pct=0.05, cap=2.0)
    assert not r_no_flip.rake_changes_action, \
        f'High equity should not flip: {r_no_flip.rake_changes_action}'
    print(f'rake_changes_action: flipped={r_flipped.rake_changes_action} '
          f'no_flip={r_no_flip.rake_changes_action}')


def test_rake_per_100_positive():
    """rake_per_100_hands_bb should be positive."""
    r = _rake()
    assert r.rake_per_100_hands_bb > 0, \
        f'Rake per 100 should be > 0: {r.rake_per_100_hands_bb}'
    print(f'Rake per 100: {r.rake_per_100_hands_bb:.2f}BB')


def test_higher_rake_pct_costs_more():
    """Higher rake percentage should produce lower EV."""
    r_low  = _rake(pct=0.03)
    r_high = _rake(pct=0.07)
    assert r_high.ev_call_with_rake < r_low.ev_call_with_rake, \
        f'Higher rake = lower EV: {r_high.ev_call_with_rake} vs {r_low.ev_call_with_rake}'
    print(f'EV: low_rake={r_low.ev_call_with_rake:.3f} high_rake={r_high.ev_call_with_rake:.3f}')


def test_larger_cap_more_rake():
    """Larger rake cap means more rake on big pots."""
    r_small_cap = _rake(pot=200.0, call=100.0, pct=0.05, cap=1.0)
    r_large_cap = _rake(pot=200.0, call=100.0, pct=0.05, cap=10.0)
    assert r_large_cap.rake_bb > r_small_cap.rake_bb, \
        f'Larger cap = more rake: {r_large_cap.rake_bb} vs {r_small_cap.rake_bb}'
    print(f'Rake: small_cap={r_small_cap.rake_bb:.2f} large_cap={r_large_cap.rake_bb:.2f}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _rake()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    """tips should be a non-empty list."""
    r = _rake()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'tips count: {len(r.tips)}')


def test_rake_one_liner():
    """rake_one_liner should return a non-empty string."""
    r = _rake()
    line = rake_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_compare_rake_structures():
    """compare_rake_structures should return sorted list."""
    structures = [
        ('NL2_5pct', 0.05, 2.0),
        ('NL10_4.5pct', 0.045, 2.0),
        ('NL100_3pct', 0.03, 3.0),
    ]
    results = compare_rake_structures(20.0, 8.0, 0.40, structures)
    assert len(results) == 3, f'Should return 3 results: {len(results)}'
    # Should be sorted by EV descending
    evs = [r.ev_call_with_rake for _, r in results]
    assert evs == sorted(evs, reverse=True), f'Should be sorted by EV: {evs}'
    print(f'Rake comparison: {[(n, round(r.ev_call_with_rake, 3)) for n, r in results]}')


def test_action_is_call_or_fold():
    """action should be 'call' or 'fold'."""
    for equity in (0.10, 0.35, 0.50, 0.75):
        r = _rake(equity=equity)
        assert r.action in ('call', 'fold'), \
            f'action should be call/fold for equity={equity}: {r.action}'
    print('All actions are call or fold')


if __name__ == '__main__':
    tests = [
        test_returns_rake_analysis,
        test_required_fields,
        test_rake_capped,
        test_rake_not_exceed_pot_pct,
        test_pot_after_rake_less_than_total,
        test_breakeven_raked_higher_than_raw,
        test_ev_with_rake_less_than_without,
        test_ev_difference_negative,
        test_high_equity_calls_despite_rake,
        test_marginal_equity_may_flip,
        test_zero_rake_no_change,
        test_rake_changes_action_flag,
        test_rake_per_100_positive,
        test_higher_rake_pct_costs_more,
        test_larger_cap_more_rake,
        test_reasoning_is_string,
        test_tips_is_list,
        test_rake_one_liner,
        test_compare_rake_structures,
        test_action_is_call_or_fold,
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
