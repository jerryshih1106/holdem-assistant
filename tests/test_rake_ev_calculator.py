"""Tests for poker/rake_ev_calculator.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.rake_ev_calculator import calc_rake_ev, RakeEVResult, rake_ev_one_liner


def _r(**kw):
    defaults = dict(
        pot_bb=15.0, call_bb=8.0, hero_equity=0.58,
        rake_structure='nl100', hero_pos='IP', street='flop',
        n_opponents=1, rakeback_pct=0.0,
    )
    defaults.update(kw)
    return calc_rake_ev(**defaults)


def test_returns_correct_type():
    r = _r()
    assert isinstance(r, RakeEVResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _r()
    fields = [
        'pot_bb', 'call_bb', 'hero_equity', 'rake_structure', 'hero_pos', 'street',
        'n_opponents', 'rakeback_pct', 'rake_pct', 'rake_cap_bb', 'pot_after_call_bb',
        'gross_rake_bb', 'effective_rake_pct', 'rakeback_bb', 'net_rake_bb',
        'hero_rake_share_bb', 'gross_ev_bb', 'rake_adjusted_ev_bb', 'ev_loss_to_rake_bb',
        'break_even_equity_gross', 'break_even_equity_adjusted', 'action', 'verdict',
        'rake_severity', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_rake_reduces_ev():
    """Rake-adjusted EV must be <= gross EV."""
    r = _r()
    assert r.rake_adjusted_ev_bb <= r.gross_ev_bb, \
        f'Adjusted EV should be <= gross: {r.rake_adjusted_ev_bb:.2f} vs {r.gross_ev_bb:.2f}'
    print(f'Gross EV={r.gross_ev_bb:.2f}BB Adjusted={r.rake_adjusted_ev_bb:.2f}BB')


def test_zero_rake_structure():
    """Zero rake → adjusted EV == gross EV."""
    r = _r(rake_structure='zero_rake')
    assert abs(r.rake_adjusted_ev_bb - r.gross_ev_bb) < 0.01, \
        f'Zero rake should have equal EVs: {r.rake_adjusted_ev_bb:.2f} vs {r.gross_ev_bb:.2f}'
    print(f'Zero rake: gross={r.gross_ev_bb:.2f} adj={r.rake_adjusted_ev_bb:.2f}')


def test_higher_rake_structure_more_expensive():
    """Micro stakes has higher effective rake than high stakes."""
    r_micro = _r(rake_structure='nl10')
    r_mid = _r(rake_structure='nl500')
    assert r_micro.net_rake_bb >= r_mid.net_rake_bb, \
        f'NL10 rake >= NL500: {r_micro.net_rake_bb:.2f} vs {r_mid.net_rake_bb:.2f}'
    print(f'Rake: NL10={r_micro.net_rake_bb:.2f}BB NL500={r_mid.net_rake_bb:.2f}BB')


def test_gross_ev_formula():
    """Gross EV = equity × pot_after - call."""
    r = _r(pot_bb=20.0, call_bb=10.0, hero_equity=0.60)
    pot_after = 20.0 + 2 * 10.0  # 40BB
    expected_gross = round(0.60 * pot_after - 10.0, 3)
    assert abs(r.gross_ev_bb - expected_gross) < 0.1, \
        f'Gross EV: {r.gross_ev_bb:.3f} vs expected {expected_gross:.3f}'
    print(f'Gross EV: {r.gross_ev_bb:.2f}BB (expected {expected_gross:.2f}BB)')


def test_break_even_adjusted_higher_than_gross():
    """With rake, breakeven equity requirement increases."""
    r = _r()
    if r.call_bb > 0:
        assert r.break_even_equity_adjusted >= r.break_even_equity_gross, \
            f'Adj breakeven >= gross: {r.break_even_equity_adjusted:.0%} vs {r.break_even_equity_gross:.0%}'
    print(f'Breakeven: gross={r.break_even_equity_gross:.0%} adj={r.break_even_equity_adjusted:.0%}')


def test_rakeback_reduces_net_rake():
    """Rakeback reduces the effective rake cost."""
    r_no_rb = _r(rakeback_pct=0.0)
    r_rb = _r(rakeback_pct=0.30)
    assert r_rb.net_rake_bb <= r_no_rb.net_rake_bb, \
        f'Rakeback should reduce net rake: {r_rb.net_rake_bb:.2f} vs {r_no_rb.net_rake_bb:.2f}'
    print(f'Net rake: no_rb={r_no_rb.net_rake_bb:.2f}BB 30%_rb={r_rb.net_rake_bb:.2f}BB')


def test_rakeback_improves_adjusted_ev():
    """Rakeback improves rake-adjusted EV."""
    r_no_rb = _r(rakeback_pct=0.0)
    r_rb = _r(rakeback_pct=0.30)
    assert r_rb.rake_adjusted_ev_bb >= r_no_rb.rake_adjusted_ev_bb, \
        f'Rakeback should improve adj EV: {r_rb.rake_adjusted_ev_bb:.2f} vs {r_no_rb.rake_adjusted_ev_bb:.2f}'
    print(f'Adj EV: no_rb={r_no_rb.rake_adjusted_ev_bb:.2f}BB 30%_rb={r_rb.rake_adjusted_ev_bb:.2f}BB')


def test_action_is_valid():
    valid = {'call', 'call_marginal', 'fold', 'no_rake_call', 'call_if_rakeback'}
    r = _r()
    assert r.action in valid, f'Invalid action: {r.action}'
    print(f'Action: {r.action}')


def test_strong_equity_calls():
    """Strong equity always calls (70% equity with any normal rake)."""
    r = _r(hero_equity=0.70, pot_bb=20.0, call_bb=8.0)
    assert r.action in ('call', 'call_marginal'), \
        f'70% equity should call: {r.action} adj_ev={r.rake_adjusted_ev_bb:.2f}'
    print(f'Strong equity: {r.action} adj_ev={r.rake_adjusted_ev_bb:.2f}BB')


def test_bad_equity_folds():
    """Bad equity folds even without rake."""
    r = _r(hero_equity=0.20, pot_bb=5.0, call_bb=8.0)
    assert r.action in ('fold', 'call_if_rakeback'), \
        f'20% equity bad pot odds should fold: {r.action}'
    print(f'Bad equity: {r.action} adj_ev={r.rake_adjusted_ev_bb:.2f}BB')


def test_rake_severity_is_valid():
    valid = {'negligible', 'minor', 'significant', 'severe'}
    r = _r()
    assert r.rake_severity in valid, f'Invalid severity: {r.rake_severity}'
    print(f'Severity: {r.rake_severity}')


def test_live_1_2_higher_effective_rake():
    """Live $1/$2 has very high effective rake rate."""
    r_live = _r(rake_structure='live_1_2')
    r_nl100 = _r(rake_structure='nl100')
    assert r_live.effective_rake_pct >= r_nl100.effective_rake_pct, \
        f'Live rake should be >= NL100: {r_live.effective_rake_pct:.1%} vs {r_nl100.effective_rake_pct:.1%}'
    print(f'Effective rake: live_1_2={r_live.effective_rake_pct:.1%} nl100={r_nl100.effective_rake_pct:.1%}')


def test_rake_cap_enforced():
    """Rake never exceeds the cap."""
    r = _r(pot_bb=100.0, call_bb=50.0, rake_structure='nl100')
    assert r.gross_rake_bb <= 3.0, f'NL100 rake should not exceed 3BB: {r.gross_rake_bb:.2f}'
    print(f'NL100 rake capped at: {r.gross_rake_bb:.2f}BB (cap=3BB)')


def test_no_call_case():
    """When call_bb=0 (free check), action should be no_rake_call."""
    r = _r(call_bb=0.0)
    assert r.action == 'no_rake_call', f'Free check should be no_rake_call: {r.action}'
    print(f'Free check: {r.action}')


def test_ev_loss_is_nonnegative():
    """EV loss to rake must be non-negative."""
    r = _r()
    assert r.ev_loss_to_rake_bb >= 0, f'EV loss should be >= 0: {r.ev_loss_to_rake_bb}'
    print(f'EV loss to rake: {r.ev_loss_to_rake_bb:.2f}BB')


def test_all_rake_structures_work():
    for struct in ['nl2', 'nl10', 'nl25', 'nl50', 'nl100', 'nl200', 'nl500', 'live_1_2', 'live_2_5', 'zero_rake']:
        r = _r(rake_structure=struct)
        assert r.action in {'call', 'call_marginal', 'fold', 'no_rake_call', 'call_if_rakeback'}
    print('All rake structures produce valid actions')


def test_larger_pot_hits_cap_sooner():
    """Larger pot: effective rake % decreases once cap is hit."""
    r_small = _r(pot_bb=5.0, call_bb=3.0, rake_structure='nl100')
    r_large = _r(pot_bb=100.0, call_bb=50.0, rake_structure='nl100')
    # Large pot hits cap → lower effective rake %
    assert r_large.effective_rake_pct <= r_small.effective_rake_pct, \
        f'Large pot effective rake <= small: {r_large.effective_rake_pct:.1%} vs {r_small.effective_rake_pct:.1%}'
    print(f'Eff rake: small_pot={r_small.effective_rake_pct:.1%} large_pot={r_large.effective_rake_pct:.1%}')


def test_tips_not_empty():
    r = _r()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_verdict_not_empty():
    r = _r()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:60]}...')


def test_one_liner():
    r = _r()
    line = rake_ev_one_liner(r)
    assert 'RAKE' in line and 'gross_ev=' in line and 'rake=' in line and 'sev=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_rake_reduces_ev, test_zero_rake_structure,
        test_higher_rake_structure_more_expensive, test_gross_ev_formula,
        test_break_even_adjusted_higher_than_gross, test_rakeback_reduces_net_rake,
        test_rakeback_improves_adjusted_ev, test_action_is_valid,
        test_strong_equity_calls, test_bad_equity_folds,
        test_rake_severity_is_valid, test_live_1_2_higher_effective_rake,
        test_rake_cap_enforced, test_no_call_case,
        test_ev_loss_is_nonnegative, test_all_rake_structures_work,
        test_larger_pot_hits_cap_sooner, test_tips_not_empty,
        test_verdict_not_empty, test_one_liner,
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
