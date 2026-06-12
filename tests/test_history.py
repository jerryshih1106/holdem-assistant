"""Tests for poker/history.py"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.history import HistoryTracker, HandRecord, SessionStats


def _make_tracker():
    tmp = tempfile.mktemp(suffix='.db')
    return HistoryTracker(db_path=tmp), tmp


def _rec(pos='BTN', outcome=50, followed=True, hero_action='raise', rec_action='raise'):
    return HandRecord(
        hand_id=None, session_id=1, position=pos,
        hole_cards=['Ah', 'Ks'], community=['Ac', '7h', '2d'],
        pot_size=100, call_amount=0, hero_stack=400,
        outcome=outcome, hero_action=hero_action, rec_action=rec_action,
        followed_rec=followed,
    )


def test_record_and_retrieve_hands():
    """Recorded hands should appear in recent_hands."""
    h, tmp = _make_tracker()
    for _ in range(5):
        h.record_hand(_rec())
    hands = h.recent_hands(10)
    assert len(hands) == 5, f'Should retrieve 5 hands: {len(hands)}'
    os.unlink(tmp)
    print(f'recent_hands count: {len(hands)}')


def test_recent_hands_respects_n():
    """recent_hands(n) should return at most n hands."""
    h, tmp = _make_tracker()
    for _ in range(10):
        h.record_hand(_rec())
    hands = h.recent_hands(3)
    assert len(hands) <= 3, f'recent_hands(3) should return <= 3: {len(hands)}'
    os.unlink(tmp)
    print(f'recent_hands(3): {len(hands)} returned')


def test_session_stats_hand_count():
    """session_stats.hands should match recorded hand count."""
    h, tmp = _make_tracker()
    for _ in range(8):
        h.record_hand(_rec())
    stats = h.session_stats()
    assert stats.hands == 8, f'hands should be 8: {stats.hands}'
    os.unlink(tmp)
    print(f'session_stats.hands: {stats.hands}')


def test_session_stats_profit_sum():
    """session_stats.profit should equal sum of all outcome values."""
    h, tmp = _make_tracker()
    h.record_hand(_rec(outcome=80))
    h.record_hand(_rec(outcome=-30))
    h.record_hand(_rec(outcome=50))
    stats = h.session_stats()
    assert stats.profit == 100, f'profit should be 80-30+50=100: {stats.profit}'
    os.unlink(tmp)
    print(f'session_stats.profit: {stats.profit}')


def test_rec_follow_pct():
    """rec_follow_pct() should be in [0, 100] after mixed decisions."""
    h, tmp = _make_tracker()
    for _ in range(3):
        h.record_hand(_rec(followed=True, hero_action='raise', rec_action='raise'))
    # Divergent: called when fold recommended
    h.record_hand(_rec(followed=False, hero_action='call', rec_action='fold'))
    stats = h.session_stats()
    pct = stats.rec_follow_pct()
    assert pct is None or 0.0 <= pct <= 100.0, \
        f'rec_follow_pct should be in [0,100] or None: {pct}'
    os.unlink(tmp)
    print(f'rec_follow_pct: {pct}')


def test_vpip_pct_per_position():
    """vpip_pct(pos) should return None when no hands played in that position."""
    h, tmp = _make_tracker()
    h.record_hand(_rec(pos='BTN'))
    stats = h.session_stats()
    assert stats.vpip_pct('UTG') is None, \
        f'vpip_pct should be None for unseen position: {stats.vpip_pct("UTG")}'
    os.unlink(tmp)
    print(f'vpip_pct UTG (no hands): {stats.vpip_pct("UTG")}')


def test_recent_hands_dict_keys():
    """Each hand in recent_hands should have expected keys."""
    h, tmp = _make_tracker()
    h.record_hand(_rec())
    hands = h.recent_hands(1)
    assert len(hands) > 0
    hand = hands[0]
    required = {'position', 'outcome', 'hero_action', 'rec_action'}
    for k in required:
        assert k in hand, f'Hand dict missing key: {k}'
    os.unlink(tmp)
    print(f'Hand keys: {list(hand.keys())}')


def test_find_leaks_returns_list():
    """find_leaks should return a list (possibly empty)."""
    h, tmp = _make_tracker()
    for _ in range(5):
        h.record_hand(_rec(outcome=-30, followed=False, hero_action='call', rec_action='fold'))
    leaks = h.find_leaks()
    assert isinstance(leaks, list), f'find_leaks should return list: {type(leaks)}'
    os.unlink(tmp)
    print(f'find_leaks result: {len(leaks)} items')


def test_empty_tracker_no_error():
    """session_stats on empty tracker should return valid defaults."""
    h, tmp = _make_tracker()
    stats = h.session_stats()
    assert stats.hands == 0, f'Empty tracker should have 0 hands: {stats.hands}'
    assert stats.profit == 0, f'Empty tracker profit should be 0: {stats.profit}'
    os.unlink(tmp)
    print(f'Empty tracker: hands={stats.hands} profit={stats.profit}')


def test_multiple_positions_tracked():
    """Session stats should track hands by position."""
    h, tmp = _make_tracker()
    h.record_hand(_rec(pos='BTN'))
    h.record_hand(_rec(pos='BB'))
    h.record_hand(_rec(pos='CO'))
    stats = h.session_stats()
    assert stats.hands == 3
    assert stats.hands_by_pos.get('BTN', 0) == 1
    assert stats.hands_by_pos.get('BB', 0) == 1
    os.unlink(tmp)
    print(f'hands_by_pos: {stats.hands_by_pos}')


if __name__ == '__main__':
    tests = [
        test_record_and_retrieve_hands,
        test_recent_hands_respects_n,
        test_session_stats_hand_count,
        test_session_stats_profit_sum,
        test_rec_follow_pct,
        test_vpip_pct_per_position,
        test_recent_hands_dict_keys,
        test_find_leaks_returns_list,
        test_empty_tracker_no_error,
        test_multiple_positions_tracked,
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
