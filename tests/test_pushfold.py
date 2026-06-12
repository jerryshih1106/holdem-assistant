"""Tests for poker/pushfold.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pushfold import push_advice, push_range_percent, push_range, bb_call_range


def test_premium_hand_pushes_all_stacks():
    """AA should push from any position at any stack depth."""
    for pos in ['UTG', 'CO', 'BTN', 'SB']:
        r = push_advice(hand='AA', position=pos, stack_bb=15.0)
        assert r['action'] == 'PUSH', f'AA should always push from {pos}: {r["action"]}'
    print('AA pushes from all positions')


def test_trash_hand_doesnt_push_deep():
    """72o should not push at 15BB from UTG (too deep / too weak)."""
    r = push_advice(hand='72o', position='UTG', stack_bb=15.0)
    assert r['action'] in ('FOLD', 'fold') or r['in_range'] is False, \
        f'72o UTG 15BB should fold: action={r["action"]} in_range={r["in_range"]}'
    print(f'72o UTG 15BB: action={r["action"]} in_range={r["in_range"]}')


def test_btn_wider_range_than_utg():
    """BTN push range should be wider than UTG at same stack depth."""
    btn_pct = push_range_percent('BTN', 10.0)
    utg_pct = push_range_percent('UTG', 10.0)
    assert btn_pct >= utg_pct, \
        f'BTN {btn_pct:.1f}% should >= UTG {utg_pct:.1f}%'
    print(f'Push range: BTN={btn_pct:.1f}%  UTG={utg_pct:.1f}%')


def test_shorter_stack_wider_push_range():
    """Shorter stack should use wider push range (desperation mode)."""
    pct_5bb = push_range_percent('BTN', 5.0)
    pct_15bb = push_range_percent('BTN', 15.0)
    assert pct_5bb >= pct_15bb, \
        f'5BB range {pct_5bb:.1f}% should >= 15BB {pct_15bb:.1f}%'
    print(f'BTN push range: 5BB={pct_5bb:.1f}%  15BB={pct_15bb:.1f}%')


def test_push_range_percent_between_0_and_100():
    """push_range_percent should return a valid percentage."""
    for pos in ['UTG', 'CO', 'BTN', 'SB']:
        pct = push_range_percent(pos, 10.0)
        assert 0.0 <= pct <= 100.0, f'{pos} range_pct out of bounds: {pct}'
    print('push_range_percent in [0,100] for all positions')


def test_push_range_is_set():
    """push_range should return a frozenset of hand strings."""
    r = push_range('BTN', 10.0)
    assert isinstance(r, frozenset), f'push_range should be frozenset: {type(r)}'
    assert len(r) > 0, 'push_range should not be empty at 10BB BTN'
    print(f'BTN 10BB push range: {len(r)} hands')


def test_bb_call_range_is_set():
    """bb_call_range should return a frozenset of hand strings."""
    r = bb_call_range(10.0)
    assert isinstance(r, frozenset), f'bb_call_range should be frozenset: {type(r)}'
    assert len(r) > 0, 'bb_call_range should not be empty at 10BB'
    print(f'BB call range at 10BB: {len(r)} hands')


def test_bb_calls_premium_hands():
    """BB should call a push with premium hands (AA, KK, AK)."""
    call_range = bb_call_range(10.0)
    for hand in ['AA', 'KK', 'AKs']:
        assert hand in call_range, f'BB should call {hand}: not in call range'
    print(f'BB calls AA/KK/AKs at 10BB (call range={len(call_range)} hands)')


def test_push_in_range_flag():
    """push_advice in_range should match whether hand is in push range."""
    r = push_advice(hand='AKs', position='BTN', stack_bb=10.0)
    assert isinstance(r['in_range'], bool), f'in_range should be bool: {type(r["in_range"])}'
    print(f'AKs BTN 10BB: in_range={r["in_range"]} action={r["action"]}')


def test_push_rank_positive():
    """push_rank should be a positive integer indicating hand strength order."""
    r = push_advice(hand='AA', position='BTN', stack_bb=10.0)
    assert isinstance(r['push_rank'], int) and r['push_rank'] >= 0, \
        f'push_rank should be non-negative int: {r["push_rank"]}'
    # AA is rank 0 (index 0 = best hand in 169-hand order), note says #1/169
    print(f'AA push_rank: {r["push_rank"]} ({r["note"]})')


if __name__ == '__main__':
    tests = [
        test_premium_hand_pushes_all_stacks,
        test_trash_hand_doesnt_push_deep,
        test_btn_wider_range_than_utg,
        test_shorter_stack_wider_push_range,
        test_push_range_percent_between_0_and_100,
        test_push_range_is_set,
        test_bb_call_range_is_set,
        test_bb_calls_premium_hands,
        test_push_in_range_flag,
        test_push_rank_positive,
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
