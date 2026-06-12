"""Tests for poker/multiway_call.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway_call import analyze_multiway_call, multiway_call_summary


def test_multiway_requires_more_equity_than_hu():
    """3-way pot should require more equity than heads-up pot odds."""
    # HU: call 5 into pot 10 → need 33%
    # 3-way: same bet but n_behind=1 → threshold higher
    r_hw = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.40,
                                  n_opponents=1, n_behind=0)   # HU baseline
    r_mw = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.40,
                                  n_opponents=2, n_behind=1)   # 3-way
    assert r_mw.equity_threshold > r_hw.equity_threshold, \
        f'3-way threshold {r_mw.equity_threshold:.0%} should > HU {r_hw.equity_threshold:.0%}'
    print(f'HU threshold={r_hw.equity_threshold:.0%}  3-way threshold={r_mw.equity_threshold:.0%}')


def test_4way_threshold_higher_than_3way():
    """4-way pot should require more equity than 3-way."""
    r_3 = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.50,
                                 n_opponents=2, n_behind=1)
    r_4 = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.50,
                                 n_opponents=3, n_behind=2)
    assert r_4.equity_threshold >= r_3.equity_threshold, \
        f'4-way threshold {r_4.equity_threshold:.0%} should >= 3-way {r_3.equity_threshold:.0%}'
    print(f'3-way={r_3.equity_threshold:.0%}  4-way={r_4.equity_threshold:.0%}')


def test_strong_equity_calls():
    """Strong equity well above threshold should recommend call."""
    r = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.70,
                               n_opponents=2, n_behind=0)
    assert r.action in ('call', 'call_wide'), \
        f'70% equity should call in 3-way: {r.action}'
    print(f'70% equity in 3-way: {r.action}')


def test_weak_equity_folds():
    """Weak equity below threshold should fold."""
    r = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.20,
                               n_opponents=3, n_behind=1)
    assert r.action == 'fold', f'20% equity in 4-way should fold: {r.action}'
    print(f'20% equity in 4-way: {r.action}')


def test_bluff_not_viable_in_multiway():
    """Bluffing should not be viable in 4+ player pots."""
    r = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.30,
                               n_opponents=3, n_behind=2)
    assert not r.bluff_viable, f'Bluffing should not be viable in 4-way: {r.bluff_viable}'
    print(f'4-way bluff_viable: {r.bluff_viable} (expected False)')


def test_multiway_fold_equity_decreases_with_opponents():
    """More opponents → lower fold equity for bluffs."""
    r2 = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.30, n_opponents=2)
    r3 = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.30, n_opponents=3)
    r4 = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.30, n_opponents=4)
    assert r2.multiway_fold_equity > r3.multiway_fold_equity > r4.multiway_fold_equity, \
        f'Fold equity should decrease: {r2.multiway_fold_equity:.0%}>{r3.multiway_fold_equity:.0%}>{r4.multiway_fold_equity:.0%}'
    print(f'Fold equity: 3-way={r2.multiway_fold_equity:.0%} 4-way={r3.multiway_fold_equity:.0%} 5-way={r4.multiway_fold_equity:.0%}')


def test_players_behind_increase_threshold():
    """More players behind → higher equity threshold."""
    r0 = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.40,
                                n_opponents=2, n_behind=0)
    r2 = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.40,
                                n_opponents=2, n_behind=2)
    assert r2.equity_threshold > r0.equity_threshold, \
        f'2 behind {r2.equity_threshold:.0%} should > 0 behind {r0.equity_threshold:.0%}'
    print(f'0 behind threshold={r0.equity_threshold:.0%}  2 behind threshold={r2.equity_threshold:.0%}')


def test_nit_has_higher_fold_rate():
    """Nit (low VPIP) should have higher estimated fold rate."""
    r_nit  = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.40,
                                    n_opponents=2, villain_vpip=0.15)
    r_fish = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.40,
                                    n_opponents=2, villain_vpip=0.55)
    assert r_nit.single_villain_fold_rate > r_fish.single_villain_fold_rate, \
        f'Nit fold rate {r_nit.single_villain_fold_rate:.0%} should > fish {r_fish.single_villain_fold_rate:.0%}'
    print(f'Nit fold rate={r_nit.single_villain_fold_rate:.0%}  Fish fold rate={r_fish.single_villain_fold_rate:.0%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [多人跟注]."""
    r = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.45, n_opponents=2)
    s = multiway_call_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[多人跟注]' in s, f'Missing [多人跟注]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_pot_odds_is_minimum_threshold():
    """Threshold should always be >= basic pot odds."""
    for n_opp in [2, 3, 4]:
        r = analyze_multiway_call(pot_bb=10.0, call_bb=5.0, hero_equity=0.50, n_opponents=n_opp)
        assert r.equity_threshold >= r.pot_odds_only, \
            f'Threshold {r.equity_threshold:.0%} should >= pot odds {r.pot_odds_only:.0%} at {n_opp} opponents'
    print('Threshold always >= pot odds: OK')


if __name__ == '__main__':
    tests = [
        test_multiway_requires_more_equity_than_hu,
        test_4way_threshold_higher_than_3way,
        test_strong_equity_calls,
        test_weak_equity_folds,
        test_bluff_not_viable_in_multiway,
        test_multiway_fold_equity_decreases_with_opponents,
        test_players_behind_increase_threshold,
        test_nit_has_higher_fold_rate,
        test_summary_format,
        test_pot_odds_is_minimum_threshold,
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
