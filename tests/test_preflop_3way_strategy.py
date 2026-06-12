"""Tests for preflop_3way_strategy.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_3way_strategy import (
    analyze_3way_preflop, ThreeWayPreflopAdvice, p3w_one_liner,
    _squeeze_size, _cold_call_action, _3way_cbet_freq,
    SQUEEZE_MULTIPLIER, COLD_CALL_IP_HANDS,
)


def _p3w(**kw):
    defaults = dict(
        hero_hand='TT',
        hero_position='btn',
        opener_position='co',
        n_callers=1,
        open_size_bb=3.0,
        stack_bb=100.0,
        opener_vpip=0.28,
        caller_fold_to_3bet=0.55,
        opener_fold_to_3bet=0.50,
        board_texture='dry',
        hand_category_postflop='top_pair',
    )
    defaults.update(kw)
    return analyze_3way_preflop(**defaults)


def test_returns_three_way_preflop_advice():
    r = _p3w()
    assert isinstance(r, ThreeWayPreflopAdvice)


def test_squeeze_size_formula():
    size = _squeeze_size(3.0, 1)
    # 3.0 * 3 + 1 * 3.0 = 12.0
    assert abs(size - 12.0) < 0.1


def test_squeeze_size_more_callers():
    size1 = _squeeze_size(3.0, 1)
    size2 = _squeeze_size(3.0, 2)
    assert size2 > size1


def test_aa_3bets():
    action = _cold_call_action('AA', 'btn', 'co', 100.0, 0.28, 1)
    assert '3bet' in action


def test_kk_3bets():
    action = _cold_call_action('KK', 'co', 'hj', 100.0, 0.28, 1)
    assert '3bet' in action


def test_tt_cold_calls_ip():
    action = _cold_call_action('TT', 'btn', 'co', 100.0, 0.28, 1)
    assert 'cold_call' in action


def test_small_pair_ip_set_mines():
    action = _cold_call_action('33', 'btn', 'co', 100.0, 0.28, 1)
    assert 'set_mine' in action or 'cold_call' in action


def test_oop_hand_folds():
    action = _cold_call_action('T9s', 'bb', 'co', 100.0, 0.28, 1)
    assert 'oop' in action or 'fold' in action


def test_3way_cbet_lower_than_hu():
    cbet_3way = _3way_cbet_freq('dry', 'ip', 'top_pair')
    # 3-way cbet should be significantly less than HU cbet (~65%)
    assert cbet_3way < 0.60


def test_wet_board_lower_cbet():
    dry = _3way_cbet_freq('dry', 'ip', 'top_pair')
    wet = _3way_cbet_freq('wet', 'ip', 'top_pair')
    assert wet < dry


def test_oop_lower_cbet():
    ip_cbet = _3way_cbet_freq('dry', 'ip', 'top_pair')
    oop_cbet = _3way_cbet_freq('dry', 'oop', 'top_pair')
    assert oop_cbet <= ip_cbet


def test_set_high_cbet():
    set_cbet = _3way_cbet_freq('dry', 'ip', 'set')
    assert set_cbet >= 0.60


def test_cold_call_action_stored():
    r = _p3w()
    assert len(r.cold_call_action) > 0


def test_squeeze_size_stored():
    r = _p3w()
    assert r.squeeze_size_bb > 0


def test_dead_money_stored():
    r = _p3w()
    # dead money = open_size * (n_callers + 1)
    expected = 3.0 * 2
    assert abs(r.dead_money_bb - expected) < 0.1


def test_squeeze_ev_is_float():
    r = _p3w()
    assert isinstance(r.squeeze_ev_est, float)


def test_cbet_freq_stored():
    r = _p3w()
    assert 0.0 < r.three_way_cbet_freq < 1.0


def test_is_good_squeeze_is_bool():
    r = _p3w()
    assert isinstance(r.is_good_squeeze_spot, bool)


def test_tips_populated():
    r = _p3w()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _p3w()
    line = p3w_one_liner(r)
    assert '[P3W' in line
    assert 'sqz_ev=' in line
    assert '3way_cbet=' in line


def test_aa_squeeze_ev_positive():
    r = _p3w(hero_hand='AA', opener_fold_to_3bet=0.55, caller_fold_to_3bet=0.60)
    assert r.squeeze_ev_est > 0


def test_more_callers_more_dead_money():
    r1 = _p3w(n_callers=1)
    r2 = _p3w(n_callers=2)
    assert r2.dead_money_bb > r1.dead_money_bb


def test_cold_call_ip_hands_has_pairs():
    assert '77' in COLD_CALL_IP_HANDS.get('set_mine', set())


def test_squeeze_multiplier_is_3():
    assert SQUEEZE_MULTIPLIER == 3.0


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
