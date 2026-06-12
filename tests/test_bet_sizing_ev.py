"""Tests for poker/bet_sizing_ev.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bet_sizing_ev import compare_bet_sizes, sizing_ev_summary, sizing_ev_table, SizingEVResult, SizingEV


def test_result_has_required_fields():
    """SizingEVResult should have all expected fields."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70)
    required = ['options', 'optimal', 'check_ev', 'ev_loss_from_check', 'pot_bb', 'hero_equity']
    for field in required:
        assert hasattr(r, field), f'SizingEVResult missing field: {field}'
    print('All fields present')


def test_options_are_list_of_sizing_ev():
    """options should be a list of SizingEV objects."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70)
    assert isinstance(r.options, list) and len(r.options) >= 3, \
        f'options should have >= 3 items: {len(r.options)}'
    for o in r.options:
        assert isinstance(o, SizingEV), f'Each option should be SizingEV: {type(o)}'
    print(f'options count: {len(r.options)}')


def test_exactly_one_optimal():
    """Exactly one option should have is_optimal=True."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70)
    optimal_count = sum(1 for o in r.options if o.is_optimal)
    assert optimal_count == 1, f'Exactly 1 option should be optimal: {optimal_count}'
    print(f'Optimal: {r.optimal.label} (ev={r.optimal.ev_bb:.2f})')


def test_optimal_has_highest_ev():
    """The optimal option should have the highest ev_bb among all options."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70)
    max_ev = max(o.ev_bb for o in r.options)
    assert abs(r.optimal.ev_bb - max_ev) < 0.01, \
        f'Optimal EV {r.optimal.ev_bb:.2f} should = max {max_ev:.2f}'
    print(f'Optimal EV: {r.optimal.ev_bb:.2f} == max({max_ev:.2f})')


def test_check_ev_formula():
    """check_ev should equal equity * pot_bb."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70, base_fold_freq=0.50)
    expected = 0.70 * 10
    assert abs(r.check_ev - expected) < 0.5, \
        f'check_ev should ~= equity*pot {expected:.1f}: {r.check_ev:.1f}'
    print(f'check_ev: {r.check_ev:.1f} (equity*pot={expected:.1f})')


def test_ev_loss_from_check_positive_when_betting_is_better():
    """ev_loss_from_check should be positive when best bet exceeds check EV."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70, base_fold_freq=0.50)
    assert r.ev_loss_from_check >= 0, \
        f'ev_loss_from_check should be >= 0 when betting is best: {r.ev_loss_from_check}'
    print(f'ev_loss_from_check: {r.ev_loss_from_check:.2f} BB')


def test_high_equity_prefers_larger_bet():
    """With high equity and sticky villain, larger bets should have higher EV."""
    r_low  = compare_bet_sizes(pot_bb=10, hero_equity=0.40, base_fold_freq=0.30)
    r_high = compare_bet_sizes(pot_bb=10, hero_equity=0.90, base_fold_freq=0.30)
    # Higher equity → bigger bet preferred
    assert r_high.optimal.pct >= r_low.optimal.pct - 0.20, \
        f'High equity prefers >= bet: high={r_high.optimal.pct:.0%} low={r_low.optimal.pct:.0%}'
    print(f'Optimal pct: eq=40%→{r_low.optimal.pct:.0%}  eq=90%→{r_high.optimal.pct:.0%}')


def test_sizing_ev_fields():
    """Each SizingEV should have all required fields."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70)
    for o in r.options:
        for field in ['label', 'pct', 'bet_bb', 'fold_freq', 'ev_bb', 'ev_vs_check', 'is_optimal']:
            assert hasattr(o, field), f'SizingEV missing field: {field}'
    print(f'SizingEV fields OK for {len(r.options)} options')


def test_sizing_ev_summary_returns_string():
    """sizing_ev_summary should return a non-empty string."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70)
    s = sizing_ev_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'sizing_ev_summary should be non-empty: {repr(s)[:50]}'
    print(f'sizing_ev_summary length: {len(s)}')


def test_sizing_ev_table_returns_string():
    """sizing_ev_table should return a multi-line string."""
    r = compare_bet_sizes(pot_bb=10, hero_equity=0.70)
    s = sizing_ev_table(r)
    assert isinstance(s, str) and len(s) > 20, \
        f'sizing_ev_table should be non-empty: {repr(s)[:50]}'
    print(f'sizing_ev_table length: {len(s)}')


if __name__ == '__main__':
    tests = [
        test_result_has_required_fields,
        test_options_are_list_of_sizing_ev,
        test_exactly_one_optimal,
        test_optimal_has_highest_ev,
        test_check_ev_formula,
        test_ev_loss_from_check_positive_when_betting_is_better,
        test_high_equity_prefers_larger_bet,
        test_sizing_ev_fields,
        test_sizing_ev_summary_returns_string,
        test_sizing_ev_table_returns_string,
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
