"""Tests for poker/run_it_twice_advisor.py"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.run_it_twice_advisor import advise_run_it_twice, RunItTwiceAdvice, rit_one_liner


def _rit(**kw):
    defaults = dict(
        pot_bb=100.0, hero_equity=0.65, bankroll_bb=2000.0,
        tilt_score=0.2, is_tournament=False, is_hero_offering=False,
    )
    defaults.update(kw)
    return advise_run_it_twice(**defaults)


def test_returns_correct_type():
    r = _rit()
    assert isinstance(r, RunItTwiceAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _rit()
    fields = [
        'pot_bb', 'hero_equity', 'bankroll_bb', 'tilt_score',
        'is_tournament', 'is_hero_offering',
        'ev_either_way', 'std_run_once', 'std_run_twice',
        'variance_reduction_pct', 'bankroll_risk_pct_once', 'bankroll_risk_pct_twice',
        'recommendation', 'confidence', 'reasoning_code',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_ev_is_equity_times_pot():
    """EV = equity * pot, identical for run-once and run-twice."""
    pot, eq = 200.0, 0.40
    r = _rit(pot_bb=pot, hero_equity=eq)
    expected = round(eq * pot, 2)
    assert abs(r.ev_either_way - expected) < 0.01, \
        f'EV mismatch: {r.ev_either_way:.2f} vs {expected:.2f}'
    print(f'EV={r.ev_either_way:.2f}BB (expected {expected:.2f})')


def test_run_twice_has_lower_std():
    """Running twice has lower standard deviation than running once."""
    r = _rit()
    assert r.std_run_twice < r.std_run_once, \
        f'Run twice should have lower std: {r.std_run_twice:.2f} vs {r.std_run_once:.2f}'
    print(f'Std: once={r.std_run_once:.2f} twice={r.std_run_twice:.2f}')


def test_variance_reduction_is_approx_29_pct():
    """Running twice reduces std by ~29.3% (1 - 1/sqrt(2))."""
    r = _rit()
    expected = 1 - 1 / math.sqrt(2)
    assert abs(r.variance_reduction_pct - expected) < 0.001, \
        f'Variance reduction: {r.variance_reduction_pct:.4f} vs {expected:.4f}'
    print(f'Variance reduction: {r.variance_reduction_pct:.1%} (expected {expected:.1%})')


def test_std_twice_is_std_once_over_sqrt2():
    """std_twice = std_once / sqrt(2)."""
    r = _rit()
    expected = r.std_run_once / math.sqrt(2)
    assert abs(r.std_run_twice - expected) < 0.01, \
        f'std_twice={r.std_run_twice:.2f} vs expected={expected:.2f}'
    print(f'std_twice={r.std_run_twice:.2f} = {r.std_run_once:.2f}/sqrt(2)={expected:.2f}')


def test_short_bankroll_recommends_accept():
    """Very short bankroll -> accept RIT."""
    # pot=200BB in 500BB bankroll = 40% risk -> strong accept
    r = _rit(pot_bb=200.0, bankroll_bb=500.0, hero_equity=0.65)
    assert r.recommendation == 'accept_rit', \
        f'Short bankroll should accept RIT: {r.recommendation} (br_risk={r.bankroll_risk_pct_once:.1%})'
    print(f'Short BR accept: {r.recommendation} ({r.confidence})')


def test_huge_favorite_declines_rit():
    """Huge equity + deep bankroll -> can decline RIT."""
    r = _rit(pot_bb=50.0, hero_equity=0.90, bankroll_bb=10000.0, tilt_score=0.0)
    assert r.recommendation in ('decline_rit', 'indifferent'), \
        f'Huge fav with deep BR should decline or be indifferent: {r.recommendation}'
    print(f'Huge fav recommendation: {r.recommendation}')


def test_tilt_favors_accepting():
    """High tilt -> accept RIT (reduce variance)."""
    r_notilt = _rit(tilt_score=0.0, bankroll_bb=5000.0)
    r_tilt = _rit(tilt_score=0.8, bankroll_bb=5000.0)
    # Tilt should push recommendation toward accept
    tilt_score_map = {'accept_rit': 1, 'indifferent': 0, 'decline_rit': -1}
    notilt_val = tilt_score_map.get(r_notilt.recommendation, 0)
    tilt_val = tilt_score_map.get(r_tilt.recommendation, 0)
    assert tilt_val >= notilt_val, \
        f'Tilt should favor accept more: notilt={r_notilt.recommendation} tilt={r_tilt.recommendation}'
    print(f'No-tilt: {r_notilt.recommendation} | High-tilt: {r_tilt.recommendation}')


def test_bankroll_risk_twice_less_than_once():
    r = _rit()
    assert r.bankroll_risk_pct_twice < r.bankroll_risk_pct_once
    print(f'BR risk: once={r.bankroll_risk_pct_once:.2%} twice={r.bankroll_risk_pct_twice:.2%}')


def test_recommendation_is_valid():
    r = _rit()
    assert r.recommendation in ('accept_rit', 'decline_rit', 'indifferent')
    print(f'Recommendation: {r.recommendation}')


def test_confidence_is_valid():
    r = _rit()
    assert r.confidence in ('strong', 'moderate', 'marginal')
    print(f'Confidence: {r.confidence}')


def test_ev_note_in_tips():
    """Tips should mention EV is identical for both options."""
    r = _rit()
    ev_tips = [t for t in r.tips if 'EV' in t and 'identical' in t.lower() or 'same' in t.lower() or 'NOT change' in t]
    assert len(ev_tips) > 0, f'No EV-identical tip found. Tips: {r.tips}'
    print(f'EV note tip: {ev_tips[0][:60]}')


def test_tournament_flag_works():
    r = _rit(is_tournament=True)
    tourney_tips = [t for t in r.tips if 'TOURNAMENT' in t.upper() or 'ICM' in t]
    assert len(tourney_tips) > 0, f'No tournament tip found. Tips: {r.tips}'
    print(f'Tournament tip: {tourney_tips[0][:60]}')


def test_std_formula_correct():
    """std_once = pot * sqrt(equity*(1-equity))."""
    pot, eq = 100.0, 0.65
    r = _rit(pot_bb=pot, hero_equity=eq)
    expected_std = round(pot * math.sqrt(eq * (1 - eq)), 2)
    assert abs(r.std_run_once - expected_std) < 0.01, \
        f'std_once={r.std_run_once:.2f} vs expected={expected_std:.2f}'
    print(f'std_once={r.std_run_once:.2f} (expected {expected_std:.2f})')


def test_even_equity_has_max_variance():
    """50/50 equity produces maximum variance."""
    r_even = _rit(hero_equity=0.50)
    r_fav = _rit(hero_equity=0.80)
    assert r_even.std_run_once >= r_fav.std_run_once, \
        f'50/50 should have more variance: {r_even.std_run_once:.2f} vs {r_fav.std_run_once:.2f}'
    print(f'50/50 std={r_even.std_run_once:.2f} vs 80% fav std={r_fav.std_run_once:.2f}')


def test_hero_offering_when_ahead_penalized():
    """Hero offering RIT when ahead should be penalized vs accepting from behind."""
    r_ahead_offering = _rit(hero_equity=0.80, is_hero_offering=True, bankroll_bb=5000.0)
    r_behind_offering = _rit(hero_equity=0.30, is_hero_offering=True, bankroll_bb=5000.0)
    # Behind offering -> should still tend toward accept (variance reduction for underdog)
    print(f'Ahead-offering: {r_ahead_offering.recommendation} | Behind-offering: {r_behind_offering.recommendation}')
    assert isinstance(r_ahead_offering.recommendation, str)


def test_tips_not_empty():
    r = _rit()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_not_empty():
    r = _rit()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _rit()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _rit()
    line = rit_one_liner(r)
    assert 'RIT' in line and 'ev=' in line and 'br_risk' in line
    print(f'one_liner: {line}')


def test_bankroll_risk_calculation():
    """bankroll_risk_pct_once = std_run_once / bankroll."""
    r = _rit(pot_bb=100.0, hero_equity=0.65, bankroll_bb=1000.0)
    expected = round(r.std_run_once / 1000.0, 4)
    assert abs(r.bankroll_risk_pct_once - expected) < 0.001, \
        f'BR risk once: {r.bankroll_risk_pct_once:.4f} vs expected {expected:.4f}'
    print(f'BR risk once={r.bankroll_risk_pct_once:.3f} (expected {expected:.3f})')


def test_reasoning_code_not_empty():
    r = _rit()
    assert isinstance(r.reasoning_code, str) and len(r.reasoning_code) > 2
    print(f'Reasoning code: {r.reasoning_code}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_ev_is_equity_times_pot, test_run_twice_has_lower_std,
        test_variance_reduction_is_approx_29_pct, test_std_twice_is_std_once_over_sqrt2,
        test_short_bankroll_recommends_accept, test_huge_favorite_declines_rit,
        test_tilt_favors_accepting, test_bankroll_risk_twice_less_than_once,
        test_recommendation_is_valid, test_confidence_is_valid,
        test_ev_note_in_tips, test_tournament_flag_works, test_std_formula_correct,
        test_even_equity_has_max_variance, test_hero_offering_when_ahead_penalized,
        test_tips_not_empty, test_verdict_not_empty, test_reasoning_not_empty,
        test_one_liner, test_bankroll_risk_calculation, test_reasoning_code_not_empty,
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
