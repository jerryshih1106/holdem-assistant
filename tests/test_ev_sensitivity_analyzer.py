"""Tests for poker/ev_sensitivity_analyzer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.ev_sensitivity_analyzer import analyze_ev_sensitivity, EVSensitivityResult, evs_one_liner


def _evs(**kw):
    defaults = dict(
        pot_bb=20.0, bet_bb=15.0, hero_equity=0.35, fold_equity=0.40,
        call_bb=0.0, action='bet',
    )
    defaults.update(kw)
    return analyze_ev_sensitivity(**defaults)


def test_returns_correct_type():
    r = _evs()
    assert isinstance(r, EVSensitivityResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _evs()
    fields = [
        'action', 'pot_bb', 'bet_bb', 'call_bb', 'hero_equity', 'fold_equity',
        'base_ev', 'decision', 'sensitivity_equity', 'sensitivity_fold_eq',
        'sensitivity_pot', 'breakeven_equity', 'breakeven_fold_eq',
        'most_important_factor', 'robustness', 'equity_margin', 'fold_eq_margin',
        'ev_equity_low', 'ev_equity_high', 'ev_fold_eq_low', 'ev_fold_eq_high',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_positive_ev_bets_recommend_betting():
    """High equity + fold equity -> positive EV -> bet/raise."""
    r = _evs(hero_equity=0.60, fold_equity=0.50)
    assert r.base_ev > 0, f'Expected positive EV: {r.base_ev}'
    assert r.decision in ('bet/raise',), f'Expected bet/raise: {r.decision}'
    print(f'Positive EV bet: {r.base_ev:+.2f}BB decision={r.decision}')


def test_negative_ev_bets_recommend_fold():
    """Very low equity + low fold equity -> negative EV."""
    r = _evs(hero_equity=0.15, fold_equity=0.10)
    assert r.base_ev < 0, f'Expected negative EV: {r.base_ev}'
    assert r.decision in ('check/fold',), f'Expected check/fold: {r.decision}'
    print(f'Negative EV: {r.base_ev:+.2f}BB decision={r.decision}')


def test_call_ev_correct():
    """EV of call = equity * (pot+call) - call."""
    pot, call, eq = 20.0, 10.0, 0.40
    r = analyze_ev_sensitivity(pot_bb=pot, call_bb=call, hero_equity=eq, action='call')
    expected_ev = eq * (pot + call) - call
    assert abs(r.base_ev - expected_ev) < 0.01, \
        f'Call EV mismatch: got {r.base_ev:.4f} expected {expected_ev:.4f}'
    print(f'Call EV correct: {r.base_ev:+.3f}BB (expected {expected_ev:+.3f})')


def test_breakeven_equity_is_correct():
    """At breakeven equity, EV should be ~0."""
    r = _evs(pot_bb=30.0, bet_bb=20.0, fold_equity=0.35)
    # Verify breakeven equity gives near-zero EV
    be_eq = r.breakeven_equity
    from poker.ev_sensitivity_analyzer import _bet_ev
    ev_at_be = _bet_ev(30.0, 20.0, be_eq, 0.35)
    assert abs(ev_at_be) < 0.05, f'BE equity EV not ~0: {ev_at_be:.4f} (be_eq={be_eq:.3f})'
    print(f'BE equity={be_eq:.3f}, EV at BE={ev_at_be:.4f}')


def test_sensitivity_equity_positive():
    """More equity always improves EV for bet/call."""
    r = _evs()
    assert r.sensitivity_equity > 0, f'Equity sensitivity should be positive: {r.sensitivity_equity}'
    print(f'Equity sensitivity: +{r.sensitivity_equity:.3f}BB per 1%')


def test_sensitivity_fold_eq_positive_when_unprofitable_called():
    """More fold equity helps when called EV is negative."""
    r = _evs(hero_equity=0.20, fold_equity=0.40, pot_bb=20.0, bet_bb=15.0)
    # With low equity, called EV = 0.20*(50) - 15 = -5, so more fold eq helps
    assert r.sensitivity_fold_eq > 0, \
        f'Fold eq sensitivity should be positive when called EV<0: {r.sensitivity_fold_eq}'
    print(f'FE sensitivity: +{r.sensitivity_fold_eq:.3f}BB per 1%')


def test_robustness_robust_when_large_margin():
    """Large margin above breakeven -> robust."""
    r = _evs(hero_equity=0.70, fold_equity=0.70)
    assert r.robustness == 'robust', f'Expected robust: {r.robustness} (margin={r.equity_margin:.2%})'
    print(f'Robust: margin={r.equity_margin:.1%}')


def test_robustness_fragile_when_small_margin():
    """Very thin margin (hero barely above breakeven) -> fragile/marginal."""
    # fold_eq=0.10, pot=20, bet=15: BE_equity = (0.9*15 - 0.1*20)/(0.9*50) = 11.5/45 = 0.256
    # hero_equity=0.26 -> margin = 0.004 (0.4%) -> fragile
    r = _evs(hero_equity=0.26, fold_equity=0.10, pot_bb=20.0, bet_bb=15.0)
    assert r.robustness in ('fragile', 'marginal'), \
        f'Expected fragile/marginal with thin margins: {r.robustness} (margin={r.equity_margin:.2%})'
    print(f'Fragile/marginal: {r.robustness} (margin={r.equity_margin:.2%})')


def test_most_important_factor_valid():
    r = _evs()
    assert r.most_important_factor in ('equity', 'fold_equity', 'pot')
    print(f'Most important: {r.most_important_factor}')


def test_equity_margin_correct():
    """equity_margin = hero_equity - breakeven_equity."""
    r = _evs()
    expected = round(r.hero_equity - r.breakeven_equity, 4)
    assert abs(r.equity_margin - expected) < 0.001, \
        f'Equity margin: {r.equity_margin:.4f} vs expected {expected:.4f}'
    print(f'Equity margin: {r.equity_margin:.3f}')


def test_ev_scenarios_ordered():
    """EV at equity+5% should exceed EV at equity-5%."""
    r = _evs()
    assert r.ev_equity_high >= r.ev_equity_low, \
        f'Higher equity should give higher EV: {r.ev_equity_high} vs {r.ev_equity_low}'
    print(f'EV scenarios: eq-5%={r.ev_equity_low:+.2f} base={r.base_ev:+.2f} eq+5%={r.ev_equity_high:+.2f}')


def test_fold_eq_scenarios_ordered():
    """EV at fold_eq+5% should exceed EV at fold_eq-5% when called EV < 0."""
    r = _evs(hero_equity=0.20)  # low equity: called EV is negative
    if r.action != 'call':
        assert r.ev_fold_eq_high >= r.ev_fold_eq_low, \
            f'Higher FE should give higher EV: {r.ev_fold_eq_high} vs {r.ev_fold_eq_low}'
    print(f'FE scenarios: fe-5%={r.ev_fold_eq_low:+.2f} base={r.base_ev:+.2f} fe+5%={r.ev_fold_eq_high:+.2f}')


def test_call_action_ignores_fold_equity():
    """For calls, fold equity sensitivity should be 0."""
    r = _evs(action='call', call_bb=10.0, bet_bb=0.0)
    assert r.sensitivity_fold_eq == 0.0, \
        f'Call fold-eq sensitivity should be 0: {r.sensitivity_fold_eq}'
    print(f'Call FE sensitivity=0: confirmed')


def test_call_decision_when_positive_ev():
    """Positive-EV call should recommend call."""
    r = _evs(action='call', call_bb=10.0, hero_equity=0.50, pot_bb=20.0)
    assert r.decision == 'call', f'Expected call: {r.decision}'
    print(f'Call decision: {r.decision} (EV={r.base_ev:+.2f}BB)')


def test_breakeven_equity_call():
    """BE equity for call = call/(pot+call)."""
    pot, call = 30.0, 10.0
    r = _evs(action='call', pot_bb=pot, call_bb=call, hero_equity=0.50)
    expected_be = call / (pot + call)
    assert abs(r.breakeven_equity - expected_be) < 0.001, \
        f'BE equity for call: {r.breakeven_equity:.4f} vs {expected_be:.4f}'
    print(f'Call BE equity={r.breakeven_equity:.3f} (expected={expected_be:.3f})')


def test_tips_not_empty():
    r = _evs()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_not_empty():
    r = _evs()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _evs()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _evs()
    line = evs_one_liner(r)
    assert 'EVS' in line and 'ev=' in line and 'key_factor=' in line and 'robustness=' in line
    print(f'one_liner: {line}')


def test_pot_only_bet_is_profitable_bluff():
    """Pure bluff with fold_eq=1.0 should have EV = pot."""
    r = _evs(hero_equity=0.0, fold_equity=1.0, pot_bb=20.0, bet_bb=15.0)
    assert abs(r.base_ev - 20.0) < 0.01, f'Pure fold EV should = pot: {r.base_ev}'
    print(f'Pure bluff (fe=100%): EV={r.base_ev:.2f}BB (expected 20.0)')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_positive_ev_bets_recommend_betting, test_negative_ev_bets_recommend_fold,
        test_call_ev_correct, test_breakeven_equity_is_correct,
        test_sensitivity_equity_positive, test_sensitivity_fold_eq_positive_when_unprofitable_called,
        test_robustness_robust_when_large_margin, test_robustness_fragile_when_small_margin,
        test_most_important_factor_valid, test_equity_margin_correct,
        test_ev_scenarios_ordered, test_fold_eq_scenarios_ordered,
        test_call_action_ignores_fold_equity, test_call_decision_when_positive_ev,
        test_breakeven_equity_call, test_tips_not_empty,
        test_verdict_not_empty, test_reasoning_not_empty,
        test_one_liner, test_pot_only_bet_is_profitable_bluff,
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
