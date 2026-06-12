"""Tests for poker/equity_realizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.equity_realizer import calculate_equity_realization, equity_realization_summary


def test_ip_realizes_more_than_oop():
    """IP hand should realize more equity than OOP hand (all else equal)."""
    r_ip  = calculate_equity_realization(raw_equity=0.55, is_ip=True)
    r_oop = calculate_equity_realization(raw_equity=0.55, is_ip=False)
    assert r_ip.realized_equity > r_oop.realized_equity, \
        f'IP ({r_ip.realized_equity:.0%}) should > OOP ({r_oop.realized_equity:.0%})'
    print(f'IP: {r_ip.realized_equity:.0%}  OOP: {r_oop.realized_equity:.0%}')


def test_monster_hand_bonus():
    """Monster hand type should increase realized equity."""
    r_monster = calculate_equity_realization(0.75, is_ip=True, hand_category='怪獸牌')
    r_weak    = calculate_equity_realization(0.75, is_ip=True, hand_category='弱牌')
    assert r_monster.realized_equity > r_weak.realized_equity, \
        f'Monster ({r_monster.realized_equity:.0%}) should > Weak ({r_weak.realized_equity:.0%})'
    print(f'Monster: {r_monster.realized_equity:.0%}  Weak: {r_weak.realized_equity:.0%}')


def test_wet_board_reduces_equity():
    """Wet board should reduce realized equity vs dry board."""
    r_dry = calculate_equity_realization(0.60, is_ip=True, board_texture='乾燥')
    r_wet = calculate_equity_realization(0.60, is_ip=True, board_texture='濕潤')
    assert r_dry.realized_equity > r_wet.realized_equity, \
        f'Dry ({r_dry.realized_equity:.0%}) should > Wet ({r_wet.realized_equity:.0%})'
    print(f'Dry board: {r_dry.realized_equity:.0%}  Wet board: {r_wet.realized_equity:.0%}')


def test_low_spr_high_realization():
    """Low SPR (committed) → higher realization than high SPR."""
    r_low_spr  = calculate_equity_realization(0.58, is_ip=True, spr=2.0)
    r_high_spr = calculate_equity_realization(0.58, is_ip=True, spr=15.0)
    assert r_low_spr.realized_equity > r_high_spr.realized_equity, \
        f'Low SPR ({r_low_spr.realized_equity:.0%}) should > High SPR ({r_high_spr.realized_equity:.0%})'
    print(f'SPR=2: {r_low_spr.realized_equity:.0%}  SPR=15: {r_high_spr.realized_equity:.0%}')


def test_multiway_lowers_realization():
    """More opponents → lower equity realization."""
    r_hu = calculate_equity_realization(0.50, is_ip=True, n_opponents=1)
    r_3w = calculate_equity_realization(0.50, is_ip=True, n_opponents=2)
    r_4w = calculate_equity_realization(0.50, is_ip=True, n_opponents=3)
    assert r_hu.realized_equity > r_3w.realized_equity > r_4w.realized_equity, \
        'Equity realization should decrease as more opponents are added'
    print(f'HU: {r_hu.realized_equity:.0%}  3-way: {r_3w.realized_equity:.0%}  4-way: {r_4w.realized_equity:.0%}')


def test_draw_hand_lower_than_strong():
    """Drawing hand has lower realization factor than strong made hand."""
    r_strong = calculate_equity_realization(0.55, is_ip=True, hand_category='強牌', has_draw=False)
    r_draw   = calculate_equity_realization(0.55, is_ip=True, hand_category='聽牌邊緣', has_draw=True)
    assert r_strong.realized_equity > r_draw.realized_equity, \
        f'Strong hand ({r_strong.realized_equity:.0%}) should > Draw ({r_draw.realized_equity:.0%})'
    print(f'Strong made: {r_strong.realized_equity:.0%}  Draw: {r_draw.realized_equity:.0%}')


def test_er_factor_reasonable_range():
    """ER factor should stay in a reasonable range (0.5-1.3)."""
    for raw in [0.30, 0.50, 0.70, 0.90]:
        for ip in [True, False]:
            for n_opp in [1, 2, 3]:
                r = calculate_equity_realization(raw, is_ip=ip, n_opponents=n_opp)
                assert 0.50 <= r.er_factor <= 1.30, \
                    f'ER factor out of range: {r.er_factor} (raw={raw}, ip={ip}, n_opp={n_opp})'
    print('All ER factors in range 0.50-1.30')


def test_realized_equity_clamped():
    """Realized equity should stay in [0.01, 0.99]."""
    r_high = calculate_equity_realization(0.99, is_ip=True, hand_category='怪獸牌')
    r_low  = calculate_equity_realization(0.01, is_ip=False, n_opponents=3)
    assert r_high.realized_equity <= 0.99
    assert r_low.realized_equity  >= 0.01
    print(f'High: {r_high.realized_equity:.0%}  Low: {r_low.realized_equity:.0%}')


def test_adjustments_captured():
    """All adjustment reasons should be listed."""
    r = calculate_equity_realization(
        0.55,
        is_ip=False,
        hand_category='中等',
        board_texture='濕潤',
        spr=12.0,
        n_opponents=2,
    )
    assert len(r.adjustments_zh) >= 3, f'Expected ≥3 adjustments, got {r.adjustments_zh}'
    print(f'Adjustments: {r.adjustments_zh}')


def test_summary_format():
    """Summary should contain [實現勝率] and be ≤80 chars."""
    r = calculate_equity_realization(
        0.55, is_ip=False, hand_category='頂對強踢', board_texture='濕潤',
    )
    s = equity_realization_summary(r)
    assert '[實現勝率]' in s, f'Missing header: {s}'
    assert len(s) <= 80, f'Too long ({len(s)}): {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_equity_delta_direction():
    """Delta should be positive for IP monster, negative for OOP weak hand."""
    r_pos = calculate_equity_realization(0.60, is_ip=True, hand_category='超強牌')
    r_neg = calculate_equity_realization(0.60, is_ip=False, hand_category='弱牌', n_opponents=3)
    assert r_pos.equity_delta > 0, f'IP monster should have positive delta: {r_pos.equity_delta}'
    assert r_neg.equity_delta < 0, f'OOP weak multiway should have negative delta: {r_neg.equity_delta}'
    print(f'IP monster delta: {r_pos.equity_delta:+.0%}  OOP weak delta: {r_neg.equity_delta:+.0%}')


if __name__ == '__main__':
    tests = [
        test_ip_realizes_more_than_oop,
        test_monster_hand_bonus,
        test_wet_board_reduces_equity,
        test_low_spr_high_realization,
        test_multiway_lowers_realization,
        test_draw_hand_lower_than_strong,
        test_er_factor_reasonable_range,
        test_realized_equity_clamped,
        test_adjustments_captured,
        test_summary_format,
        test_equity_delta_direction,
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
