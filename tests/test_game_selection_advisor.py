"""Tests for poker/game_selection_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.game_selection_advisor import advise_game_selection, GameSelectionAdvice, game_selection_one_liner


def _gs(**kw):
    defaults = dict(
        player_vpips=[0.48, 0.32, 0.26, 0.55, 0.18, 0.22],
        player_stacks_bb=[120.0, 100.0, 85.0, 200.0, 60.0, 40.0],
        hero_seat=0,
        table_size=6,
        avg_pot_bb=15.0,
        rake_structure='nl100',
        hero_winrate_baseline_bb100=3.0,
    )
    defaults.update(kw)
    return advise_game_selection(**defaults)


def test_returns_correct_type():
    r = _gs()
    assert isinstance(r, GameSelectionAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _gs()
    fields = [
        'player_vpips', 'player_stacks_bb', 'hero_seat', 'table_size',
        'avg_pot_bb', 'rake_structure', 'hero_winrate_baseline_bb100',
        'fish_count', 'reg_count', 'avg_table_vpip', 'table_type',
        'table_score', 'seat_quality', 'best_available_seat',
        'estimated_winrate_bb100', 'winrate_confidence', 'stay_or_leave',
        'verdict', 'player_types', 'exploit_notes', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_fish_count_correct():
    """Fish count = players with VPIP >= 40%."""
    r = _gs(player_vpips=[0.48, 0.32, 0.26, 0.55, 0.18, 0.22])
    # Seats 0 (0.48) and 3 (0.55) are fish, but hero=seat 0 excluded from opponent analysis
    assert r.fish_count >= 1, f'Should detect at least 1 fish: {r.fish_count}'
    print(f'Fish count: {r.fish_count}')


def test_all_fish_table_high_score():
    """Table full of fish should have high score."""
    r = _gs(player_vpips=[0.50, 0.55, 0.60, 0.45, 0.48, 0.52])
    assert r.table_score >= 70, f'All-fish table should score >= 70: {r.table_score}'
    print(f'All-fish table score: {r.table_score}')


def test_all_reg_table_low_score():
    """Table full of regs should have low score."""
    r = _gs(player_vpips=[0.24, 0.20, 0.22, 0.19, 0.23, 0.21])
    assert r.table_score <= 45, f'All-reg table should score <= 45: {r.table_score}'
    print(f'All-reg table score: {r.table_score}')


def test_fish_table_stay():
    """Fish-heavy table should recommend staying."""
    r = _gs(player_vpips=[0.50, 0.55, 0.60, 0.45, 0.48, 0.52])
    assert r.stay_or_leave in ('stay', 'stay_and_move_seat'), \
        f'Fish table should stay: {r.stay_or_leave}'
    print(f'Fish table: {r.stay_or_leave}')


def test_reg_table_leave():
    """All-reg table should recommend leaving."""
    r = _gs(player_vpips=[0.22, 0.20, 0.22, 0.19, 0.23, 0.21])
    assert r.stay_or_leave == 'leave', f'All-reg table should leave: {r.stay_or_leave}'
    print(f'All-reg table: {r.stay_or_leave}')


def test_table_type_fish_heavy():
    """3+ fish at 6-max → fish_heavy."""
    r = _gs(player_vpips=[0.50, 0.55, 0.60, 0.45, 0.22, 0.24])
    assert r.table_type == 'fish_heavy', f'Should be fish_heavy: {r.table_type}'
    print(f'Table type: {r.table_type}')


def test_fish_improves_estimated_winrate():
    """More fish → higher estimated winrate."""
    r_fish = _gs(player_vpips=[0.50, 0.55, 0.60, 0.48, 0.22, 0.24])
    r_reg = _gs(player_vpips=[0.22, 0.20, 0.22, 0.19, 0.23, 0.21])
    assert r_fish.estimated_winrate_bb100 > r_reg.estimated_winrate_bb100, \
        f'Fish table WR > reg table: {r_fish.estimated_winrate_bb100} vs {r_reg.estimated_winrate_bb100}'
    print(f'WR: fish={r_fish.estimated_winrate_bb100:+.1f} reg={r_reg.estimated_winrate_bb100:+.1f}')


def test_seat_quality_with_fish_to_right():
    """Fish immediately to hero's right → good/excellent seat quality."""
    # Seat 0 = hero. Seat 5 = player to hero's right (wraps around in 6-handed)
    r = _gs(
        player_vpips=[0.24, 0.22, 0.24, 0.20, 0.22, 0.55],  # fish at seat 5 (hero's right)
        hero_seat=0,
    )
    assert r.seat_quality in ('excellent', 'good'), \
        f'Fish to right should be good/excellent seat: {r.seat_quality}'
    print(f'Seat quality (fish to right): {r.seat_quality}')


