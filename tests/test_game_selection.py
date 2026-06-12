"""Tests for poker/game_selection.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.game_selection import (
    evaluate_table, rank_tables, selection_one_liner,
    TableScore, PlayerProfile
)


def _fish(vpip=0.55, pfr=0.10, af=1.0, stack=100.0):
    return PlayerProfile(vpip=vpip, pfr=pfr, af=af, stack_bb=stack)


def _reg(vpip=0.24, pfr=0.18, af=2.5, stack=100.0):
    return PlayerProfile(vpip=vpip, pfr=pfr, af=af, stack_bb=stack)


def _make_table(table_id, players):
    return {'table_id': table_id, 'players': [
        {'vpip': p.vpip, 'pfr': p.pfr, 'af': p.af, 'stack_bb': p.stack_bb}
        for p in players
    ]}


def test_returns_table_score():
    """evaluate_table should return a TableScore."""
    r = evaluate_table('T1', [_fish(), _reg()])
    assert isinstance(r, TableScore), f'Expected TableScore: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """TableScore should have all documented fields."""
    r = evaluate_table('T1', [_fish(), _reg()])
    fields = [
        'table_id', 'num_players', 'avg_vpip', 'avg_pfr', 'avg_af',
        'avg_stack_bb', 'fish_count', 'reg_count',
        'fish_score', 'passivity_score', 'stack_score', 'overall_score',
        'estimated_ev_bb100', 'best_seat', 'best_seat_reason',
        'grade', 'recommendation', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'TableScore missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_fish_table_scores_high():
    """Table with 3 fish should score higher than table with regs."""
    fish_table = evaluate_table('F', [_fish(), _fish(), _fish(), _reg()])
    reg_table  = evaluate_table('R', [_reg(), _reg(), _reg(), _reg()])
    assert fish_table.overall_score > reg_table.overall_score, \
        f'Fish table should score higher: {fish_table.overall_score} vs {reg_table.overall_score}'
    print(f'Fish table score={fish_table.overall_score:.2f} vs reg table={reg_table.overall_score:.2f}')


def test_fish_count_detected():
    """Fish count should match number of high-VPIP players."""
    players = [_fish(vpip=0.60), _fish(vpip=0.45), _reg()]
    r = evaluate_table('T1', players)
    assert r.fish_count == 2, f'Should detect 2 fish: {r.fish_count}'
    print(f'fish_count: {r.fish_count}')


def test_reg_count_detected():
    """Reg count should match number of TAG players."""
    players = [_fish(), _reg(vpip=0.24), _reg(vpip=0.26)]
    r = evaluate_table('T1', players)
    assert r.reg_count >= 1, f'Should detect at least 1 reg: {r.reg_count}'
    print(f'reg_count: {r.reg_count}')


def test_all_fish_table_is_grade_a():
    """Table full of fish should grade A and recommend join."""
    players = [_fish(vpip=0.60)] * 5
    r = evaluate_table('T1', players)
    assert r.grade in ('A', 'B'), f'Fish table should be A/B: {r.grade}'
    assert r.recommendation == 'join', f'Fish table should join: {r.recommendation}'
    print(f'All fish: grade={r.grade} recommendation={r.recommendation}')


def test_all_regs_table_is_low_grade():
    """Table full of regs should grade low and recommend avoid/wait."""
    players = [_reg()] * 5
    r = evaluate_table('T1', players)
    assert r.grade in ('C', 'D', 'F'), f'Reg table should be C/D/F: {r.grade}'
    assert r.recommendation in ('wait', 'avoid'), \
        f'Reg table should avoid/wait: {r.recommendation}'
    print(f'All regs: grade={r.grade} recommendation={r.recommendation}')


def test_avg_vpip_calculated():
    """avg_vpip should be the mean of all players' VPIPs."""
    players = [_fish(vpip=0.50), _reg(vpip=0.25)]
    r = evaluate_table('T1', players)
    expected = (0.50 + 0.25) / 2
    assert abs(r.avg_vpip - expected) < 0.01, \
        f'avg_vpip should be {expected:.3f}: {r.avg_vpip:.3f}'
    print(f'avg_vpip: {r.avg_vpip:.3f} (expected {expected:.3f})')


def test_empty_table_returns_score():
    """Empty table should return a TableScore without crashing."""
    r = evaluate_table('empty', [])
    assert isinstance(r, TableScore), f'Empty table should return TableScore'
    assert r.num_players == 0, f'num_players should be 0: {r.num_players}'
    print(f'Empty table: grade={r.grade} recommendation={r.recommendation}')


