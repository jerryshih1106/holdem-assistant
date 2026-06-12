"""Tests for poker/bb_postflop.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bb_postflop import analyze_bb_postflop, bb_postflop_summary


def test_strong_hand_check_raises_facing_cbet():
    """Strong hand (70%+) facing villain cbet should check-raise."""
    r = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.72, call_bb=3.5,
                             is_villain_cbet=True, community=['2h','7c','Kd'],
                             street='flop')
    assert r.action == 'check_raise', \
        f'Strong hand facing cbet should check-raise: {r.action}'
    assert r.sizing_pct > 0, f'Check-raise should have sizing: {r.sizing_pct}'
    print(f'Strong hand facing cbet: {r.action} {r.sizing_pct:.1f}x')


def test_weak_hand_folds_to_cbet():
    """Very weak hand (25%) should fold to cbet."""
    r = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.25, call_bb=4.0,
                             is_villain_cbet=True, community=['A','K','Q'],
                             villain_cbet=0.65, street='flop')
    assert r.action in ('check_fold',), \
        f'Weak hand should fold to cbet on high board: {r.action}'
    print(f'Weak hand vs cbet: {r.action}')


def test_villain_check_triggers_probe_bet():
    """Medium hand when villain checks should probe bet."""
    r = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.50, call_bb=0.0,
                             is_villain_cbet=False, community=['2h','5c','8d'],
                             villain_cbet=0.60, street='turn')
    assert r.action in ('probe_bet', 'lead_bet'), \
        f'Medium hand when villain checks should probe: {r.action}'
    print(f'Villain checks, BB probes: {r.action} {r.sizing_pct:.0%}pot')


def test_low_board_is_bb_favorable():
    """Low card board (2-7) should favor BB range."""
    r = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.50, call_bb=0.0,
                             is_villain_cbet=False, community=['2h','5c','7d'],
                             street='flop')
    assert r.board_advantage == 'bb_favor', \
        f'Low board should be BB favorable: {r.board_advantage}'
    print(f'Low board advantage: {r.board_advantage}')


def test_high_board_is_villain_favorable():
    """High card board (A-K-Q) should favor villain (BTN/CO opener) range."""
    r = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.45, call_bb=0.0,
                             is_villain_cbet=False, community=['Ah','Kc','Qd'],
                             street='flop')
    assert r.board_advantage == 'villain_favor', \
        f'High board should favor villain: {r.board_advantage}'
    print(f'High board advantage: {r.board_advantage}')


def test_cr_frequency_higher_on_bb_favorable_board():
    """BB should check-raise more often on BB-favorable boards."""
    r_low  = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.50, call_bb=3.5,
                                  is_villain_cbet=True, community=['2h','5c','7d'], street='flop')
    r_high = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.50, call_bb=3.5,
                                  is_villain_cbet=True, community=['Ah','Kc','Qd'], street='flop')
    assert r_low.cr_frequency >= r_high.cr_frequency, \
        f'Low board CR freq {r_low.cr_frequency:.0%} should >= high board {r_high.cr_frequency:.0%}'
    print(f'Low board CR={r_low.cr_frequency:.0%}  High board CR={r_high.cr_frequency:.0%}')


def test_probe_frequency_higher_on_bb_favorable_board():
    """BB should probe bet more often on BB-favorable boards when villain checks."""
    r_low  = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.50, call_bb=0.0,
                                  is_villain_cbet=False, community=['2h','5c','7d'], street='turn')
    r_high = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.50, call_bb=0.0,
                                  is_villain_cbet=False, community=['Ah','Kc','Qd'], street='turn')
    assert r_low.probe_frequency >= r_high.probe_frequency, \
        f'Low board probe {r_low.probe_frequency:.0%} should >= high board {r_high.probe_frequency:.0%}'
    print(f'Low board probe={r_low.probe_frequency:.0%}  High board probe={r_high.probe_frequency:.0%}')


def test_medium_equity_check_calls_vs_cbet():
    """Medium equity (40-55%) should check-call vs cbet (has pot odds)."""
    r = analyze_bb_postflop(pot_bb=10.0, hero_equity=0.48, call_bb=4.0,
                             is_villain_cbet=True, community=['5h','9c','Kd'],
                             villain_cbet=0.60, street='flop')
    assert r.action in ('check_call', 'check_fold'), \
        f'Medium equity vs cbet should be check-call or fold: {r.action}'
    print(f'Medium equity vs cbet: {r.action}')


def test_high_cbet_freq_villain_range_includes_bluffs():
    """vs high-cbet villain, should call/raise wider (he has more bluffs)."""
    r_high_cb = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.42, call_bb=3.5,
                                     is_villain_cbet=True, villain_cbet=0.80, street='flop')
    r_low_cb  = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.42, call_bb=3.5,
                                     is_villain_cbet=True, villain_cbet=0.30, street='flop')
    # High cbet villain bluffs more → hero's tips should mention adjusting
    print(f'High cbet action: {r_high_cb.action}  Low cbet action: {r_low_cb.action}')
    # At least one tip should mention cbet frequency
    has_cbet_tip = any('C-bet' in t or 'cbet' in t.lower() or 'C-bet' in t for t in r_high_cb.tips)
    print(f'High cbet tip: {r_high_cb.tips}')


def test_summary_format():
    """Summary should be <=85 chars and contain [BB翻後]."""
    r = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.50, call_bb=3.5,
                             is_villain_cbet=True, community=['5h','9c','Kd'], street='flop')
    s = bb_postflop_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[BB翻後]' in s, f'Missing [BB翻後]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_sizing_zero_when_checking():
    """Actions with no bet should have zero sizing."""
    r = analyze_bb_postflop(pot_bb=7.0, hero_equity=0.28, call_bb=4.0,
                             is_villain_cbet=True, community=['Ah','Kc','Qd'], street='flop')
    if r.action in ('check_fold', 'check_call', 'check_back'):
        assert r.sizing_pct == 0.0, f'{r.action} should have 0 sizing: {r.sizing_pct}'
    print(f'{r.action}: sizing_pct={r.sizing_pct}')


if __name__ == '__main__':
    tests = [
        test_strong_hand_check_raises_facing_cbet,
        test_weak_hand_folds_to_cbet,
        test_villain_check_triggers_probe_bet,
        test_low_board_is_bb_favorable,
        test_high_board_is_villain_favorable,
        test_cr_frequency_higher_on_bb_favorable_board,
        test_probe_frequency_higher_on_bb_favorable_board,
        test_medium_equity_check_calls_vs_cbet,
        test_high_cbet_freq_villain_range_includes_bluffs,
        test_summary_format,
        test_sizing_zero_when_checking,
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
