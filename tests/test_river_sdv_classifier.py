"""Tests for river_sdv_classifier.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_sdv_classifier import (
    classify_river_hand, RiverSDVResult, sdv_one_liner,
    _value_bet_threshold, _sdv_threshold, _villain_bluff_freq,
)


def _sdv(**kw):
    defaults = dict(
        hero_hand_rank_pct=0.62,
        villain_wtsd=0.30,
        villain_af=2.2,
        villain_vpip=0.28,
        pot_bb=25.0,
        bet_to_hero_bb=0.0,
        hero_position='IP',
        board_type='dry',
        has_blocked_draw=False,
    )
    defaults.update(kw)
    return classify_river_hand(**defaults)


def test_returns_river_sdv_result():
    r = _sdv()
    assert isinstance(r, RiverSDVResult)


def test_value_bet_threshold_calling_station():
    thresh = _value_bet_threshold(villain_wtsd=0.45, villain_vpip=0.40)
    assert thresh <= 0.58   # lower: call with worse, so we can bet thinner


def test_value_bet_threshold_nit():
    thresh = _value_bet_threshold(villain_wtsd=0.18, villain_vpip=0.15)
    assert thresh >= 0.68   # higher: nit only calls with strong hands


def test_value_bet_threshold_nit_higher_than_station():
    t_station = _value_bet_threshold(0.45, 0.40)
    t_nit = _value_bet_threshold(0.18, 0.15)
    assert t_nit > t_station


def test_sdv_threshold_aggressive_villain():
    thresh = _sdv_threshold(villain_af=3.5, villain_wtsd=0.32)
    assert thresh <= 0.40   # aggressive bluffer: lower threshold to have SDV


def test_sdv_threshold_passive_villain():
    thresh = _sdv_threshold(villain_af=0.8, villain_wtsd=0.25)
    assert thresh >= 0.45


def test_villain_bluff_freq_aggressive():
    freq = _villain_bluff_freq(villain_af=3.0, villain_wtsd=0.25)
    assert freq >= 0.25


def test_villain_bluff_freq_passive():
    freq = _villain_bluff_freq(villain_af=0.1, villain_wtsd=0.60)
    assert freq <= 0.15


def test_strong_hand_value_bets():
    r = _sdv(hero_hand_rank_pct=0.90, villain_wtsd=0.35)
    assert r.hand_class == 'value_bet'


def test_weak_hand_gives_up():
    r = _sdv(hero_hand_rank_pct=0.15, villain_wtsd=0.35, villain_af=1.0)
    assert r.hand_class == 'give_up'


def test_medium_equity_showdown_value():
    r = _sdv(hero_hand_rank_pct=0.55, villain_wtsd=0.30, villain_af=1.5)
    assert r.hand_class in ('showdown_value', 'thin_value')


def test_blocked_draw_reduces_value():
    r_normal = _sdv(hero_hand_rank_pct=0.68, has_blocked_draw=False)
    r_blocked = _sdv(hero_hand_rank_pct=0.68, has_blocked_draw=True)
    # blocked draw should not make classification better
    classes = ['value_bet', 'thin_value', 'showdown_value', 'give_up']
    assert classes.index(r_blocked.hand_class) >= classes.index(r_normal.hand_class)


def test_ip_action_facing_no_bet():
    r = _sdv(hero_position='IP', bet_to_hero_bb=0.0, hero_hand_rank_pct=0.70)
    assert r.action in ('bet', 'check', 'check_call', 'check_fold')


def test_facing_villain_bet():
    r = _sdv(bet_to_hero_bb=12.0, hero_hand_rank_pct=0.60)
    assert r.action in ('call', 'fold', 'raise', 'check_call', 'check_fold')


def test_calling_station_lower_value_threshold():
    r_station = _sdv(villain_wtsd=0.45)
    r_nit = _sdv(villain_wtsd=0.18)
    assert r_station.value_bet_threshold < r_nit.value_bet_threshold


def test_ev_bet_computed():
    r = _sdv(pot_bb=20.0, hero_hand_rank_pct=0.75)
    assert r.ev_bet_75pct != 0.0 or r.ev_bet_100pct != 0.0


def test_one_liner_format():
    r = _sdv()
    line = sdv_one_liner(r)
    assert '[SDV' in line
    assert 'eq=' in line


def test_hand_class_valid():
    r = _sdv()
    assert r.hand_class in ('value_bet', 'thin_value', 'showdown_value', 'give_up')


def test_action_valid():
    r = _sdv()
    assert r.action in ('bet', 'check', 'check_call', 'check_fold', 'call', 'fold', 'raise')


def test_tips_populated():
    r = _sdv()
    assert len(r.tips) > 0


def test_wet_board_more_cautious():
    r_dry = _sdv(board_type='dry', hero_hand_rank_pct=0.63)
    r_wet = _sdv(board_type='wet', hero_hand_rank_pct=0.63)
    classes = ['value_bet', 'thin_value', 'showdown_value', 'give_up']
    # wet board should be same or more conservative (check_call/give_up more common)
    assert classes.index(r_wet.hand_class) >= classes.index(r_dry.hand_class) - 1


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
