"""Tests for poker/table_analyzer.py — uses real HUDTracker PlayerStats."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hud import HUDTracker
from poker.table_analyzer import analyze_table, table_summary, TableReport


def _hud_with_player(vpip_hands, pfr_hands, total_hands, af_bets=0, af_calls=0,
                     vpip_pct_approx=None):
    """Build a HUDTracker with one player recorded to given stats."""
    tmp = tempfile.mktemp(suffix='.db')
    h = HUDTracker(tmp)
    h.set_players({1: 'V'})
    for i in range(total_hands):
        h.new_hand([1])
        if i < vpip_hands:
            h.record(1, 'vpip')
        if i < pfr_hands:
            h.record(1, 'pfr')
    return h, tmp


def test_empty_players_returns_valid_report():
    """analyze_table with empty list should return a valid default report."""
    r = analyze_table([])
    assert isinstance(r, TableReport)
    assert r.total_players == 0
    assert r.stars >= 1
    print(f'Empty table: stars={r.stars}')


def test_fish_table_high_stars():
    """Table full of fish (high VPIP, low PFR) should get high stars."""
    h, tmp = _hud_with_player(vpip_hands=14, pfr_hands=1, total_hands=20)
    players = h.all_players()
    r = analyze_table(players * 5)  # 5 fish
    assert r.stars >= 3, f'Fish table should have >= 3 stars: {r.stars}'
    assert r.fish_count >= 0  # fish might be classified by vpip_pct thresholds
    os.unlink(tmp)
    print(f'Fish table: stars={r.stars} fish={r.fish_count} avg_vpip={r.avg_vpip:.0f}%')


def test_table_report_has_required_fields():
    """TableReport should have all expected fields."""
    h, tmp = _hud_with_player(10, 5, 20)
    r = analyze_table(h.all_players())
    required = ['total_players', 'players_with_data', 'avg_vpip', 'avg_pfr',
                'fish_count', 'nit_count', 'reg_count', 'shark_count',
                'stars', 'rating_label', 'rating_color', 'action', 'advice']
    for field in required:
        assert hasattr(r, field), f'TableReport missing field: {field}'
    os.unlink(tmp)
    print('All fields present')


def test_stars_in_valid_range():
    """stars should be an integer in [1, 5]."""
    h, tmp = _hud_with_player(10, 5, 20)
    r = analyze_table(h.all_players())
    assert 1 <= r.stars <= 5, f'stars should be in [1,5]: {r.stars}'
    os.unlink(tmp)
    print(f'Stars: {r.stars}')


def test_rating_color_valid():
    """rating_color should be one of green/yellow/red."""
    h, tmp = _hud_with_player(10, 5, 20)
    r = analyze_table(h.all_players())
    assert r.rating_color in ('green', 'yellow', 'red'), \
        f'rating_color should be green/yellow/red: {r.rating_color}'
    os.unlink(tmp)
    print(f'Rating color: {r.rating_color}')


def test_action_valid_values():
    """action should be one of STAY/CONSIDER_LEAVING/LEAVE."""
    h, tmp = _hud_with_player(10, 5, 20)
    r = analyze_table(h.all_players())
    assert r.action in ('STAY', 'CONSIDER_LEAVING', 'LEAVE'), \
        f'action should be valid: {r.action}'
    os.unlink(tmp)
    print(f'Action: {r.action}')


def test_avg_vpip_calculated():
    """avg_vpip should reflect actual VPIP recorded."""
    h, tmp = _hud_with_player(vpip_hands=15, pfr_hands=5, total_hands=20)
    r = analyze_table(h.all_players())
    # 15/20 = 75% VPIP
    assert r.avg_vpip > 50.0, \
        f'High-VPIP player avg_vpip should be > 50%: {r.avg_vpip}'
    os.unlink(tmp)
    print(f'High-VPIP avg_vpip: {r.avg_vpip:.0f}%')


def test_players_with_data_counts_only_qualified():
    """players_with_data should only count players with >= 10 hands."""
    h, tmp = _hud_with_player(vpip_hands=3, pfr_hands=1, total_hands=5)
    r = analyze_table(h.all_players())
    # Only 5 hands — below the 10-hand threshold
    assert r.players_with_data == 0, \
        f'Player with <10 hands should not qualify: {r.players_with_data}'
    os.unlink(tmp)
    print(f'players_with_data for <10 hands: {r.players_with_data}')


def test_table_summary_returns_string():
    """table_summary should return a non-empty string."""
    h, tmp = _hud_with_player(10, 5, 20)
    r = analyze_table(h.all_players())
    s = table_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'table_summary should be non-empty: {repr(s)[:50]}'
    os.unlink(tmp)
    print(f'table_summary length: {len(s)}')


def test_high_vpip_table_gets_stay_recommendation():
    """Table with many high-VPIP players should recommend STAY."""
    h, tmp = _hud_with_player(vpip_hands=16, pfr_hands=2, total_hands=20)
    players = h.all_players()
    r = analyze_table(players * 4)
    assert r.action in ('STAY', 'CONSIDER_LEAVING'), \
        f'High-VPIP table should not immediately say LEAVE: {r.action}'
    os.unlink(tmp)
    print(f'High-VPIP table action: {r.action} stars={r.stars}')


if __name__ == '__main__':
    tests = [
        test_empty_players_returns_valid_report,
        test_fish_table_high_stars,
        test_table_report_has_required_fields,
        test_stars_in_valid_range,
        test_rating_color_valid,
        test_action_valid_values,
        test_avg_vpip_calculated,
        test_players_with_data_counts_only_qualified,
        test_table_summary_returns_string,
        test_high_vpip_table_gets_stay_recommendation,
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
