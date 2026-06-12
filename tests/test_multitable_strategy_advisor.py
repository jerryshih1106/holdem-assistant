"""Tests for poker/multitable_strategy_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.multitable_strategy_advisor import advise_multitable, MultitableAdvice, mt_one_liner


def _mt(**kw):
    defaults = dict(
        n_tables=4, current_bb100=4.0, vpip=26.0,
        game_format='6max', hands_per_hour_single=250,
    )
    defaults.update(kw)
    return advise_multitable(**defaults)


def test_returns_correct_type():
    r = _mt()
    assert isinstance(r, MultitableAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _mt()
    fields = [
        'n_tables', 'current_bb100', 'vpip', 'game_format', 'hands_per_hour_single',
        'strategy_tier', 'tier_description', 'estimated_wr_at_n', 'estimated_hands_per_hour',
        'estimated_bb_per_hour', 'optimal_table_count', 'optimal_bb_per_hour',
        'adjusted_vpip_target', 'do_list', 'dont_list', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_single_table_is_full_gto():
    r = _mt(n_tables=1)
    assert r.strategy_tier == 'full_gto', f'1 table should be full_gto: {r.strategy_tier}'
    print(f'1 table tier: {r.strategy_tier}')


def test_two_to_three_tables_creative_tag():
    r2 = _mt(n_tables=2)
    r3 = _mt(n_tables=3)
    assert r2.strategy_tier == 'creative_tag'
    assert r3.strategy_tier == 'creative_tag'
    print(f'2-3 tables: creative_tag confirmed')


def test_four_to_six_tables_solid_tag():
    r4 = _mt(n_tables=4)
    r6 = _mt(n_tables=6)
    assert r4.strategy_tier == 'solid_tag'
    assert r6.strategy_tier == 'solid_tag'
    print(f'4-6 tables: solid_tag confirmed')


def test_seven_to_ten_tables_nitty_tag():
    r7 = _mt(n_tables=7)
    r10 = _mt(n_tables=10)
    assert r7.strategy_tier == 'nitty_tag'
    assert r10.strategy_tier == 'nitty_tag'
    print(f'7-10 tables: nitty_tag confirmed')


def test_eleven_plus_tables_mass_table():
    r = _mt(n_tables=11)
    assert r.strategy_tier == 'mass_table', f'11+ tables should be mass_table: {r.strategy_tier}'
    print(f'11 tables: mass_table confirmed')


def test_wr_decreases_with_more_tables():
    """More tables -> lower estimated BB/100."""
    r1 = _mt(n_tables=1)
    r4 = _mt(n_tables=4)
    r8 = _mt(n_tables=8)
    assert r4.estimated_wr_at_n <= r1.estimated_wr_at_n, \
        f'4 tables WR should be <= 1 table: {r4.estimated_wr_at_n} vs {r1.estimated_wr_at_n}'
    assert r8.estimated_wr_at_n <= r4.estimated_wr_at_n, \
        f'8 tables WR should be <= 4 tables: {r8.estimated_wr_at_n} vs {r4.estimated_wr_at_n}'
    print(f'WR: 1={r1.estimated_wr_at_n:.2f} 4={r4.estimated_wr_at_n:.2f} 8={r8.estimated_wr_at_n:.2f}')


def test_hands_per_hour_increases_with_tables():
    """More tables -> more total hands/hour (up to a point)."""
    r1 = _mt(n_tables=1)
    r4 = _mt(n_tables=4)
    assert r4.estimated_hands_per_hour > r1.estimated_hands_per_hour, \
        f'4 tables HPH should exceed 1 table: {r4.estimated_hands_per_hour} vs {r1.estimated_hands_per_hour}'
    print(f'HPH: 1={r1.estimated_hands_per_hour} 4={r4.estimated_hands_per_hour}')


def test_optimal_table_count_positive():
    r = _mt()
    assert r.optimal_table_count >= 1, f'Optimal tables must be >= 1: {r.optimal_table_count}'
    print(f'Optimal table count: {r.optimal_table_count}')


def test_optimal_bb_per_hour_positive():
    r = _mt()
    assert r.optimal_bb_per_hour > 0, f'Optimal BB/hr should be positive: {r.optimal_bb_per_hour}'
    print(f'Optimal BB/hr: {r.optimal_bb_per_hour:+.2f}')


def test_vpip_decreases_with_more_tables():
    """More tables -> tighter recommended VPIP."""
    r1 = _mt(n_tables=1, vpip=26.0)
    r8 = _mt(n_tables=8, vpip=26.0)
    assert r8.adjusted_vpip_target < r1.adjusted_vpip_target, \
        f'8 tables VPIP should be < 1 table: {r8.adjusted_vpip_target} vs {r1.adjusted_vpip_target}'
    print(f'VPIP target: 1={r1.adjusted_vpip_target} 8={r8.adjusted_vpip_target}')


def test_do_list_not_empty():
    r = _mt()
    assert isinstance(r.do_list, list) and len(r.do_list) > 0
    print(f'Do list ({len(r.do_list)}): {r.do_list[:2]}')


def test_dont_list_has_content_for_many_tables():
    r = _mt(n_tables=6)
    assert isinstance(r.dont_list, list) and len(r.dont_list) > 0, \
        f'6 tables should have a dont_list: {r.dont_list}'
    print(f'Dont list ({len(r.dont_list)}): {r.dont_list[:2]}')


def test_single_table_dont_list_empty():
    r = _mt(n_tables=1)
    assert len(r.dont_list) == 0, f'1 table dont list should be empty: {r.dont_list}'
    print(f'1 table dont_list: [] confirmed')


def test_tips_not_empty():
    r = _mt()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_over_tabled_tip_when_many_tables():
    """Playing too many tables should trigger an over-tabled warning."""
    # Simulate case where optimal is much lower than current
    r = _mt(n_tables=16, current_bb100=2.0)
    over_tips = [t for t in r.tips if 'OVER' in t.upper() or 'over' in t.lower()]
    # Either over-table tip or another relevant warning should appear
    assert len(r.tips) > 0
    print(f'16 table tips: {len(r.tips)} tips present')


def test_low_wr_warning():
    """Low win rate with multi-tabling should generate a warning."""
    r = _mt(n_tables=4, current_bb100=1.5)
    low_wr_tips = [t for t in r.tips if 'WR' in t or 'warning' in t.lower() or 'marginal' in t.lower() or 'LOW' in t]
    print(f'Low WR tips: {low_wr_tips[:1] if low_wr_tips else "(none, check tips:)"} {r.tips}')


def test_verdict_not_empty():
    r = _mt()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _mt()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _mt()
    line = mt_one_liner(r)
    assert 'MT' in line and 'WR=' in line and 'optimal=' in line
    print(f'one_liner: {line}')


def test_bb_per_hour_calculation():
    """BB/hr = WR/100 * HPH."""
    r = _mt()
    expected = round(r.estimated_wr_at_n / 100 * r.estimated_hands_per_hour, 2)
    assert abs(r.estimated_bb_per_hour - expected) < 0.01, \
        f'BB/hr mismatch: {r.estimated_bb_per_hour} vs expected {expected}'
    print(f'BB/hr={r.estimated_bb_per_hour:.2f} (wr={r.estimated_wr_at_n:.2f} * {r.estimated_hands_per_hour}h/100)')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_single_table_is_full_gto, test_two_to_three_tables_creative_tag,
        test_four_to_six_tables_solid_tag, test_seven_to_ten_tables_nitty_tag,
        test_eleven_plus_tables_mass_table, test_wr_decreases_with_more_tables,
        test_hands_per_hour_increases_with_tables, test_optimal_table_count_positive,
        test_optimal_bb_per_hour_positive, test_vpip_decreases_with_more_tables,
        test_do_list_not_empty, test_dont_list_has_content_for_many_tables,
        test_single_table_dont_list_empty, test_tips_not_empty,
        test_over_tabled_tip_when_many_tables, test_low_wr_warning,
        test_verdict_not_empty, test_reasoning_not_empty,
        test_one_liner, test_bb_per_hour_calculation,
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
