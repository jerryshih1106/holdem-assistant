"""Tests for poker/river_medium.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_medium import analyze_river_medium, river_medium_summary


def test_strong_medium_ip_safe_board_bets():
    """Strong medium hand (58%) IP on safe board should thin value bet."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.58, is_ip=True,
                              board_danger='safe', villain_wtsd=0.32)
    assert r.action == 'thin_value_bet', \
        f'Strong medium IP safe should thin bet: {r.action}'
    assert r.bet_size_pct > 0.0
    print(f'Strong medium IP safe: {r.action} {r.bet_size_pct:.0%}pot')


def test_dangerous_board_aggressive_villain_check_folds():
    """Medium hand on dangerous board vs aggressive villain should check-fold."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.50, is_ip=True,
                              board_danger='dangerous',
                              villain_af=3.0, villain_vpip=0.30)
    assert r.action in ('check_fold', 'check_call'), \
        f'Dangerous board vs aggro: {r.action}'
    print(f'Dangerous+aggro: {r.action}')


def test_calling_station_gets_thin_bet():
    """vs calling station (WTSD=0.45), hero should thin value bet even weak medium."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.44, is_ip=True,
                              board_danger='safe',
                              villain_wtsd=0.45, villain_vpip=0.50, villain_af=1.2)
    assert r.action == 'thin_value_bet', \
        f'vs calling station with weak medium should thin bet: {r.action}'
    print(f'vs calling station (WTSD=45%): {r.action} {r.bet_size_pct:.0%}pot')


def test_aggressive_villain_oop_blocking_bet():
    """OOP vs aggressive villain (AF=2.8) should blocking bet."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.56, is_ip=False,
                              board_danger='safe',
                              villain_af=2.8, villain_vpip=0.35)
    assert r.action == 'blocking_bet', \
        f'OOP vs aggressive should blocking bet: {r.action}'
    assert r.bet_size_pct <= 0.33, \
        f'Blocking bet should be small (<33%): {r.bet_size_pct:.0%}'
    print(f'OOP vs aggro: {r.action} {r.bet_size_pct:.0%}pot')


def test_passive_tight_check_folds():
    """vs passive tight villain, check then fold to bet (they have it)."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.44, is_ip=True,
                              board_danger='safe',
                              villain_af=0.6, villain_vpip=0.20, villain_wtsd=0.25)
    assert r.action in ('check_fold',), \
        f'vs passive tight weak medium should check-fold: {r.action}'
    print(f'vs passive tight: {r.action}')


def test_aggressive_villain_triggers_check_call():
    """vs aggressive villain (AF>2.5), hero should check-call to trap bluffs."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.52, is_ip=True,
                              board_danger='safe',
                              villain_af=3.2, villain_vpip=0.32, villain_wtsd=0.30)
    assert r.action in ('check_call',), \
        f'vs aggro should check-call: {r.action}'
    print(f'vs aggressive: {r.action}')


def test_bet_size_ip_larger_than_oop():
    """IP thin value bet should be larger than OOP blocking bet."""
    r_ip  = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.57, is_ip=True,
                                  board_danger='safe', villain_wtsd=0.35)
    r_oop = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.57, is_ip=False,
                                  board_danger='safe', villain_af=2.5)
    if r_ip.bet_size_pct > 0 and r_oop.bet_size_pct > 0:
        assert r_ip.bet_size_pct >= r_oop.bet_size_pct, \
            f'IP bet {r_ip.bet_size_pct:.0%} should >= OOP {r_oop.bet_size_pct:.0%}'
    print(f'IP bet={r_ip.bet_size_pct:.0%}  OOP bet={r_oop.bet_size_pct:.0%}')


def test_ev_reflects_action_direction():
    """Better action should have higher EV."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.56, is_ip=True,
                              board_danger='safe', villain_wtsd=0.35)
    print(f'EVs: bet={r.ev_bet:+.1f}BB  check_call={r.ev_check_call:+.1f}BB  '
          f'check_fold={r.ev_check_fold:+.1f}BB')
    # check_call should be > check_fold (calling dominant over folding when you have equity)
    assert r.ev_check_call >= r.ev_check_fold, \
        f'check_call EV should >= check_fold EV: {r.ev_check_call} vs {r.ev_check_fold}'


def test_moderate_board_thin_bet_smaller():
    """Thin value bet on moderate board should be smaller than on safe board."""
    r_safe = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.58, is_ip=True,
                                   board_danger='safe')
    r_mod  = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.58, is_ip=True,
                                   board_danger='moderate')
    if r_safe.action == r_mod.action == 'thin_value_bet':
        assert r_safe.bet_size_pct >= r_mod.bet_size_pct, \
            f'Safe bet {r_safe.bet_size_pct:.0%} should >= moderate {r_mod.bet_size_pct:.0%}'
    print(f'Safe bet={r_safe.bet_size_pct:.0%}  Moderate bet={r_mod.bet_size_pct:.0%}')


def test_raised_thin_bet_should_not_call():
    """After thin value bet, hero should NOT call a raise (medium hand)."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.55, is_ip=True,
                              board_danger='safe')
    if r.action == 'thin_value_bet':
        assert not r.call_if_raised, \
            f'After thin bet, should fold to raise: call_if_raised={r.call_if_raised}'
    print(f'Thin bet call_if_raised: {r.call_if_raised} (expected False)')


def test_summary_format():
    """Summary should be <=85 chars and contain [河牌中等]."""
    r = analyze_river_medium(pot_bb=20.0, hero_hand_pct=0.52, is_ip=True,
                              board_danger='safe')
    s = river_medium_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[河牌中等]' in s, f'Missing [河牌中等]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_strong_medium_ip_safe_board_bets,
        test_dangerous_board_aggressive_villain_check_folds,
        test_calling_station_gets_thin_bet,
        test_aggressive_villain_oop_blocking_bet,
        test_passive_tight_check_folds,
        test_aggressive_villain_triggers_check_call,
        test_bet_size_ip_larger_than_oop,
        test_ev_reflects_action_direction,
        test_moderate_board_thin_bet_smaller,
        test_raised_thin_bet_should_not_call,
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