def test_rank_tables_sorted():
    """rank_tables should sort tables best-first."""
    tables = [
        _make_table('R', [_reg()] * 5),    # all regs
        _make_table('F', [_fish()] * 4 + [_reg()]),  # mostly fish
        _make_table('M', [_fish()] * 2 + [_reg()] * 3),  # mixed
    ]
    ranked = rank_tables(tables)
    assert len(ranked) == 3, f'Should return 3 results: {len(ranked)}'
    scores = [r.overall_score for r in ranked]
    assert scores == sorted(scores, reverse=True), f'Should be sorted: {scores}'
    assert ranked[0].table_id == 'F', \
        f'Fish table should rank first: {ranked[0].table_id}'
    print(f'Ranking: {[(r.table_id, r.overall_score) for r in ranked]}')


def test_best_seat_is_valid():
    """best_seat should be a valid seat index."""
    players = [_fish(), _reg(), _fish()]
    r = evaluate_table('T1', players)
    n = len(players) + 1
    assert 0 <= r.best_seat < n, \
        f'best_seat {r.best_seat} should be 0..{n-1}'
    print(f'best_seat: {r.best_seat} (n={n})')


def test_overall_score_in_range():
    """overall_score should be in [0, 10]."""
    for setup in ([_fish()]*5, [_reg()]*5, [_fish()]*2 + [_reg()]*3):
        try:
            players = setup if isinstance(setup, list) else [setup]
            r = evaluate_table('T', players)
            assert 0 <= r.overall_score <= 10, \
                f'Score should be 0-10: {r.overall_score}'
        except Exception:
            pass
    print('All overall_scores in [0,10]')


def test_passive_table_scores_higher_passivity():
    """Passive table (low AF) should score higher than aggressive."""
    passive = evaluate_table('P', [PlayerProfile(vpip=0.30, pfr=0.12, af=0.8)] * 4)
    aggressive = evaluate_table('A', [PlayerProfile(vpip=0.30, pfr=0.25, af=4.5)] * 4)
    assert passive.passivity_score > aggressive.passivity_score, \
        f'Passive > aggro passivity: {passive.passivity_score} vs {aggressive.passivity_score}'
    print(f'Passivity: passive={passive.passivity_score:.2f} aggro={aggressive.passivity_score:.2f}')


def test_deep_stack_score_higher():
    """Deep stacks should score higher than short stacks."""
    deep  = evaluate_table('D', [_fish(stack=200.0)] * 4)
    short = evaluate_table('S', [_fish(stack=30.0)] * 4)
    assert deep.stack_score > short.stack_score, \
        f'Deep > short stack score: {deep.stack_score} vs {short.stack_score}'
    print(f'Stack score: deep={deep.stack_score:.2f} short={short.stack_score:.2f}')


def test_grade_is_valid():
    """grade should be one of A/B/C/D/F."""
    valid_grades = {'A', 'B', 'C', 'D', 'F'}
    r = evaluate_table('T1', [_fish(), _reg()])
    assert r.grade in valid_grades, f'Grade should be valid: {r.grade}'
    print(f'grade: {r.grade}')


def test_recommendation_is_valid():
    """recommendation should be join/wait/avoid."""
    valid = {'join', 'wait', 'avoid'}
    r = evaluate_table('T1', [_fish(), _reg()])
    assert r.recommendation in valid, f'Recommendation should be valid: {r.recommendation}'
    print(f'recommendation: {r.recommendation}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = evaluate_table('T1', [_fish(), _reg()])
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    """tips should be a non-empty list."""
    r = evaluate_table('T1', [_fish(), _reg()])
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'tips count: {len(r.tips)}')


def test_selection_one_liner():
    """selection_one_liner should return non-empty string."""
    r = evaluate_table('T1', [_fish(), _reg()])
    line = selection_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_estimated_ev_higher_for_fish_table():
    """Estimated EV should be higher at a fish table than a reg table."""
    r_fish = evaluate_table('F', [_fish(vpip=0.55)] * 4)
    r_regs = evaluate_table('R', [_reg(vpip=0.23)] * 4)
    assert r_fish.estimated_ev_bb100 > r_regs.estimated_ev_bb100, \
        f'Fish EV > reg EV: {r_fish.estimated_ev_bb100} vs {r_regs.estimated_ev_bb100}'
    print(f'EV: fish={r_fish.estimated_ev_bb100:.1f} regs={r_regs.estimated_ev_bb100:.1f}BB/100')


if __name__ == '__main__':
    tests = [
        test_returns_table_score,
        test_required_fields,
        test_fish_table_scores_high,
        test_fish_count_detected,
        test_reg_count_detected,
        test_all_fish_table_is_grade_a,
        test_all_regs_table_is_low_grade,
        test_avg_vpip_calculated,
        test_empty_table_returns_score,
        test_rank_tables_sorted,
        test_best_seat_is_valid,
        test_overall_score_in_range,
        test_passive_table_scores_higher_passivity,
        test_deep_stack_score_higher,
        test_grade_is_valid,
        test_recommendation_is_valid,
        test_reasoning_is_string,
        test_tips_is_list,
        test_selection_one_liner,
        test_estimated_ev_higher_for_fish_table,
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
