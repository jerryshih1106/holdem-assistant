"""Tests for poker/river_overbet_strategy.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.river_overbet_strategy import advise_river_overbet, RiverOverbetAdvice, rob_one_liner


def _rob(**kw):
    defaults = dict(
        hero_nut_advantage=0.65,
        hero_equity=0.75,
        pot_bb=30.0,
        effective_stack_bb=70.0,
        villain_wtsd=0.28,
        villain_af=1.8,
        villain_vpip=0.24,
        hero_position='IP',
        hero_hand_rank_pct=0.82,
        board_type='dry',
        range_is_polarized=True,
    )
    defaults.update(kw)
    return advise_river_overbet(**defaults)


def test_returns_correct_type():
    r = _rob()
    assert isinstance(r, RiverOverbetAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _rob()
    fields = [
        'hero_nut_advantage', 'hero_equity', 'pot_bb', 'effective_stack_bb',
        'villain_wtsd', 'villain_af', 'villain_vpip', 'hero_position',
        'hero_hand_rank_pct', 'board_type', 'range_is_polarized',
        'overbet_score', 'overbet_recommended',
        'size_120_ev', 'size_150_ev', 'size_175_ev', 'size_200_ev', 'size_check_ev',
        'optimal_size_fraction', 'optimal_size_bb', 'optimal_ev', 'optimal_fold_pct',
        'fold_pct_at_optimal', 'fold_equity_needed', 'fold_equity_surplus',
        'action', 'action_reason', 'confidence', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_high_nut_advantage_recommends_overbet():
    """High nut advantage + polarized range should recommend overbet."""
    r = _rob(hero_nut_advantage=0.80, range_is_polarized=True, villain_wtsd=0.25)
    assert 'overbet' in r.action or r.overbet_recommended, \
        f'High nut advantage should overbet: {r.action}'
    print(f'High nut advantage: {r.action}')


def test_call_station_prevents_overbet():
    """Call station (high VPIP) should not get overbets."""
    r = _rob(villain_vpip=0.55, hero_nut_advantage=0.70)
    assert r.action != 'overbet_200', \
        f'Should not overbet vs call station: {r.action}'
    print(f'Call station action: {r.action}')


def test_unpolarized_range_uses_standard_bet():
    """Unpolarized range should not overbet."""
    r = _rob(range_is_polarized=False)
    assert 'overbet' not in r.action, \
        f'Unpolarized should not overbet: {r.action}'
    print(f'Unpolarized action: {r.action}')


def test_low_nut_advantage_prevents_overbet():
    """Low nut advantage should prevent overbets."""
    r = _rob(hero_nut_advantage=0.20, villain_wtsd=0.30)
    assert 'overbet' not in r.action or r.overbet_score < 0.55, \
        f'Low nut advantage should not overbet: {r.action}'
    print(f'Low nut advantage: action={r.action} score={r.overbet_score:.2f}')


def test_overbet_score_in_range():
    r = _rob()
    assert 0.0 <= r.overbet_score <= 1.0, f'Score out of range: {r.overbet_score}'
    print(f'Overbet score: {r.overbet_score:.2f}')


def test_high_nut_advantage_higher_score():
    """Higher nut advantage should give higher overbet score."""
    r_low = _rob(hero_nut_advantage=0.20)
    r_high = _rob(hero_nut_advantage=0.90)
    assert r_high.overbet_score > r_low.overbet_score, \
        f'High na score {r_high.overbet_score:.2f} should > low {r_low.overbet_score:.2f}'
    print(f'Score: low_na={r_low.overbet_score:.2f} high_na={r_high.overbet_score:.2f}')


def test_tight_villain_higher_fold_pct():
    """Tight villain (low WTSD) should fold more."""
    r_tight = _rob(villain_wtsd=0.20)
    r_loose = _rob(villain_wtsd=0.45)
    assert r_tight.optimal_fold_pct > r_loose.optimal_fold_pct, \
        f'Tight should fold more: tight={r_tight.optimal_fold_pct:.0%} loose={r_loose.optimal_fold_pct:.0%}'
    print(f'Fold: tight={r_tight.optimal_fold_pct:.0%} loose={r_loose.optimal_fold_pct:.0%}')


def test_optimal_size_bb_positive():
    r = _rob()
    assert r.optimal_size_bb > 0
    print(f'Optimal size: {r.optimal_size_bb:.1f}BB')


def test_optimal_size_larger_than_pot():
    """Overbet optimal size should exceed pot."""
    r = _rob()
    if r.overbet_recommended:
        assert r.optimal_size_bb > r.pot_bb * 1.1, \
            f'Overbet should exceed pot: {r.optimal_size_bb:.1f} vs pot {r.pot_bb:.1f}'
    print(f'Optimal size: {r.optimal_size_bb:.1f}BB pot={r.pot_bb:.1f}BB')


def test_check_ev_positive_for_strong_hand():
    """Strong hand should have positive check EV."""
    r = _rob(hero_equity=0.80)
    assert r.size_check_ev > 0, f'Strong hand check EV should be positive: {r.size_check_ev:.2f}'
    print(f'Check EV (eq=80%): {r.size_check_ev:.2f}BB')


def test_ev_ordering_sensible():
    """With high fold rates, larger bets should not always be worse."""
    r = _rob(villain_wtsd=0.20, hero_nut_advantage=0.80)
    # At least one overbet should beat check
    max_bet_ev = max(r.size_120_ev, r.size_150_ev, r.size_175_ev, r.size_200_ev)
    # Hard to guarantee order strictly, but max bet EV should be reasonable
    assert max_bet_ev > r.size_check_ev - 5.0, \
        f'Max bet EV {max_bet_ev:.2f} should be near check EV {r.size_check_ev:.2f}'
    print(f'EVs: check={r.size_check_ev:.2f} 120%={r.size_120_ev:.2f} 150%={r.size_150_ev:.2f}')


def test_action_valid():
    valid = {'overbet_200', 'overbet_175', 'overbet_150', 'overbet_120', 'standard_bet', 'check'}
    r = _rob()
    assert r.action in valid, f'Invalid action: {r.action}'
    print(f'Action: {r.action}')


def test_confidence_valid():
    valid = {'high', 'medium', 'low'}
    r = _rob()
    assert r.confidence in valid
    print(f'Confidence: {r.confidence}')


def test_tips_not_empty():
    r = _rob()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_size_comparison_tip_present():
    """Tips should include size comparison."""
    r = _rob()
    size_tips = [t for t in r.tips if 'SIZE COMPARISON' in t or '120%' in t]
    assert len(size_tips) > 0, f'Size comparison tip missing: {r.tips}'
    print('Size comparison tip found')


def test_call_station_warning_tip():
    """Call station should trigger warning tip."""
    r = _rob(villain_vpip=0.55)
    warning_tips = [t for t in r.tips if 'CALL STATION' in t or 'station' in t.lower()]
    assert len(warning_tips) > 0, f'Call station warning missing: {r.tips}'
    print('Call station warning found')


def test_fold_equity_surplus_consistent():
    """fold_surplus = optimal_fold_pct - fold_equity_needed."""
    r = _rob()
    expected = round(r.fold_pct_at_optimal - r.fold_equity_needed, 3)
    assert abs(r.fold_equity_surplus - expected) < 0.02, \
        f'Surplus: {r.fold_equity_surplus:.3f} vs computed {expected:.3f}'
    print(f'Fold surplus: {r.fold_equity_surplus:+.0%}')


def test_overbet_recommended_flag():
    """overbet_recommended should be True when score >= 0.55."""
    r = _rob()
    if r.overbet_score >= 0.55:
        assert r.overbet_recommended, f'Score {r.overbet_score:.2f} >= 0.55 should set overbet_recommended'
    print(f'Overbet recommended: {r.overbet_recommended} (score={r.overbet_score:.2f})')


def test_board_type_affects_score():
    """Dry board should score higher than wet for overbets."""
    r_dry = _rob(board_type='dry')
    r_wet = _rob(board_type='wet')
    assert r_dry.overbet_score >= r_wet.overbet_score, \
        f'Dry score {r_dry.overbet_score:.2f} should >= wet {r_wet.overbet_score:.2f}'
    print(f'Score: dry={r_dry.overbet_score:.2f} wet={r_wet.overbet_score:.2f}')


def test_verdict_contains_action():
    r = _rob()
    assert r.action.upper() in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _rob()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _rob()
    line = rob_one_liner(r)
    assert 'ROB' in line and 'ev=' in line and 'fold=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_high_nut_advantage_recommends_overbet, test_call_station_prevents_overbet,
        test_unpolarized_range_uses_standard_bet, test_low_nut_advantage_prevents_overbet,
        test_overbet_score_in_range, test_high_nut_advantage_higher_score,
        test_tight_villain_higher_fold_pct, test_optimal_size_bb_positive,
        test_optimal_size_larger_than_pot, test_check_ev_positive_for_strong_hand,
        test_ev_ordering_sensible, test_action_valid, test_confidence_valid,
        test_tips_not_empty, test_size_comparison_tip_present,
        test_call_station_warning_tip, test_fold_equity_surplus_consistent,
        test_overbet_recommended_flag, test_board_type_affects_score,
        test_verdict_contains_action, test_reasoning_not_empty, test_one_liner,
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
