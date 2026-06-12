"""Tests for river_bet_size_selector.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_bet_size_selector import (
    select_river_size, RiverSizeSelection, rss_one_liner,
    _base_call_rate, _size_discount, _texture_factor,
    _call_rate_at_size, _ev_at_size, CANDIDATE_SIZES,
)


def _rss(**kw):
    defaults = dict(
        hero_equity=0.70,
        pot_bb=30.0,
        hero_stack_bb=100.0,
        villain_wtsd=0.32,
        villain_vpip=0.30,
        villain_af=2.0,
        board_texture='dry',
        hero_hand_type='value',
    )
    defaults.update(kw)
    return select_river_size(**defaults)


def test_returns_river_size_selection():
    r = _rss()
    assert isinstance(r, RiverSizeSelection)


def test_optimal_size_is_candidate():
    r = _rss()
    assert r.optimal_size_pct in CANDIDATE_SIZES


def test_6_size_options():
    r = _rss()
    assert len(r.size_options) == 6


def test_size_options_ranked():
    r = _rss()
    evs = [o.ev_bb for o in r.size_options]
    assert evs == sorted(evs, reverse=True)


def test_base_call_rate_increases_with_wtsd():
    cr_low  = _base_call_rate(0.22, 0.25)
    cr_high = _base_call_rate(0.42, 0.40)
    assert cr_high > cr_low


def test_size_discount_small_bet_bigger():
    disc_small = _size_discount(0.33)
    disc_large = _size_discount(1.50)
    assert disc_small > disc_large


def test_texture_factor_wet_higher():
    assert _texture_factor('wet') > _texture_factor('dry')


def test_call_rate_decreases_with_size():
    base = 0.35
    tex = 1.0
    af = 2.0
    cr_small = _call_rate_at_size(0.33, base, tex, af)
    cr_large = _call_rate_at_size(1.50, base, tex, af)
    assert cr_small > cr_large


def test_ev_value_positive_with_high_equity():
    ev = _ev_at_size(0.50, 30.0, 0.40, 0.80, 'value')
    assert ev > 0.0


def test_ev_bluff_positive_when_fold_eq_high():
    ev = _ev_at_size(0.33, 30.0, 0.20, 0.10, 'bluff')
    # fold_rate = 0.80; pot=30; bet=10
    # ev = 0.80 * 30 - 0.20 * 10 = 24 - 2 = 22
    assert ev > 0.0


def test_ev_bluff_negative_vs_calling_station():
    ev = _ev_at_size(1.0, 30.0, 0.80, 0.05, 'bluff')
    # fold_rate = 0.20; ev = 0.20*30 - 0.80*30 = 6-24 = -18
    assert ev < 0.0


def test_value_optimal_size_reasonable():
    r = _rss(hero_equity=0.85, villain_wtsd=0.25)
    assert r.optimal_size_pct >= 0.67   # high equity + low WTSD → larger sizes


def test_bluff_optimal_size_smaller():
    r_value = _rss(hero_hand_type='value', hero_equity=0.80)
    r_bluff  = _rss(hero_hand_type='bluff', hero_equity=0.05)
    # Bluff should prefer smaller sizes to maximize fold equity / EV
    assert r_bluff.optimal_size_pct <= r_value.optimal_size_pct or r_bluff.optimal_ev_bb < r_value.optimal_ev_bb


def test_optimal_ev_is_best_ev():
    r = _rss()
    for opt in r.size_options:
        assert r.optimal_ev_bb >= opt.ev_bb - 0.01


def test_base_call_rate_stored():
    r = _rss()
    assert 0.0 < r.base_call_rate < 1.0


def test_ev_check_value_bet():
    r = _rss(hero_equity=0.70, hero_hand_type='value')
    assert r.ev_check > 0.0


def test_ev_check_bluff():
    r = _rss(hero_hand_type='bluff')
    assert r.ev_check == 0.0


def test_calling_station_warns():
    r = _rss(villain_wtsd=0.50, hero_hand_type='bluff')
    tips_lower = ' '.join(r.tips).lower()
    assert 'call' in tips_lower or 'station' in tips_lower or 'wtsd' in tips_lower


def test_optimal_size_bb_computed():
    r = _rss(pot_bb=20.0)
    expected = round(r.optimal_size_pct * 20.0, 1)
    assert abs(r.optimal_size_bb - expected) < 0.01


def test_size_option_fields():
    r = _rss()
    for opt in r.size_options:
        assert opt.size_pct in CANDIDATE_SIZES
        assert 0.0 < opt.call_rate < 1.0
        assert isinstance(opt.ev_bb, float)
        assert opt.rank >= 1


def test_tips_populated():
    r = _rss()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rss()
    line = rss_one_liner(r)
    assert '[RSS' in line
    assert 'EV=' in line
    assert 'call=' in line


def test_thin_value_lower_ev_than_value():
    r_v = _rss(hero_hand_type='value', hero_equity=0.65)
    r_t = _rss(hero_hand_type='thin_value', hero_equity=0.65)
    assert r_t.optimal_ev_bb <= r_v.optimal_ev_bb


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
