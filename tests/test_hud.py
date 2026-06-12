"""Tests for poker/hud.py"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hud import HUDTracker, PlayerStats


def _make_tracker():
    """Create HUDTracker backed by a temp SQLite file."""
    tmp = tempfile.mktemp(suffix='.db')
    h = HUDTracker(tmp)
    return h, tmp


def test_vpip_pct_calculated_correctly():
    """VPIP% = vpip_count / hands * 100."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero'})
    for _ in range(10):
        h.new_hand([1])
        h.record(1, 'vpip')
    for _ in range(10):
        h.new_hand([1])     # fold preflop
    ps = h.get_player(1)
    assert ps.hands == 20
    assert abs(ps.vpip_pct - 50.0) < 1.0, \
        f'VPIP should be 50%: {ps.vpip_pct}'
    os.unlink(tmp)
    print(f'VPIP: {ps.vpip_pct:.0f}% (expected 50%)')


def test_pfr_pct_calculated_correctly():
    """PFR% = pfr_count / hands * 100."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero'})
    for _ in range(20):
        h.new_hand([1])
        h.record(1, 'vpip')
        h.record(1, 'pfr')
    for _ in range(20):
        h.new_hand([1])
    ps = h.get_player(1)
    assert abs(ps.pfr_pct - 50.0) < 1.0, \
        f'PFR should be 50%: {ps.pfr_pct}'
    os.unlink(tmp)
    print(f'PFR: {ps.pfr_pct:.0f}% (expected 50%)')


def test_fish_classification():
    """High VPIP + low PFR = Fish/Calling type."""
    h, tmp = _make_tracker()
    h.set_players({1: 'V'})
    for _ in range(50):
        h.new_hand([1])
        h.record(1, 'vpip')   # 100% VPIP
    for _ in range(50):
        h.new_hand([1])
        h.record(1, 'vpip')
        h.record(1, 'call')   # never raises
    ps = h.get_player(1)
    assert ps.vpip_pct >= 50, f'VPIP should be >= 50%: {ps.vpip_pct}'
    ptype = ps.player_type()
    assert 'fish' in ptype.lower() or 'call' in ptype.lower() or 'lag' in ptype.lower(), \
        f'High VPIP player should be fish/calling/lag: {ptype}'
    os.unlink(tmp)
    print(f'Fish type: {ptype} (VPIP={ps.vpip_pct:.0f}% PFR={ps.pfr_pct}%)')


def test_vpip_pct_none_when_no_hands():
    """vpip_pct should be None when hands=0."""
    h, tmp = _make_tracker()
    ps = h.get_player(99)  # unseen seat
    assert ps.vpip_pct is None, \
        f'vpip_pct should be None with no hands: {ps.vpip_pct}'
    os.unlink(tmp)
    print('vpip_pct=None when hands=0')


def test_hands_count_increments():
    """Hand count should increment with each new_hand call."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero'})
    for _ in range(15):
        h.new_hand([1])
    ps = h.get_player(1)
    assert ps.hands == 15, f'hands should be 15: {ps.hands}'
    os.unlink(tmp)
    print(f'Hand count: {ps.hands}')


def test_player_stats_fields_exist():
    """PlayerStats should have expected fields."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero'})
    h.new_hand([1])
    h.record(1, 'vpip')
    ps = h.get_player(1)
    required = ['hands', 'vpip', 'pfr', 'cbet', 'fcbet']
    for field in required:
        assert hasattr(ps, field), f'PlayerStats missing field: {field}'
    os.unlink(tmp)
    print(f'Required fields present: {required}')


def test_cbet_recording():
    """C-bet recording should increment cbet count."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero'})
    for _ in range(5):
        h.new_hand([1])
        h.record(1, 'cbet')
        h.record(1, 'cbet')   # cbet_opps counts individually
    ps = h.get_player(1)
    assert ps.cbet > 0, f'cbet count should be > 0: {ps.cbet}'
    os.unlink(tmp)
    print(f'C-bet recorded: cbet={ps.cbet}')


def test_exploit_note_returns_string():
    """exploit_note should return a string."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero'})
    h.new_hand([1]); h.record(1, 'vpip')
    ps = h.get_player(1)
    note = ps.exploit_note()
    assert isinstance(note, str), f'exploit_note should be str: {type(note)}'
    os.unlink(tmp)
    print(f'Exploit note: {note[:50]}')


def test_all_players_returns_list():
    """all_players should return a list of PlayerStats."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero', 2: 'Villain'})
    h.new_hand([1, 2])
    h.record(1, 'vpip'); h.record(2, 'vpip')
    players = h.all_players()
    assert isinstance(players, list), f'all_players should return list: {type(players)}'
    os.unlink(tmp)
    print(f'all_players count: {len(players)}')


def test_record_multiple_actions():
    """Recording multiple action types should all be stored."""
    h, tmp = _make_tracker()
    h.set_players({1: 'Hero'})
    for _ in range(10):
        h.new_hand([1])
        h.record(1, 'vpip')
        h.record(1, 'pfr')
        h.record(1, 'cbet')
        h.record(1, 'fcbet')
    ps = h.get_player(1)
    assert ps.vpip > 0 and ps.pfr > 0, \
        f'All action types should be recorded: vpip={ps.vpip} pfr={ps.pfr}'
    os.unlink(tmp)
    print(f'Multi-action: vpip={ps.vpip} pfr={ps.pfr} cbet={ps.cbet}')


if __name__ == '__main__':
    tests = [
        test_vpip_pct_calculated_correctly,
        test_pfr_pct_calculated_correctly,
        test_fish_classification,
        test_vpip_pct_none_when_no_hands,
        test_hands_count_increments,
        test_player_stats_fields_exist,
        test_cbet_recording,
        test_exploit_note_returns_string,
        test_all_players_returns_list,
        test_record_multiple_actions,
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
