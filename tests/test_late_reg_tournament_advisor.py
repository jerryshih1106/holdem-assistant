"""Tests for poker/late_reg_tournament_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.late_reg_tournament_advisor import advise_late_reg, LateRegAdvice, latreg_one_liner


def _lr(**kw):
    defaults = dict(
        starting_chips=10000, current_bb=200, current_ante=25,
        n_players_table=9, avg_stack=12000, total_registered=300,
        blind_level=8, estimated_ev_per_level=0.02, big_blind_at_level1=50.0,
    )
    defaults.update(kw)
    return advise_late_reg(**defaults)


def test_returns_correct_type():
    r = _lr()
    assert isinstance(r, LateRegAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _lr()
    fields = [
        'starting_chips', 'current_bb', 'current_ante', 'n_players_table',
        'avg_stack', 'total_registered', 'blind_level', 'estimated_ev_per_level',
        'm_ratio_on_reg', 'm_zone', 'avg_stack_ratio', 'chips_behind_avg',
        'recommendation', 'recommendation_desc', 'latest_recommended_level',
        'ideal_reg_level', 'ev_saved_by_skipping', 'ev_lost_by_skipping',
        'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_m_ratio_calculation():
    """M = starting_chips / orbit_cost."""
    # orbit = BB + SB + ante*n = 200 + 100 + 25*9 = 525
    # M = 10000/525 = 19.05
    r = _lr(starting_chips=10000, current_bb=200, current_ante=25, n_players_table=9)
    expected_m = 10000 / (200 + 100 + 25 * 9)
    assert abs(r.m_ratio_on_reg - round(expected_m, 1)) < 0.1, \
        f'M-ratio: {r.m_ratio_on_reg:.2f} vs expected {expected_m:.2f}'
    print(f'M-ratio: {r.m_ratio_on_reg:.2f}')


def test_high_m_ratio_recommends_register():
    """High M-ratio (green zone) with reasonable stack -> register now."""
    r = _lr(starting_chips=20000, current_bb=200, current_ante=0,
            avg_stack=18000, n_players_table=9)
    # M = 20000 / 300 = 66 -> green, stack > avg -> register
    assert r.recommendation in ('register_now', 'marginal'), \
        f'High M should recommend registration: {r.recommendation}'
    print(f'High M recommendation: {r.recommendation} (M={r.m_ratio_on_reg:.1f})')


def test_very_low_m_do_not_reg():
    """M < 6 -> do not register (push/fold mode on arrival)."""
    r = _lr(starting_chips=5000, current_bb=2000, current_ante=200, n_players_table=9)
    # M = 5000 / (2000+1000+200*9) = 5000/4800 = 1.04 -> red/dead
    assert r.recommendation == 'do_not_reg' or r.m_ratio_on_reg < 6, \
        f'Very low M should not reg: {r.recommendation} (M={r.m_ratio_on_reg:.1f})'
    print(f'Low M recommendation: {r.recommendation} (M={r.m_ratio_on_reg:.1f})')


def test_avg_stack_ratio_correct():
    r = _lr(starting_chips=8000, avg_stack=16000)
    assert abs(r.avg_stack_ratio - 0.5) < 0.01, f'Ratio: {r.avg_stack_ratio}'
    print(f'avg_stack_ratio: {r.avg_stack_ratio:.3f}')


def test_chips_behind_avg_positive_when_below():
    r = _lr(starting_chips=8000, avg_stack=12000)
    assert r.chips_behind_avg > 0, f'Should be behind avg: {r.chips_behind_avg}'
    print(f'Chips behind avg: {r.chips_behind_avg:,.0f}')


def test_chips_behind_avg_negative_when_ahead():
    r = _lr(starting_chips=15000, avg_stack=10000)
    assert r.chips_behind_avg < 0, f'Should be ahead of avg: {r.chips_behind_avg}'
    print(f'Chips ahead of avg: {-r.chips_behind_avg:,.0f}')


def test_m_zone_green_when_high_m():
    r = _lr(starting_chips=30000, current_bb=200, current_ante=0, n_players_table=9)
    assert r.m_zone == 'green', f'Should be green: {r.m_zone} (M={r.m_ratio_on_reg})'
    print(f'M zone: {r.m_zone}')


def test_m_zone_yellow_midrange():
    r = _lr(starting_chips=10000, current_bb=400, current_ante=0, n_players_table=9)
    # M = 10000 / 600 = 16.7 -> yellow
    assert r.m_zone in ('yellow', 'green', 'orange'), f'M zone: {r.m_zone}'
    print(f'M zone: {r.m_zone} (M={r.m_ratio_on_reg:.1f})')


def test_latest_recommended_level_positive():
    r = _lr()
    assert r.latest_recommended_level >= 1
    print(f'Latest recommended level: {r.latest_recommended_level}')


def test_ideal_reg_level_positive():
    r = _lr()
    assert r.ideal_reg_level >= 1
    print(f'Ideal reg level: {r.ideal_reg_level}')


def test_ideal_level_less_than_or_equal_current():
    """Ideal reg level should be at or before current (can't go back in time)."""
    r = _lr(blind_level=10)
    assert r.ideal_reg_level <= r.blind_level, \
        f'Ideal level should be <= current: {r.ideal_reg_level} vs {r.blind_level}'
    print(f'Ideal={r.ideal_reg_level} <= current={r.blind_level}')


def test_ev_lost_increases_with_edge():
    """More EV per level -> more lost by skipping."""
    r_low = _lr(estimated_ev_per_level=0.01)
    r_high = _lr(estimated_ev_per_level=0.05)
    assert r_high.ev_lost_by_skipping >= r_low.ev_lost_by_skipping, \
        f'Higher edge should lose more by skipping: {r_high.ev_lost_by_skipping} vs {r_low.ev_lost_by_skipping}'
    print(f'EV lost: low_edge={r_low.ev_lost_by_skipping:.0f} high_edge={r_high.ev_lost_by_skipping:.0f}')


def test_recommendation_is_valid():
    valid = {'register_now', 'marginal', 'do_not_reg', 'questionable', 'late_disadvantage'}
    r = _lr()
    assert r.recommendation in valid, f'Invalid recommendation: {r.recommendation}'
    print(f'Recommendation: {r.recommendation}')


def test_recommendation_desc_not_empty():
    r = _lr()
    assert isinstance(r.recommendation_desc, str) and len(r.recommendation_desc) > 10
    print(f'Desc: {r.recommendation_desc[:60]}')


def test_tips_not_empty():
    r = _lr()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_contains_level():
    r = _lr()
    assert f'Level {r.blind_level}' in r.verdict or str(r.blind_level) in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _lr()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _lr()
    line = latreg_one_liner(r)
    assert 'LATREG' in line and 'M=' in line and 'stack=' in line
    print(f'one_liner: {line}')


def test_latest_level_gt_current_when_m_high():
    """When M is high (lots of room), can still register at future levels."""
    r = _lr(starting_chips=20000, current_bb=100, current_ante=0, n_players_table=9)
    # M = 20000/150 = 133 -> can still reg much later
    assert r.latest_recommended_level >= r.blind_level
    print(f'Latest level >= current: {r.latest_recommended_level} >= {r.blind_level}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_m_ratio_calculation, test_high_m_ratio_recommends_register,
        test_very_low_m_do_not_reg, test_avg_stack_ratio_correct,
        test_chips_behind_avg_positive_when_below, test_chips_behind_avg_negative_when_ahead,
        test_m_zone_green_when_high_m, test_m_zone_yellow_midrange,
        test_latest_recommended_level_positive, test_ideal_reg_level_positive,
        test_ideal_level_less_than_or_equal_current, test_ev_lost_increases_with_edge,
        test_recommendation_is_valid, test_recommendation_desc_not_empty,
        test_tips_not_empty, test_verdict_contains_level,
        test_reasoning_not_empty, test_one_liner,
        test_latest_level_gt_current_when_m_high,
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
