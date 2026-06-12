"""Tests for oop_float_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.oop_float_advisor import (
    advise_oop_float, OOPFloatAdvice, ofa_one_liner,
    _villain_check_back_freq, _float_type, _probe_success_rate,
    _should_float, MIN_EQUITY_OOP_FLOAT,
)


def _ofa(**kw):
    defaults = dict(
        hero_hand_category='middle_pair',
        board_texture='semi_wet',
        street='flop',
        cbet_size_pct=0.50,
        villain_af=1.5,
        villain_wtsd=0.30,
        villain_cbet_turn_pct=0.45,
        hero_equity=0.35,
        pot_bb=10.0,
        hero_stack_bb=90.0,
    )
    defaults.update(kw)
    return advise_oop_float(**defaults)


def test_returns_oop_float_advice():
    r = _ofa()
    assert isinstance(r, OOPFloatAdvice)


def test_min_equity_positive():
    assert MIN_EQUITY_OOP_FLOAT > 0.0


def test_villain_check_back_passive():
    cb = _villain_check_back_freq(0.8, 0.30)
    assert cb >= 0.70   # low AF: checks back often


def test_villain_check_back_aggressive():
    cb = _villain_check_back_freq(3.5, 0.70)
    assert cb <= 0.30   # high AF + high cbet turn: rarely checks back


def test_villain_check_back_increases_with_low_cbet_turn():
    cb_low  = _villain_check_back_freq(2.0, 0.25)
    cb_high = _villain_check_back_freq(2.0, 0.65)
    assert cb_low > cb_high


def test_float_type_draw_is_semi_float():
    ft = _float_type('flush_draw', 0.38, 'wet', 0.50)
    assert ft == 'semi_float'


def test_float_type_middle_pair_passive():
    ft = _float_type('middle_pair', 0.35, 'dry', 0.55)
    assert ft in ('float_to_probe', 'float_and_raise')


def test_probe_success_air_high():
    ps = _probe_success_rate('air', 'dry', 0.25, 1.5)
    assert ps >= 0.55


def test_probe_success_top_pair_lower():
    ps_tp  = _probe_success_rate('top_pair', 'dry', 0.30, 2.0)
    ps_air = _probe_success_rate('air', 'dry', 0.30, 2.0)
    assert ps_air > ps_tp


def test_probe_success_calling_station_lower():
    ps_call = _probe_success_rate('air', 'dry', 0.45, 2.0)
    ps_fold = _probe_success_rate('air', 'dry', 0.20, 2.0)
    assert ps_fold > ps_call


def test_should_not_float_aggressive_villain():
    should = _should_float(0.35, 1.0, 'float_to_probe', 4.0, 0.20, 'flop')
    assert not should


def test_should_not_float_low_check_back():
    should = _should_float(0.35, 1.0, 'float_to_probe', 1.5, 0.10, 'flop')
    assert not should


def test_should_not_float_on_river():
    should = _should_float(0.35, 1.0, 'float_to_probe', 1.5, 0.55, 'river')
    assert not should


def test_float_action_passive_villain():
    r = _ofa(villain_af=0.8, villain_cbet_turn_pct=0.25, hero_equity=0.38)
    assert r.action in ('float', 'call_showdown')


def test_fold_action_aggressive_villain():
    r = _ofa(villain_af=4.0, villain_cbet_turn_pct=0.80, hero_equity=0.25)
    assert r.action == 'fold'


def test_semi_float_draw():
    r = _ofa(hero_hand_category='flush_draw', board_texture='wet', hero_equity=0.38)
    assert r.float_type == 'semi_float'


def test_check_back_freq_in_result():
    r = _ofa()
    assert 0.0 < r.villain_check_back_freq < 1.0


def test_call_cost_computed():
    r = _ofa(cbet_size_pct=0.50, pot_bb=20.0)
    assert abs(r.call_cost_bb - 10.0) < 0.01


def test_probe_success_in_result():
    r = _ofa()
    assert 0.0 < r.probe_success_rate < 1.0


def test_float_ev_type():
    r = _ofa()
    assert isinstance(r.float_ev, float)


def test_tips_populated():
    r = _ofa()
    assert len(r.tips) >= 1


def test_one_liner_format():
    r = _ofa()
    line = ofa_one_liner(r)
    assert '[OFA' in line
    assert 'ev=' in line
    assert 'probe=' in line


def test_high_equity_can_call_showdown():
    r = _ofa(hero_equity=0.55, villain_af=3.5, villain_cbet_turn_pct=0.75)
    assert r.action in ('call_showdown', 'float', 'fold')


def test_air_hand_folds_vs_aggressive():
    r = _ofa(hero_hand_category='air', villain_af=3.2, hero_equity=0.15)
    assert r.action == 'fold'


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