def test_player_types_correct_length():
    """Player types list should have one entry per player."""
    vpips = [0.48, 0.32, 0.26, 0.55, 0.18, 0.22]
    r = _gs(player_vpips=vpips)
    assert len(r.player_types) == len(vpips), \
        f'Player types length: {len(r.player_types)} vs {len(vpips)}'
    print(f'Player types: {r.player_types}')


def test_fish_classified_as_fish():
    """VPIP >= 40% players should be classified as fish."""
    r = _gs(player_vpips=[0.50, 0.22, 0.20, 0.22, 0.21, 0.23])
    assert r.player_types[0] == 'fish', f'VPIP 50% should be fish: {r.player_types[0]}'
    print(f'Fish classification: {r.player_types[0]}')


def test_nit_classified_as_nit():
    """VPIP <= 18% should be classified as nit."""
    r = _gs(player_vpips=[0.15, 0.22, 0.20, 0.22, 0.21, 0.23])
    assert r.player_types[0] == 'nit', f'VPIP 15% should be nit: {r.player_types[0]}'
    print(f'Nit classification: {r.player_types[0]}')


def test_table_score_range():
    """Table score must be between 0 and 100."""
    r = _gs()
    assert 0 <= r.table_score <= 100, f'Score out of range: {r.table_score}'
    print(f'Table score: {r.table_score}')


def test_stay_or_leave_valid():
    valid = {'stay', 'leave', 'stay_and_move_seat'}
    r = _gs()
    assert r.stay_or_leave in valid, f'Invalid decision: {r.stay_or_leave}'
    print(f'Decision: {r.stay_or_leave}')


def test_winrate_confidence_valid():
    valid = {'high', 'medium', 'low'}
    r = _gs()
    assert r.winrate_confidence in valid, f'Invalid confidence: {r.winrate_confidence}'
    print(f'Confidence: {r.winrate_confidence}')


def test_deep_stacks_boost_score():
    """Deep stacks should increase table attractiveness."""
    r_deep = _gs(player_stacks_bb=[200.0, 200.0, 200.0, 200.0, 200.0, 200.0])
    r_short = _gs(player_stacks_bb=[30.0, 30.0, 30.0, 30.0, 30.0, 30.0])
    assert r_deep.table_score >= r_short.table_score, \
        f'Deep stacks should score >= short: {r_deep.table_score} vs {r_short.table_score}'
    print(f'Score: deep={r_deep.table_score} short={r_short.table_score}')


def test_exploit_notes_not_empty():
    """Exploit notes should identify fish and nits."""
    r = _gs(player_vpips=[0.50, 0.55, 0.22, 0.20, 0.18, 0.24])
    # Should have notes about at least the fish
    assert len(r.exploit_notes) > 0
    print(f'Exploit notes: {len(r.exploit_notes)}')


def test_tips_not_empty():
    r = _gs()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_verdict_not_empty():
    r = _gs()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:60]}...')


def test_one_liner():
    r = _gs()
    line = game_selection_one_liner(r)
    assert 'GS' in line and 'score=' in line and 'fish=' in line and 'wr=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_fish_count_correct, test_all_fish_table_high_score,
        test_all_reg_table_low_score, test_fish_table_stay,
        test_reg_table_leave, test_table_type_fish_heavy,
        test_fish_improves_estimated_winrate, test_seat_quality_with_fish_to_right,
        test_player_types_correct_length, test_fish_classified_as_fish,
        test_nit_classified_as_nit, test_table_score_range,
        test_stay_or_leave_valid, test_winrate_confidence_valid,
        test_deep_stacks_boost_score, test_exploit_notes_not_empty,
        test_tips_not_empty, test_verdict_not_empty,
        test_one_liner,
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
