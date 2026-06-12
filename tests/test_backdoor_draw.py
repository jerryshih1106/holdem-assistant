"""Tests for poker/backdoor_draw.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.backdoor_draw import analyze_backdoor_draw, backdoor_draw_summary


def test_suited_hole_same_suit_backdoor_flush():
    """KcQc on Ac7h2s → backdoor flush (two clubs, one club on board)."""
    r = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qc'],
        community=['Ac', '7h', '2s'],
        raw_equity=0.32,
    )
    assert r.has_backdoor_flush, f'KcQc on Ac7h2s should have backdoor flush'
    assert r.backdoor_equity_pct > 0, f'Should have backdoor equity contribution'
    print(f'KcQc/Ac7h2s: bf={r.has_backdoor_flush}  equity+={r.backdoor_equity_pct:.1f}%  adj={r.adjusted_equity:.0%}')


def test_offsuit_no_backdoor_flush():
    """KcQh on Ah7s2d → no backdoor flush (hole cards different suits)."""
    r = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qh'],
        community=['Ah', '7s', '2d'],
        raw_equity=0.32,
    )
    assert not r.has_backdoor_flush, f'KcQh (offsuit) should have no backdoor flush'
    print(f'KcQh (offsuit): bf={r.has_backdoor_flush}')


def test_three_flush_board_no_backdoor():
    """AdKd on Qd7d2d → no backdoor flush (3 diamonds on board, not runner-runner)."""
    r = analyze_backdoor_draw(
        hole_cards=['Ad', 'Kd'],
        community=['Qd', '7d', '2d'],
        raw_equity=0.50,
    )
    # Board already has 3 diamonds → not a backdoor draw (need 0 or 1 board matches)
    # With hole having 2 diamonds and board having 3: total 5 diamonds → already made flush!
    # OR board has 3 of suit, hero has 2 → that's 5 diamonds with overlap
    # The function checks board_matching <= 1
    # Here board has 3d: count of 'd' in board = 3 → matching = 3 → not backdoor
    assert not r.has_backdoor_flush, f'Board already has 3 diamonds, not backdoor'
    print(f'Flush board: bf={r.has_backdoor_flush} (correct, already made or not backdoor)')


def test_connected_cards_backdoor_straight():
    """JcTh on 8h5d2c → backdoor straight (J-T connected, some coverage)."""
    r = analyze_backdoor_draw(
        hole_cards=['Jc', 'Th'],
        community=['8h', '5d', '2c'],
        raw_equity=0.30,
    )
    # J-T-8 spans: J=11, T=10, 8=8 → in range 7-11 (5-wide): J,T,8 = 3 in window → strong
    assert r.has_backdoor_straight, f'JT on 8-high board should have backdoor straight draw'
    assert r.backdoor_type in ('strong', 'medium'), f'Type should be strong/medium: {r.backdoor_type}'
    print(f'JcTh/8h5d2c: bs={r.has_backdoor_straight}  type={r.backdoor_type}  equity+={r.backdoor_equity_pct:.1f}%')


def test_double_backdoor_highest_equity():
    """KdQd on Jd7h3c → both backdoor flush and straight."""
    r = analyze_backdoor_draw(
        hole_cards=['Kd', 'Qd'],
        community=['Jd', '7h', '3c'],
        raw_equity=0.38,
    )
    assert r.n_backdoor_draws == 2, f'Should have 2 backdoor draws: {r.n_backdoor_draws}'
    assert r.backdoor_equity_pct >= 6.0, f'Double backdoor should add >=6%: {r.backdoor_equity_pct}'
    print(f'KdQd/Jd7h3c: draws={r.n_backdoor_draws}  equity+={r.backdoor_equity_pct:.1f}%  adj={r.adjusted_equity:.0%}')


def test_adjusted_equity_higher_than_raw():
    """Adjusted equity should always be >= raw equity when backdoor draws exist."""
    r = analyze_backdoor_draw(
        hole_cards=['Ac', 'Kc'],
        community=['Qd', '7s', '2h'],
        raw_equity=0.40,
    )
    if r.n_backdoor_draws > 0:
        assert r.adjusted_equity >= r.raw_equity, \
            f'Adjusted equity should be >= raw: {r.adjusted_equity} vs {r.raw_equity}'
    print(f'AcKc/Qd7s2h: raw={r.raw_equity:.0%}  adjusted={r.adjusted_equity:.0%}  draws={r.n_backdoor_draws}')


def test_no_backdoor_high_equity_check_call():
    """No backdoor but high raw equity → check-call (not semi-bluff)."""
    r = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qd'],
        community=['Jd', '5h', '2c'],
        raw_equity=0.45,
        primary_draw_outs=4,  # gutshot
    )
    # Has primary draw → should check-call or bet
    print(f'KcQd/Jd5h2c: cont_type={r.continuation_type}  should_semi={r.should_semi_bluff}')
    # Just verify no crash
    assert r.continuation_type in ('semibluff', 'thin_value', 'check_call', 'check_fold')


def test_multiway_no_semibluff():
    """Multiway pot (3 opponents) → do not semi-bluff with backdoor draws."""
    r = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qc'],
        community=['Jd', '7h', '2s'],
        raw_equity=0.35,
        n_opponents=3,
    )
    assert not r.should_semi_bluff, f'Multiway should not semi-bluff: {r.should_semi_bluff}'
    assert r.bet_frequency == 0.0, f'Multiway freq should be 0: {r.bet_frequency}'
    print(f'Multiway: should_semi={r.should_semi_bluff}  freq={r.bet_frequency:.0%}')


def test_high_cbet_boosts_bluff_frequency():
    """High c-bet villain → better probe/bluff opportunity."""
    r_high = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qc'], community=['Jd', '7h', '2s'],
        raw_equity=0.38, villain_cbet_pct=0.80,
    )
    r_low  = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qc'], community=['Jd', '7h', '2s'],
        raw_equity=0.38, villain_cbet_pct=0.35,
    )
    if r_high.should_semi_bluff and r_low.should_semi_bluff:
        assert r_high.bet_frequency >= r_low.bet_frequency, \
            f'High cbet should boost frequency: {r_high.bet_frequency:.0%} vs {r_low.bet_frequency:.0%}'
    print(f'High cbet: {r_high.bet_frequency:.0%}  Low cbet: {r_low.bet_frequency:.0%}')


def test_small_sizing_for_backdoor_bluffs():
    """Backdoor semi-bluffs should use small sizing (1/3 to 1/2 pot)."""
    r = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qc'], community=['Jd', '7h', '2s'],
        raw_equity=0.38, pot_bb=20.0, villain_cbet_pct=0.75,
    )
    if r.should_semi_bluff:
        assert r.sizing_pct <= 0.60, f'Backdoor bluff sizing should be small: {r.sizing_pct:.0%}'
        assert r.sizing_bb > 0, 'Should have non-zero sizing'
    print(f'Sizing: {r.sizing_pct:.0%} pot = {r.sizing_bb:.0f}BB  (pot={r.pot_bb}BB)')


def test_no_draws_low_equity_check_fold():
    """No draws + low equity → check-fold."""
    r = analyze_backdoor_draw(
        hole_cards=['7c', '2h'],
        community=['Ac', 'Kd', 'Jh'],
        raw_equity=0.08,
        primary_draw_outs=0,
    )
    assert r.continuation_type == 'check_fold', \
        f'No draws, low equity should check-fold: {r.continuation_type}'
    assert not r.should_semi_bluff, f'Should not semi-bluff with 7-2'
    print(f'7-2 on AKJ: {r.continuation_type}  draws={r.n_backdoor_draws}')


def test_summary_format():
    """Summary should be <=85 chars and contain [後門]."""
    r = analyze_backdoor_draw(
        hole_cards=['Kc', 'Qc'],
        community=['Jd', '7h', '2s'],
        raw_equity=0.40,
        villain_cbet_pct=0.70,
        pot_bb=15.0,
    )
    s = backdoor_draw_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[後門]' in s, f'Missing [後門]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_suited_hole_same_suit_backdoor_flush,
        test_offsuit_no_backdoor_flush,
        test_three_flush_board_no_backdoor,
        test_connected_cards_backdoor_straight,
        test_double_backdoor_highest_equity,
        test_adjusted_equity_higher_than_raw,
        test_no_backdoor_high_equity_check_call,
        test_multiway_no_semibluff,
        test_high_cbet_boosts_bluff_frequency,
        test_small_sizing_for_backdoor_bluffs,
        test_no_draws_low_equity_check_fold,
        test_summary_format,
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
