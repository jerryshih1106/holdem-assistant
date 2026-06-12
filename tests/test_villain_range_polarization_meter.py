"""Tests for villain_range_polarization_meter.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_range_polarization_meter import (
    measure_polarization, PolarizationResult, pol_one_liner,
    _af_component, _wtsd_component, _sizing_component, _streets_component,
    _action_sequence_component, _range_type,
)


def _pol(**kw):
    defaults = dict(
        villain_af=2.5,
        villain_wtsd=0.28,
        villain_vpip=0.28,
        streets_bet=2,
        avg_bet_size_pct=0.80,
        action_sequence='bet-bet',
        n_players=2,
        pot_bb=30.0,
    )
    defaults.update(kw)
    return measure_polarization(**defaults)


def test_returns_polarization_result():
    r = _pol()
    assert isinstance(r, PolarizationResult)


def test_af_component_high_af():
    c = _af_component(4.5)
    assert c >= 0.25


def test_af_component_low_af():
    c = _af_component(0.5)
    assert c <= 0.05


def test_af_component_increases_with_af():
    c_low = _af_component(0.5)
    c_high = _af_component(4.0)
    assert c_high > c_low


def test_wtsd_low_increases_polarization():
    c_low = _wtsd_component(0.18)
    c_high = _wtsd_component(0.42)
    assert c_low > c_high


def test_sizing_large_bet_polar():
    c = _sizing_component(2.0)
    assert c >= 0.20


def test_sizing_small_bet_condensed():
    c = _sizing_component(0.30)
    assert c <= 0.05


def test_streets_3_more_polar_than_1():
    c3 = _streets_component(3)
    c1 = _streets_component(1)
    assert c3 > c1


def test_sequence_raise_adds_polarity():
    c_raise = _action_sequence_component('bet-raise')
    c_plain = _action_sequence_component('bet-bet')
    assert c_raise > c_plain


def test_sequence_check_raise_polar():
    c = _action_sequence_component('check-raise')
    assert c >= 0.10


def test_range_type_highly_polarized():
    rt = _range_type(0.85)
    assert rt == 'highly_polarized'


def test_range_type_condensed():
    rt = _range_type(0.30)
    assert rt == 'condensed'


def test_range_type_linear():
    rt = _range_type(0.10)
    assert rt == 'linear'


def test_range_type_polarized():
    rt = _range_type(0.65)
    assert rt == 'polarized'


def test_high_af_3bet_polar():
    r = _pol(villain_af=4.5, villain_wtsd=0.18, avg_bet_size_pct=1.50, streets_bet=3)
    assert r.range_type in ('polarized', 'highly_polarized')


def test_low_af_small_bets_linear():
    r = _pol(villain_af=0.5, villain_wtsd=0.45, avg_bet_size_pct=0.33, streets_bet=1)
    assert r.range_type in ('linear', 'condensed', 'semi_polarized')


def test_polarization_score_0_to_1():
    r = _pol()
    assert 0.0 <= r.polarization_score <= 1.0


def test_range_type_stored():
    r = _pol()
    assert r.range_type in ('linear', 'condensed', 'semi_polarized', 'polarized', 'highly_polarized')


def test_exploitation_advice_nonempty():
    r = _pol()
    assert len(r.exploitation_advice) > 20


def test_tips_populated():
    r = _pol()
    assert len(r.tips) >= 1


def test_one_liner_format():
    r = _pol()
    line = pol_one_liner(r)
    assert '[POL' in line
    assert 'score=' in line
    assert 'af=' in line


def test_overbet_more_polar_than_small_bet():
    r_big = _pol(avg_bet_size_pct=1.50)
    r_small = _pol(avg_bet_size_pct=0.33)
    assert r_big.polarization_score > r_small.polarization_score


def test_all_streets_more_polar():
    r_3 = _pol(streets_bet=3)
    r_1 = _pol(streets_bet=1)
    assert r_3.polarization_score > r_1.polarization_score


def test_nut_advantage_condensed_higher():
    r_condensed = _pol(villain_af=0.3, villain_wtsd=0.50, avg_bet_size_pct=0.33, streets_bet=1)
    r_polar = _pol(villain_af=4.5, villain_wtsd=0.18, avg_bet_size_pct=1.50, streets_bet=3)
    assert r_condensed.nut_advantage_hero >= r_polar.nut_advantage_hero


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
