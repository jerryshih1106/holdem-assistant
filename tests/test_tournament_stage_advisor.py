"""Tests for poker/tournament_stage_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.tournament_stage_advisor import advise_tournament_stage, TournamentStageAdvice, tourney_one_liner


def _adv(**kw):
    defaults = dict(
        stack_bb=50.0, big_blind=1.0, small_blind=0.5, ante_bb=0.0,
        n_players_table=9, total_players_started=1000,
        players_remaining=500, in_money=False, final_table=False,
        avg_stack_bb=50.0, itm_spots=100,
    )
    defaults.update(kw)
    return advise_tournament_stage(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, TournamentStageAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'stack_bb', 'big_blind', 'small_blind', 'ante_bb', 'n_players_table',
        'total_players_started', 'players_remaining', 'in_money', 'final_table',
        'avg_stack_bb', 'm_ratio', 'm_zone', 'pct_remaining', 'phase',
        'stack_vs_avg', 'strategy_mode', 'strategy_advice', 'vpip_target',
        'open_raise_size', 'reshove_range', 'calloff_range', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_m_ratio_green_zone():
    """Stack=100BB, orbit cost=1.5BB (no ante) -> M=66 -> green."""
    r = _adv(stack_bb=100.0, big_blind=1.0, small_blind=0.5, ante_bb=0.0)
    assert r.m_zone == 'green', f'Expected green: {r.m_zone} (M={r.m_ratio})'
    print(f'M={r.m_ratio} zone={r.m_zone}')


def test_m_ratio_yellow_zone():
    """Stack=20BB, orbit=1.5BB -> M=13.3 -> yellow."""
    r = _adv(stack_bb=20.0, big_blind=1.0, small_blind=0.5, ante_bb=0.0)
    assert r.m_zone == 'yellow', f'Expected yellow: {r.m_zone} (M={r.m_ratio})'
    print(f'M={r.m_ratio} zone={r.m_zone}')


def test_m_ratio_orange_zone():
    """Stack=10BB, orbit=1.5BB -> M=6.7 -> orange."""
    r = _adv(stack_bb=10.0, big_blind=1.0, small_blind=0.5, ante_bb=0.0)
    assert r.m_zone == 'orange', f'Expected orange: {r.m_zone} (M={r.m_ratio})'
    print(f'M={r.m_ratio} zone={r.m_zone}')


def test_m_ratio_red_zone():
    """Stack=5BB, orbit=1.5BB -> M=3.3 -> red."""
    r = _adv(stack_bb=5.0, big_blind=1.0, small_blind=0.5, ante_bb=0.0)
    assert r.m_zone == 'red', f'Expected red: {r.m_zone} (M={r.m_ratio})'
    print(f'M={r.m_ratio} zone={r.m_zone}')


def test_m_ratio_dead_zone():
    """Stack=0.8BB -> M < 1 -> dead."""
    r = _adv(stack_bb=0.8, big_blind=1.0, small_blind=0.5, ante_bb=0.0)
    assert r.m_zone == 'dead', f'Expected dead: {r.m_zone} (M={r.m_ratio})'
    print(f'M={r.m_ratio} zone={r.m_zone}')


def test_antes_reduce_m():
    """Antes increase orbit cost, reducing M ratio."""
    r_no_ante = _adv(stack_bb=50.0, ante_bb=0.0, n_players_table=9)
    r_with_ante = _adv(stack_bb=50.0, ante_bb=0.1, n_players_table=9)
    assert r_with_ante.m_ratio < r_no_ante.m_ratio, \
        f'Antes should reduce M: no_ante={r_no_ante.m_ratio} with_ante={r_with_ante.m_ratio}'
    print(f'M: no_ante={r_no_ante.m_ratio} with_ante={r_with_ante.m_ratio}')


def test_phase_early():
    """75%+ players remaining -> early phase."""
    r = _adv(players_remaining=800, total_players_started=1000, in_money=False, final_table=False)
    assert r.phase == 'early', f'Expected early: {r.phase}'
    print(f'Phase: {r.phase}')


def test_phase_middle():
    """25-75% remaining -> middle phase."""
    r = _adv(players_remaining=400, total_players_started=1000, in_money=False, final_table=False, itm_spots=100)
    assert r.phase == 'middle', f'Expected middle: {r.phase}'
    print(f'Phase: {r.phase}')


def test_phase_bubble():
    """Very close to ITM -> bubble phase."""
    # 105 remaining, 100 paid spots -> 5% from money (bubble)
    r = _adv(players_remaining=105, total_players_started=1000, in_money=False,
             final_table=False, itm_spots=100)
    assert r.phase == 'bubble', f'Expected bubble: {r.phase}'
    print(f'Phase: {r.phase}')


def test_phase_in_money():
    """in_money=True -> in_money phase."""
    r = _adv(in_money=True, final_table=False)
    assert r.phase == 'in_money', f'Expected in_money: {r.phase}'
    print(f'Phase: {r.phase}')


def test_phase_final_table():
    """final_table=True -> final_table phase."""
    r = _adv(final_table=True)
    assert r.phase == 'final_table', f'Expected final_table: {r.phase}'
    print(f'Phase: {r.phase}')


def test_green_early_is_accumulate():
    """Green zone, early phase -> accumulate strategy."""
    r = _adv(stack_bb=200.0, players_remaining=800, total_players_started=1000)
    assert r.strategy_mode in ('accumulate',), \
        f'Green/early should be accumulate: {r.strategy_mode}'
    print(f'Mode: {r.strategy_mode}')


def test_dead_zone_is_desperate():
    """Dead zone -> desperate strategy."""
    r = _adv(stack_bb=0.5)
    assert r.strategy_mode == 'desperate', f'Dead should be desperate: {r.strategy_mode}'
    print(f'Dead zone mode: {r.strategy_mode}')


def test_stack_vs_avg_correct():
    """stack_vs_avg = hero_stack / avg_stack."""
    r = _adv(stack_bb=100.0, avg_stack_bb=50.0)
    assert abs(r.stack_vs_avg - 2.0) < 0.01, f'stack_vs_avg: {r.stack_vs_avg}'
    print(f'stack_vs_avg: {r.stack_vs_avg:.2f}x')


def test_pct_remaining_correct():
    r = _adv(players_remaining=300, total_players_started=1000)
    assert abs(r.pct_remaining - 0.3) < 0.01, f'pct_remaining: {r.pct_remaining}'
    print(f'pct_remaining: {r.pct_remaining:.1%}')


def test_vpip_target_not_empty():
    r = _adv()
    assert isinstance(r.vpip_target, str) and '%' in r.vpip_target
    print(f'VPIP target: {r.vpip_target}')


def test_open_size_not_empty():
    r = _adv()
    assert isinstance(r.open_raise_size, str) and len(r.open_raise_size) > 3
    print(f'Open size: {r.open_raise_size}')


def test_reshove_range_not_empty():
    r = _adv()
    assert isinstance(r.reshove_range, str) and len(r.reshove_range) > 5
    print(f'Reshove range: {r.reshove_range[:50]}')


def test_calloff_range_not_empty():
    r = _adv()
    assert isinstance(r.calloff_range, str) and len(r.calloff_range) > 5
    print(f'Calloff range: {r.calloff_range[:50]}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_ante_tip_present():
    """Should mention antes in tips when ante_bb > 0."""
    r = _adv(ante_bb=0.1)
    ante_tips = [t for t in r.tips if 'ANTE' in t.upper() or 'ante' in t.lower()]
    assert len(ante_tips) > 0, f'No ante tip found. Tips: {r.tips}'
    print(f'Ante tip: {ante_tips[0][:60]}')


def test_verdict_contains_zone():
    r = _adv()
    assert r.m_zone.upper() in r.verdict, f'Zone not in verdict: {r.verdict[:80]}'
    print(f'Verdict: {r.verdict[:80]}')


def test_one_liner():
    r = _adv()
    line = tourney_one_liner(r)
    assert 'MTT' in line and 'M=' in line and 'stack=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_m_ratio_green_zone, test_m_ratio_yellow_zone,
        test_m_ratio_orange_zone, test_m_ratio_red_zone, test_m_ratio_dead_zone,
        test_antes_reduce_m, test_phase_early, test_phase_middle,
        test_phase_bubble, test_phase_in_money, test_phase_final_table,
        test_green_early_is_accumulate, test_dead_zone_is_desperate,
        test_stack_vs_avg_correct, test_pct_remaining_correct,
        test_vpip_target_not_empty, test_open_size_not_empty,
        test_reshove_range_not_empty, test_calloff_range_not_empty,
        test_tips_not_empty, test_ante_tip_present,
        test_verdict_contains_zone, test_one_liner,
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
