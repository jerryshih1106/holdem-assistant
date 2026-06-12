"""Tests for poker/heads_up.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.heads_up import analyze_heads_up, heads_up_summary


def test_btn_strong_hand_opens():
    """BTN (SB) in HU with strong hand should open."""
    r = analyze_heads_up(hero_hand_pct=0.70, hero_is_btn=True, community=[])
    assert r.preflop_action == 'open', \
        f'Strong hand BTN should open: {r.preflop_action}'
    assert r.is_preflop
    print(f'BTN strong: action={r.preflop_action}  open_freq={r.open_frequency:.0%}')


def test_btn_trash_hand_folds():
    """BTN with very weak hand (bottom 12%) should fold even in HU."""
    r = analyze_heads_up(hero_hand_pct=0.05, hero_is_btn=True, community=[])
    assert r.preflop_action == 'fold', \
        f'Trash hand BTN should fold: {r.preflop_action}'
    print(f'BTN trash: action={r.preflop_action}')


def test_btn_opens_much_wider_than_6max():
    """BTN HU open frequency should be much wider than 6-max (~42%)."""
    r = analyze_heads_up(hero_hand_pct=0.50, hero_is_btn=True, community=[])
    assert r.open_frequency > 0.60, \
        f'HU BTN should open >60%: {r.open_frequency:.0%}'
    print(f'HU BTN open freq: {r.open_frequency:.0%}')


def test_bb_defends_wide():
    """BB in HU should defend very wide (>70%)."""
    r = analyze_heads_up(hero_hand_pct=0.50, hero_is_btn=False, community=[])
    assert r.open_frequency > 0.70, \
        f'HU BB defend should be >70%: {r.open_frequency:.0%}'
    print(f'HU BB defend freq: {r.open_frequency:.0%}')


def test_bb_strong_hand_3bets():
    """BB with very strong hand should 3-bet."""
    r = analyze_heads_up(hero_hand_pct=0.95, hero_is_btn=False, community=[])
    assert r.preflop_action == 'threebet', \
        f'Strong BB should 3-bet: {r.preflop_action}'
    print(f'BB strong hand: action={r.preflop_action}')


def test_bb_medium_hand_calls():
    """BB with medium hand should call (not 3-bet, not fold)."""
    r = analyze_heads_up(hero_hand_pct=0.60, hero_is_btn=False, community=[])
    assert r.preflop_action in ('call_or_3bet',), \
        f'Medium BB should call: {r.preflop_action}'
    print(f'BB medium hand: action={r.preflop_action}')


def test_hu_cbet_higher_than_6max():
    """HU c-bet frequency should be higher than typical 6-max (~60%)."""
    r = analyze_heads_up(hero_hand_pct=0.50, hero_is_btn=True,
                          community=['Ah', '7c', '2d'], board_type='dry')
    assert r.cbet_freq > 0.65, \
        f'HU cbet should be >65%: {r.cbet_freq:.0%}'
    print(f'HU cbet freq (dry): {r.cbet_freq:.0%}')


def test_hu_bluff_catch_widens_vs_lag():
    """vs LAG in HU, bluff-catch equity should be lower (call wider)."""
    vs_lag = analyze_heads_up(hero_hand_pct=0.40, hero_is_btn=False,
                               community=['Kh', '7c', '2d'],
                               villain_vpip=0.38, villain_af=3.5, villain_hands=30)
    vs_nit = analyze_heads_up(hero_hand_pct=0.40, hero_is_btn=False,
                               community=['Kh', '7c', '2d'],
                               villain_vpip=0.15, villain_af=0.9, villain_hands=30)
    assert vs_lag.bluff_catch_equity < vs_nit.bluff_catch_equity, \
        f'vs LAG catch {vs_lag.bluff_catch_equity:.0%} should be < vs Nit {vs_nit.bluff_catch_equity:.0%}'
    print(f'vs LAG catch={vs_lag.bluff_catch_equity:.0%}  vs Nit catch={vs_nit.bluff_catch_equity:.0%}')


def test_strong_hand_bets_postflop_hu():
    """Strong hand in HU postflop should recommend betting."""
    r = analyze_heads_up(hero_hand_pct=0.80, hero_is_btn=True,
                          community=['Ah', '7c', '2d'], call_amount=0.0)
    assert r.postflop_action in ('bet_value',), \
        f'Strong HU should bet: {r.postflop_action}'
    assert r.should_bet_value
    print(f'Strong HU postflop: {r.postflop_action}')


def test_weak_hand_oop_faces_bet_folds():
    """Weak hand OOP facing bet in HU should fold."""
    r = analyze_heads_up(hero_hand_pct=0.20, hero_is_btn=False,
                          community=['Kh', '7c', '2d'],
                          call_amount=10.0, pot_bb=20.0,
                          villain_vpip=0.25, villain_af=1.5, villain_hands=25)
    assert r.postflop_action == 'fold', \
        f'Weak OOP facing bet should fold: {r.postflop_action}'
    print(f'Weak OOP HU: action={r.postflop_action}  catch_thresh={r.bluff_catch_equity:.0%}')


def test_nit_cbet_higher_than_fish():
    """vs Nit in HU, c-bet frequency should be higher than vs Fish."""
    vs_nit = analyze_heads_up(hero_hand_pct=0.50, hero_is_btn=True,
                               community=['7c', '3h', '2d'], board_type='dry',
                               villain_vpip=0.16, villain_af=0.9, villain_hands=30)
    vs_fish = analyze_heads_up(hero_hand_pct=0.50, hero_is_btn=True,
                                community=['7c', '3h', '2d'], board_type='dry',
                                villain_vpip=0.55, villain_af=2.0, villain_hands=30)
    assert vs_nit.cbet_freq >= vs_fish.cbet_freq, \
        f'vs Nit cbet {vs_nit.cbet_freq:.0%} should be >= vs Fish {vs_fish.cbet_freq:.0%}'
    print(f'vs Nit cbet={vs_nit.cbet_freq:.0%}  vs Fish cbet={vs_fish.cbet_freq:.0%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [HU單挑]."""
    r = analyze_heads_up(hero_hand_pct=0.65, hero_is_btn=True, community=[])
    s = heads_up_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[HU單挑]' in s, f'Missing [HU單挑]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_btn_strong_hand_opens,
        test_btn_trash_hand_folds,
        test_btn_opens_much_wider_than_6max,
        test_bb_defends_wide,
        test_bb_strong_hand_3bets,
        test_bb_medium_hand_calls,
        test_hu_cbet_higher_than_6max,
        test_hu_bluff_catch_widens_vs_lag,
        test_strong_hand_bets_postflop_hu,
        test_weak_hand_oop_faces_bet_folds,
        test_nit_cbet_higher_than_fish,
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
